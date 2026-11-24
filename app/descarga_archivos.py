"""Descarga de los documentos de una factura desde el gestor de archivos de Nexura.

El cliente no sube los bytes: en el cuerpo de la peticion envia los metadatos de cada
adjunto (`file_uri`, `name`, `mime_type`, `size`) y el servicio descarga el contenido
en memoria, en el mismo formato {filename, content_type, file} que consume el
pipeline de clasificacion.

La descarga es **secuencial y con una sola conexion reutilizada**. El servicio corre en
una instancia de 1 vCPU donde Cloud Run estrangula la CPU en cuanto el endpoint
responde: descargar en paralelo no acelera nada y si dispara el pico de memoria (todos
los adjuntos vivos a la vez) y el de CPU (un handshake TLS por archivo).
"""
import asyncio
import logging
import os
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import httpx

from app.validacion_archivos import EXTENSIONES_SOPORTADAS
from config import CONFIG

logger = logging.getLogger(__name__)

# Servidores que bloquean el User-Agent por defecto de las librerias HTTP.
# Mismo criterio que database/database.py al consultar la API de Nexura.
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

# Proporcion de adjuntos fallidos a partir de la cual se aborta la factura completa.
UMBRAL_ABORTO = 0.5

# Timeouts por fase, no un tope global. Al ser la descarga secuencial, un adjunto
# colgado retiene a los siguientes: mas vale rendirse pronto. Un `downloadFile` que
# tarda mas de 20 s en responder ya esta roto.
TIMEOUT_DESCARGA = httpx.Timeout(connect=5.0, read=20.0, write=20.0, pool=5.0)
MAX_REINTENTOS = 2

# Una sola conexion viva: la descarga es secuencial, mas conexiones solo gastarian
# handshakes TLS, que son trabajo de CPU en el peor momento posible.
LIMITES_CONEXION = httpx.Limits(max_connections=1, max_keepalive_connections=1)


class ArchivoInvalido(ValueError):
    """El adjunto no se puede descargar: metadatos incompletos o URI no permitida."""


class DescargaAbortada(RuntimeError):
    """Fallo la descarga de una proporcion de adjuntos igual o superior al umbral."""


@dataclass
class ResultadoDescarga:
    """Resultado de descargar los adjuntos de una factura.

    Attributes:
        archivos_data: Archivos descargados, en el formato {filename, content_type,
            file} que espera BackgroundProcessor. `file` es un BytesIO listo para
            envolver en UploadFile, no bytes: evita duplicar el contenido en memoria.
        fallidos: Adjuntos que no se pudieron descargar, con su motivo.
        omitidos: Nombres de adjuntos que no se descargaron por tener una extension que
            el pipeline no procesa (p. ej. audio): bajarlos solo gastaria red y memoria.
    """

    archivos_data: List[Dict[str, Any]] = field(default_factory=list)
    fallidos: List[Dict[str, str]] = field(default_factory=list)
    omitidos: List[str] = field(default_factory=list)

    @property
    def resumen_fallos(self) -> str:
        """Devuelve los fallos en una linea legible para logs y mensajes al usuario."""
        return '; '.join(f"{f['archivo']}: {f['motivo']}" for f in self.fallidos)


def hosts_permitidos() -> Set[str]:
    """Devuelve los hosts desde los que se acepta descargar adjuntos.

    Se derivan de NEXURA_API_BASE_URL. Restringir el host no es cosmetico: descargar
    URLs arbitrarias enviadas por el cliente seria una via de SSRF contra la red interna.

    Returns:
        Conjunto de hosts permitidos; vacio si la variable de entorno no esta definida.
    """
    host = urlparse(os.getenv('NEXURA_API_BASE_URL', '')).netloc
    return {host} if host else set()


def nombre_seguro(nombre: Optional[str]) -> Optional[str]:
    """Sanea el nombre declarado por el cliente.

    Es un dato critico: todo el ruteo posterior del sistema depende de la extension
    del nombre, no del mime_type.

    Args:
        nombre: Valor del campo `name` del adjunto.

    Returns:
        El nombre sin componentes de ruta, o None si no queda nada utilizable.
    """
    if not nombre or not nombre.strip():
        return None

    # Path(...).name descarta cualquier intento de traversal en el nombre remoto.
    return Path(nombre.strip()).name or None


