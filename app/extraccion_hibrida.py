"""
Módulo de extracción híbrida de archivos.
Combina procesamiento multimodal (directo a Gemini) con preprocesamiento local.
"""
import asyncio
import logging
from dataclasses import dataclass
from functools import partial
from io import BytesIO
from typing import List, Dict, Tuple
from fastapi import UploadFile
from Extraccion import ProcesadorArchivos, preprocesar_excel_limpio, ExtractorAdjuntos, ExtractorZip, AdjuntoExtraido
from app.validacion_archivos import ValidadorArchivos

logger = logging.getLogger(__name__)


@dataclass
class ResultadoExtraccion:
    """
    Resultado de la extracción híbrida.
    Puede desempaquetarse como tupla para compatibilidad.
    """
    archivos_directos: List[UploadFile]
    textos_preprocesados: Dict[str, str]

    def __iter__(self):
        """Permite desempaquetar como tupla: directos, preprocesados = resultado"""
        return iter((self.archivos_directos, self.textos_preprocesados))


class ExtractorHibrido:
    """
    Extractor híbrido que combina procesamiento multimodal con local.

    Responsabilidades:
    - Clasificar archivos por estrategia (directo vs preprocesamiento)
    - Procesar archivos localmente cuando sea necesario
    - Preprocesar archivos Excel de forma específica

    Example:
        >>> extractor = ExtractorHibrido()
        >>> resultado = await extractor.extraer(archivos)
        >>> print(f"Directos: {len(resultado.archivos_directos)}")
    """

    EXTENSIONES_DIRECTAS = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp'}
    EXTENSIONES_EXCEL = {'xlsx', 'xls'}
    EXTENSIONES_WORD = {'docx', 'doc'}
    EXTENSIONES_ZIP = {'zip'}

    def __init__(self):
        """Inicializa el extractor con procesadores necesarios"""
        self.extractor = ProcesadorArchivos()
        self.validador = ValidadorArchivos()
        self.extractor_adjuntos = ExtractorAdjuntos()
        self.extractor_zip = ExtractorZip()

    async def extraer(self, archivos_validos: List[UploadFile]) -> ResultadoExtraccion:
        """
        Ejecuta extracción híbrida de archivos.

        Args:
            archivos_validos: Lista de archivos ya validados

        Returns:
            ResultadoExtraccion con archivos directos y textos preprocesados
        """
        logger.info(" Iniciando procesamiento híbrido multimodal: separando archivos por estrategia...")

        # Separar archivos por estrategia
        archivos_directos, archivos_preprocesamiento = self._clasificar_por_estrategia(archivos_validos)

        # Separar ZIPs del preprocesamiento local (no son archivos de texto)
        archivos_para_extraccion_local = [
            a for a in archivos_preprocesamiento
            if not (a.filename and a.filename.lower().endswith('.zip'))
        ]

        # Procesar archivos locales (sin ZIPs)
        textos_archivos_original = await self._procesar_archivos_locales(archivos_para_extraccion_local)

        # Preprocesamiento adicional para Excel
        textos_preprocesados = await self._preprocesar_excel(
            textos_archivos_original,
            archivos_para_extraccion_local
        )

        # Extraer y procesar archivos embebidos en emails (.msg / .eml)
        adjuntos_directos, textos_adjuntos = await self._procesar_adjuntos_emails(archivos_preprocesamiento)
        archivos_directos.extend(adjuntos_directos)
        textos_preprocesados.update(textos_adjuntos)

        # Extraer y procesar archivos contenidos en ZIPs (con deduplicacion)
        zip_directos, textos_zip = await self._procesar_archivos_zip(
            archivos_preprocesamiento, archivos_validos
        )
        archivos_directos.extend(zip_directos)
        textos_preprocesados.update(textos_zip)

        return ResultadoExtraccion(
            archivos_directos=archivos_directos,
            textos_preprocesados=textos_preprocesados
        )

    def _clasificar_por_estrategia(
        self,
        archivos_validos: List[UploadFile]
    ) -> tuple[List[UploadFile], List[UploadFile]]:
        """
        Clasifica archivos según estrategia de procesamiento.

        - PDFs e imágenes: Procesamiento directo multimodal (Gemini)
        - Excel, Email, Word: Preprocesamiento local

        Args:
            archivos_validos: Lista de archivos validados

        Returns:
            Tupla (archivos_directos, archivos_preprocesamiento)
        """
        archivos_directos = []
        archivos_preprocesamiento = []

        # Extensiones para procesamiento directo multimodal
        extensiones_directas = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp'}

        for archivo in archivos_validos:
            try:
                nombre_archivo = archivo.filename
                extension = self.validador._extraer_extension(nombre_archivo)

                if extension in extensiones_directas:
                    archivos_directos.append(archivo)
                    logger.info(f" Archivo directo (multimodal): {nombre_archivo}")
                else:
                    archivos_preprocesamiento.append(archivo)
                    logger.info(f" Archivo para preprocesamiento: {nombre_archivo}")
            except Exception as e:
                logger.warning(f" Error clasificando archivo: {e}")
                logger.warning(f"Enviando a preprocesamiento por seguridad: {archivo.filename}")
                archivos_preprocesamiento.append(archivo)

        logger.info(" Estrategia híbrida multimodal definida:")
        logger.info(f" Archivos directos (multimodal): {len(archivos_directos)}")
        logger.info(f" Archivos preprocesamiento local: {len(archivos_preprocesamiento)}")

        return archivos_directos, archivos_preprocesamiento

    async def _procesar_archivos_locales(
        self,
        archivos_preprocesamiento: List[UploadFile]
    ) -> Dict[str, str]:
        """
        Procesa archivos que requieren preprocesamiento local.

        Args:
            archivos_preprocesamiento: Lista de archivos para procesamiento local

        Returns:
            Diccionario {nombre_archivo: texto_extraído}
        """
        if archivos_preprocesamiento:
            logger.info(f" Iniciando extracción local para {len(archivos_preprocesamiento)} archivos...")
            textos_archivos_original = await self.extractor.procesar_multiples_archivos(
                archivos_preprocesamiento
            )
        else:
            logger.info(" No hay archivos para procesamiento local - Solo archivos directos multimodales")
            textos_archivos_original = {}

        return textos_archivos_original

    async def _preprocesar_excel(
        self,
        textos_archivos_original: Dict[str, str],
        archivos_preprocesamiento: List[UploadFile]
    ) -> Dict[str, str]:
        """
        Aplica preprocesamiento especializado a archivos Excel.

        Args:
            textos_archivos_original: Textos extraídos originalmente
            archivos_preprocesamiento: Lista de archivos originales para acceso

        Returns:
            Diccionario {nombre_archivo: texto_preprocesado}
        """
        textos_preprocesados = {}

        for nombre_archivo, contenido_original in textos_archivos_original.items():
            if nombre_archivo.lower().endswith(('.xlsx', '.xls')):
                try:
                    # Obtener archivo original
                    archivo_obj = next(
                        (arch for arch in archivos_preprocesamiento if arch.filename == nombre_archivo),
                        None
                    )

                    if archivo_obj:
                        await archivo_obj.seek(0)
                        contenido_binario = await archivo_obj.read()
                        loop = asyncio.get_event_loop()
                        texto_preprocesado = await loop.run_in_executor(
                            None,
                            partial(preprocesar_excel_limpio, contenido_binario, nombre_archivo)
                        )
                        textos_preprocesados[nombre_archivo] = texto_preprocesado
                        logger.info(f" Excel preprocesado: {nombre_archivo}")
                    else:
                        textos_preprocesados[nombre_archivo] = contenido_original
                except Exception as e:
                    logger.warning(f" Error preprocesando {nombre_archivo}: {e}")
                    textos_preprocesados[nombre_archivo] = contenido_original
            else:
                textos_preprocesados[nombre_archivo] = contenido_original

        logger.info(f" Extracción local completada: {len(textos_preprocesados)} textos extraídos")

        return textos_preprocesados

    async def _procesar_adjuntos_emails(
        self,
        archivos_preprocesamiento: List[UploadFile]
    ) -> Tuple[List[UploadFile], Dict[str, str]]:
        """
        Extrae y procesa archivos embebidos en emails .msg y .eml.

        Para cada adjunto encontrado aplica el procesamiento correcto:
        - PDF / imagen  → UploadFile sintetico para procesamiento multimodal (Gemini)
        - Excel         → preprocesar_excel_limpio() → texto preprocesado
        - Word          → extraer_texto_word() → texto preprocesado
        - Otros         → ignorar con log informativo

        Args:
            archivos_preprocesamiento: Archivos que pasaron por procesamiento local

        Returns:
            Tupla (nuevos_archivos_directos, nuevos_textos_preprocesados)
        """
        nuevos_directos: List[UploadFile] = []
        nuevos_textos: Dict[str, str] = {}

        emails = [
            arch for arch in archivos_preprocesamiento
            if arch.filename and arch.filename.lower().endswith(('.msg', '.eml'))
        ]

        if not emails:
            return nuevos_directos, nuevos_textos

        logger.info(f" Extrayendo adjuntos embebidos de {len(emails)} email(s)...")

        for archivo in emails:
            try:
                await archivo.seek(0)
                contenido = await archivo.read()
                extension_email = archivo.filename.lower().rsplit('.', 1)[-1]

                if extension_email == 'msg':
                    adjuntos = self.extractor_adjuntos.extraer_de_msg(contenido, archivo.filename)
                else:
                    adjuntos = self.extractor_adjuntos.extraer_de_eml(contenido, archivo.filename)

                for adjunto in adjuntos:
                    await self._enrutar_adjunto(adjunto, nuevos_directos, nuevos_textos)

            except Exception as e:
                logger.warning(f" Error procesando adjuntos de {archivo.filename}: {e}")

        logger.info(
            f" Adjuntos procesados — directos: {len(nuevos_directos)}, textos: {len(nuevos_textos)}"
        )
        return nuevos_directos, nuevos_textos

    async def _enrutar_adjunto(
        self,
        adjunto,
        nuevos_directos: List[UploadFile],
        nuevos_textos: Dict[str, str]
    ) -> None:
        """
        Enruta un adjunto extraido al procesador correspondiente segun su extension.

        Args:
            adjunto: AdjuntoExtraido con nombre, contenido y extension
            nuevos_directos: Lista de UploadFile para procesamiento multimodal
            nuevos_textos: Dict de textos preprocesados
        """
        if adjunto.extension in self.EXTENSIONES_DIRECTAS:
            nuevos_directos.append(self._crear_upload_file(adjunto.contenido, adjunto.nombre))
            logger.info(f" Adjunto directo (multimodal): {adjunto.nombre}")

        elif adjunto.extension in self.EXTENSIONES_EXCEL:
            loop = asyncio.get_event_loop()
            nuevos_textos[adjunto.nombre] = await loop.run_in_executor(
                None,
                partial(preprocesar_excel_limpio, adjunto.contenido, adjunto.nombre)
            )
            logger.info(f" Adjunto Excel preprocesado: {adjunto.nombre}")

        elif adjunto.extension in self.EXTENSIONES_WORD:
            nuevos_textos[adjunto.nombre] = await self.extractor.extraer_texto_word(adjunto.contenido, adjunto.nombre)
            logger.info(f" Adjunto Word extraido: {adjunto.nombre}")

        else:
            logger.info(f" Adjunto ignorado (tipo no soportado): {adjunto.nombre} (.{adjunto.extension})")

    async def _procesar_archivos_zip(
        self,
        archivos_preprocesamiento: List[UploadFile],
        todos_los_archivos: List[UploadFile]
    ) -> Tuple[List[UploadFile], Dict[str, str]]:
        """
        Extrae y procesa archivos contenidos en ZIPs.
        Deduplica contra archivos ya recibidos antes de procesar.

        Para cada archivo unico encontrado aplica el procesamiento correcto:
        - PDF / imagen  -> UploadFile sintetico para procesamiento multimodal (Gemini)
        - Excel         -> preprocesar_excel_limpio() -> texto preprocesado
        - Word          -> extraer_texto_word() -> texto preprocesado
        - Otros         -> ignorar con log informativo

        Args:
            archivos_preprocesamiento: Archivos clasificados para preprocesamiento
            todos_los_archivos: Todos los archivos recibidos (para deduplicacion)

        Returns:
            Tupla (nuevos_archivos_directos, nuevos_textos_preprocesados)
        """
        nuevos_directos: List[UploadFile] = []
        nuevos_textos: Dict[str, str] = {}

        zips = [
            arch for arch in archivos_preprocesamiento
            if arch.filename and arch.filename.lower().endswith('.zip')
        ]

        if not zips:
            return nuevos_directos, nuevos_textos

        logger.info(f" Extrayendo archivos de {len(zips)} ZIP(s)...")

        # Archivos no-ZIP para deduplicacion
        archivos_no_zip = [
            a for a in todos_los_archivos
            if not (a.filename and a.filename.lower().endswith('.zip'))
        ]

        for archivo in zips:
            try:
                await archivo.seek(0)
                contenido = await archivo.read()

                adjuntos = self.extractor_zip.extraer_de_zip(contenido, archivo.filename)

                adjuntos_unicos = self._deduplicar_adjuntos_zip(
                    adjuntos, archivos_no_zip, archivo.filename
                )

                for adjunto in adjuntos_unicos:
                    await self._enrutar_adjunto(adjunto, nuevos_directos, nuevos_textos)

            except Exception as e:
                logger.warning(f" Error procesando ZIP {archivo.filename}: {e}")

        logger.info(
            f" ZIPs procesados -- directos: {len(nuevos_directos)}, textos: {len(nuevos_textos)}"
        )
        return nuevos_directos, nuevos_textos

    def _deduplicar_adjuntos_zip(
        self,
        adjuntos: List[AdjuntoExtraido],
        archivos_existentes: List[UploadFile],
        nombre_zip: str
    ) -> List[AdjuntoExtraido]:
        """
        Filtra adjuntos de ZIP que ya existen entre los archivos recibidos.
        Criterio: mismo nombre de archivo (case-insensitive) Y tamano similar (+-10%).

        Args:
            adjuntos: Archivos extraidos del ZIP
            archivos_existentes: Archivos recibidos directamente (no-ZIP)
            nombre_zip: Nombre del ZIP para logging

        Returns:
            Lista de adjuntos unicos (no duplicados)
        """
        existentes = self._construir_indice_archivos(archivos_existentes)

        unicos: List[AdjuntoExtraido] = []
        for adjunto in adjuntos:
            if self._es_duplicado(adjunto, existentes, nombre_zip):
                continue
            unicos.append(adjunto)

        duplicados = len(adjuntos) - len(unicos)
        if duplicados > 0:
            logger.info(
                f" ZIP '{nombre_zip}': {duplicados} duplicado(s) omitido(s), "
                f"{len(unicos)} archivo(s) nuevo(s)"
            )
        return unicos

    def _construir_indice_archivos(
        self,
        archivos: List[UploadFile]
    ) -> Dict[str, int]:
        """
        Construye un indice {nombre_lower: tamano_bytes} de archivos existentes.

        Args:
            archivos: Lista de UploadFile para indexar

        Returns:
            Diccionario con nombre en minusculas como clave y tamano como valor
        """
        indice: Dict[str, int] = {}
        for arch in archivos:
            if not arch.filename:
                continue
            try:
                pos = arch.file.tell()
                arch.file.seek(0, 2)
                size = arch.file.tell()
                arch.file.seek(pos)
                indice[arch.filename.lower()] = size
            except Exception:
                indice[arch.filename.lower()] = 0
        return indice

    def _es_duplicado(
        self,
        adjunto: AdjuntoExtraido,
        existentes: Dict[str, int],
        nombre_zip: str
    ) -> bool:
        """
        Verifica si un adjunto es duplicado de un archivo existente.
        Compara nombre (case-insensitive) y tamano (tolerancia +-10%).

        Args:
            adjunto: Archivo extraido del ZIP
            existentes: Indice de archivos existentes {nombre_lower: tamano}
            nombre_zip: Nombre del ZIP para logging

        Returns:
            True si el adjunto es duplicado
        """
        nombre_lower = adjunto.nombre.lower()
        if nombre_lower not in existentes:
            return False

        tamano_existente = existentes[nombre_lower]
        if tamano_existente <= 0:
            return False

        tamano_adjunto = len(adjunto.contenido)
        ratio = tamano_adjunto / tamano_existente
        if 0.9 <= ratio <= 1.1:
            logger.info(
                f" Duplicado en ZIP '{nombre_zip}': '{adjunto.nombre}' "
                f"({tamano_adjunto} bytes) ya existe ({tamano_existente} bytes) - Omitido"
            )
            return True

        return False

    def _crear_upload_file(self, contenido: bytes, nombre: str) -> UploadFile:
        """
        Crea un UploadFile sintetico a partir de bytes en memoria.
        Permite tratar adjuntos extraidos igual que archivos subidos directamente.

        Args:
            contenido: Bytes del archivo adjunto
            nombre: Nombre del archivo (con extension)

        Returns:
            UploadFile listo para ser enviado a Gemini Files API
        """
        return UploadFile(file=BytesIO(contenido), filename=nombre)