def extension_soportada(nombre: str) -> bool:
    """Indica si el pipeline procesa la extension del archivo.

    Mismo criterio que ValidadorArchivos: la extension es lo que va tras el ultimo punto.

    Args:
        nombre: Nombre del archivo ya saneado.

    Returns:
        True si la extension esta en EXTENSIONES_SOPORTADAS.
    """
    return '.' in nombre and nombre.rsplit('.', 1)[-1].lower() in EXTENSIONES_SOPORTADAS


def validar_adjunto(adjunto: Dict[str, Any]) -> None:
    """Valida los metadatos de un adjunto sin descargarlo.

    Args:
        adjunto: Diccionario con las claves file_uri, name, mime_type y size.

    Raises:
        ArchivoInvalido: Si falta la URI o el nombre, la URI apunta a un host ajeno a
            la API de Nexura o el tamaño declarado supera el maximo permitido.
    """
    uri = (adjunto.get('file_uri') or '').strip()
    if not uri:
        raise ArchivoInvalido('El adjunto no trae "file_uri"')

    partes = urlparse(uri)
    if partes.scheme not in ('http', 'https'):
        raise ArchivoInvalido('El "file_uri" debe empezar por http:// o https://')

    permitidos = hosts_permitidos()
    if partes.netloc not in permitidos:
        origen = ', '.join(sorted(permitidos)) or 'la API de Nexura'
        raise ArchivoInvalido(
            f'Solo se aceptan archivos de {origen}, no de "{partes.netloc}"'
        )

    nombre = nombre_seguro(adjunto.get('name'))
    if not nombre:
        raise ArchivoInvalido(
            f'El adjunto {uri} no trae un "name" utilizable; la extension del nombre '
            'determina como se procesa el documento'
        )

    _validar_tamaño_declarado(nombre, adjunto.get('size'))


def validar_adjuntos(archivos: List[Dict[str, Any]]) -> None:
    """Valida la lista completa de adjuntos sin descargar nada.

    Pensada para ejecutarse en el endpoint, de modo que un payload mal construido
    falle de inmediato en vez de hacerlo mas tarde por webhook.

    Args:
        archivos: Adjuntos enviados por el cliente.

    Raises:
        ArchivoInvalido: Si la lista esta vacia, supera el maximo de archivos o alguno
            de los adjuntos no es descargable.
    """
    if not archivos:
        raise ArchivoInvalido('Debe enviar al menos un archivo')

    maximo = CONFIG['max_archivos']
    if len(archivos) > maximo:
        raise ArchivoInvalido(f'Maximo {maximo} archivos por factura, recibidos {len(archivos)}')

    for adjunto in archivos:
        validar_adjunto(adjunto)


def _validar_tamaño_declarado(nombre: str, size: Any) -> None:
    """Rechaza por tamaño antes de gastar una descarga.

    El campo `size` llega como texto y es informativo: si no es numerico se ignora,
    porque el limite real se aplica igualmente sobre los bytes recibidos.

    Args:
        nombre: Nombre del archivo, para el mensaje de error.
        size: Tamaño declarado en bytes.

    Raises:
        ArchivoInvalido: Si el tamaño declarado supera CONFIG['max_tamaño_mb'].
    """
    try:
        declarado = int(float(size))
    except (TypeError, ValueError):
        return

    if declarado > CONFIG['max_tamaño_mb'] * 1024 * 1024:
        raise ArchivoInvalido(
            f"El archivo '{nombre}' declara {declarado / 1024 / 1024:.2f} MB y supera "
            f"el maximo de {CONFIG['max_tamaño_mb']} MB"
        )


class DescargadorArchivos:
    """Descarga los adjuntos de una factura desde el gestor de archivos de Nexura.

    Los archivos se mantienen en memoria: el pipeline trabaja con bytes, no con rutas.

    Example:
        >>> descargador = DescargadorArchivos(factura_id, token)
        >>> resultado = await descargador.descargar_todos(archivos)
    """

    def __init__(
        self,
        factura_id: int,
        token: Optional[str] = None,
        timeout: Optional[httpx.Timeout] = None,
    ):
        """Inicializa el descargador.

        Args:
            factura_id: Identificador de la factura, usado para trazar los logs.
            token: Token JWT de Nexura. Se envia como Bearer si esta disponible; el
                endpoint de descarga actual no lo exige, pero si lo exigiera en
                produccion la descarga seguiria funcionando.
            timeout: Timeouts por fase de cada peticion. Por defecto TIMEOUT_DESCARGA.
        """
        self.factura_id = factura_id
        self.token = token
        self.timeout = timeout or TIMEOUT_DESCARGA
        self.max_bytes = CONFIG['max_tamaño_mb'] * 1024 * 1024

    def _cabeceras(self) -> Dict[str, str]:
        """Construye las cabeceras de la descarga.

        Returns:
            User-Agent de navegador y, si hay token, la cabecera Authorization.
        """
        cabeceras = {'User-Agent': USER_AGENT}
        if self.token:
            cabeceras['Authorization'] = f'Bearer {self.token}'
        return cabeceras

    async def descargar_todos(self, archivos: List[Dict[str, Any]]) -> ResultadoDescarga:
        """Descarga los adjuntos uno a uno y aplica la regla de aborto.

        Secuencial y sobre una unica conexion reutilizada: con 1 vCPU el paralelismo
        no da velocidad, solo multiplica el pico de memoria y los handshakes TLS.

        Los adjuntos con extension no soportada se omiten sin descargar: ValidadorArchivos
        los descartaria igualmente despues, y no cuentan para el umbral de aborto.

        Args:
            archivos: Adjuntos enviados por el cliente.

        Returns:
            ResultadoDescarga con los archivos obtenidos, los fallidos y los omitidos.

        Raises:
            DescargaAbortada: Si falla una proporcion de adjuntos igual o superior a
                UMBRAL_ABORTO. Se aborta porque la ausencia de un documento puede
                alterar la liquidacion sin que nadie lo advierta.
        """
        resultado = ResultadoDescarga()
        descargables = []
        for adjunto in archivos:
            nombre = nombre_seguro(adjunto.get('name'))
            if nombre and not extension_soportada(nombre):
                resultado.omitidos.append(nombre)
                logger.warning(
                    f"Factura {self.factura_id}: Omitido sin descargar '{nombre}' "
                    '(extension no soportada)'
                )
            else:
                descargables.append(adjunto)

        total = len(descargables)
        logger.info(
            f"Factura {self.factura_id}: Descargando {total} archivos de Nexura "
            f'(secuencial, conexion reutilizada); {len(resultado.omitidos)} omitidos'
        )

        async with httpx.AsyncClient(
            timeout=self.timeout,
            limits=LIMITES_CONEXION,
            follow_redirects=True,
        ) as cliente:
            for adjunto in descargables:
                try:
                    resultado.archivos_data.append(await self._descargar_uno(cliente, adjunto))
                except Exception as e:
                    motivo = str(e) or type(e).__name__
                    referencia = adjunto.get('name') or adjunto.get('file_uri') or '(sin nombre)'
                    logger.warning(f"Factura {self.factura_id}: Fallo {referencia} - {motivo}")
                    resultado.fallidos.append({'archivo': referencia, 'motivo': motivo})

        fallidos = len(resultado.fallidos)
        if total and (fallidos / total) >= UMBRAL_ABORTO:
            raise DescargaAbortada(
                f'No se pudieron descargar {fallidos} de {total} archivos de la API de '
                f'Nexura. {resultado.resumen_fallos}'
            )

        if fallidos:
            logger.warning(
                f"Factura {self.factura_id}: Continuando con {len(resultado.archivos_data)} "
                f"de {total} archivos ({fallidos} fallidos)"
            )

        return resultado

    async def _descargar_uno(
        self,
        cliente: httpx.AsyncClient,
        adjunto: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Descarga un adjunto con reintentos ante fallos transitorios.

        Solo se reintentan timeouts, errores de conexion y respuestas 429 o 5xx.
        Un 404, un archivo sin permisos o una URI mal formada son permanentes:
        reintentarlos solo retrasa el fallo.

        Args:
            cliente: Cliente HTTP compartido por todo el lote.
            adjunto: Diccionario con file_uri, name, mime_type y size.

        Returns:
            Diccionario {filename, content_type, file} listo para el pipeline.

        Raises:
            ArchivoInvalido: Ante cualquier fallo permanente.
        """
        validar_adjunto(adjunto)
        uri = adjunto['file_uri'].strip()
        nombre = nombre_seguro(adjunto.get('name'))
        mime = adjunto.get('mime_type')

        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                return await self._intentar_descarga(cliente, uri, nombre, mime)

            except ArchivoInvalido:
                raise  # Permanente: no tiene sentido reintentar.

            except (httpx.TimeoutException, httpx.TransportError) as e:
                if intento == MAX_REINTENTOS:
                    raise ArchivoInvalido(f'No se pudo conectar con la API de Nexura: {e}') from e
                logger.info(
                    f"Factura {self.factura_id}: Reintento {intento}/{MAX_REINTENTOS} "
                    f"de '{nombre}' tras error de red"
                )
                await asyncio.sleep(2 ** intento)

        raise ArchivoInvalido('No se pudo descargar el archivo')  # pragma: no cover

    async def _intentar_descarga(
        self,
        cliente: httpx.AsyncClient,
        uri: str,
        nombre: str,
        mime: Optional[str],
    ) -> Dict[str, Any]:
        """Ejecuta un intento de descarga por streaming.

        Args:
            cliente: Cliente HTTP compartido por todo el lote.
            uri: URL de descarga enviada por el cliente.
            nombre: Nombre ya saneado del archivo.
            mime: Tipo MIME declarado por el cliente.

        Returns:
            Diccionario {filename, content_type, file}.

        Raises:
            ArchivoInvalido: Fallo permanente (404, sin permisos, HTML de error o
                tamaño excedido).
            httpx.TransportError: Fallo transitorio, gestionado por el llamador.
        """
        async with cliente.stream('GET', uri, headers=self._cabeceras()) as respuesta:
            self._verificar_respuesta(respuesta, nombre)
            buffer = await self._leer_con_limite(respuesta, nombre)

        logger.info(
            f"Factura {self.factura_id}: Descargado '{nombre}' "
            f"({buffer.tell() / 1024 / 1024:.2f} MB)"
        )
        buffer.seek(0)
        return {
            'filename': nombre,
            'content_type': mime or respuesta.headers.get('content-type'),
            'file': buffer,
        }

    def _verificar_respuesta(self, respuesta: httpx.Response, nombre: str) -> None:
        """Comprueba que la respuesta trae un archivo y no una pagina de error.

        Args:
            respuesta: Respuesta en streaming, aun sin consumir.
            nombre: Nombre del archivo, para el mensaje de error.

        Raises:
            ArchivoInvalido: Si el estado es permanente o el cuerpo es HTML.
            httpx.TransportError: Si el estado es transitorio (429 o 5xx).
        """
        codigo = respuesta.status_code

        if codigo in (401, 403):
            raise ArchivoInvalido(
                f"Sin permiso para descargar '{nombre}'. Verifique las credenciales "
                'del servicio contra la API de Nexura'
            )
        if codigo == 404:
            raise ArchivoInvalido(f"El archivo '{nombre}' no existe o fue eliminado")
        if codigo == 429 or codigo >= 500:
            raise httpx.TransportError(f'La API de Nexura respondio {codigo}')
        if codigo != 200:
            raise ArchivoInvalido(f"La API de Nexura respondio {codigo} al descargar '{nombre}'")

        # Nexura devuelve HTML cuando la sesion caduca o el archivo no esta disponible.
        # Ese HTML NUNCA debe llegar a los extractores.
        tipo = (respuesta.headers.get('content-type') or '').lower()
        if 'text/html' in tipo:
            raise ArchivoInvalido(
                f"La API de Nexura devolvio una pagina web en vez del archivo '{nombre}'. "
                'Suele indicar que el archivo ya no esta disponible'
            )

    async def _leer_con_limite(self, respuesta: httpx.Response, nombre: str) -> BytesIO:
        """Vuelca el cuerpo en un buffer, cortando si se supera el tamaño maximo.

        No se confia en Content-Length ni en el `size` declarado: pueden faltar o no
        coincidir con lo que se envia realmente, asi que el limite se aplica sobre los
        bytes recibidos.

        Se escribe directamente en el BytesIO que acabara siendo el UploadFile: la
        version anterior acumulaba trozos en una lista y hacia `b''.join`, lo que
        duplicaba el pico de memoria de cada archivo sin necesidad.

        Args:
            respuesta: Respuesta en streaming.
            nombre: Nombre del archivo, para el mensaje de error.

        Returns:
            Buffer con el contenido completo; el puntero queda al final, de modo que
            `tell()` da el tamaño descargado.

        Raises:
            ArchivoInvalido: Si se supera CONFIG['max_tamaño_mb'].
        """
        buffer = BytesIO()
        acumulado = 0

        async for trozo in respuesta.aiter_bytes():
            acumulado += len(trozo)
            if acumulado > self.max_bytes:
                raise ArchivoInvalido(
                    f"El archivo '{nombre}' supera el maximo de "
                    f"{CONFIG['max_tamaño_mb']} MB"
                )
            buffer.write(trozo)

        return buffer
