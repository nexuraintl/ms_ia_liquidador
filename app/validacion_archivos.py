"""
Módulo de validación de archivos.
Proporciona clases para validar extensiones de archivos subidos.
"""
import logging
from dataclasses import dataclass
from typing import List, Tuple
from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

# Extensiones soportadas por el sistema
EXTENSIONES_SOPORTADAS = {
    'pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp',  # Procesamiento directo
    'xlsx', 'xls', 'docx', 'doc', 'msg', 'eml', 'xml'  # Preprocesamiento local
}


@dataclass
class ResultadoValidacionArchivos:
    """
    Resultado de la validación de archivos.
    Puede desempaquetarse como tupla para compatibilidad.
    """
    archivos_validos: List[UploadFile]
    archivos_ignorados: List[str]

    def __iter__(self):
        """Permite desempaquetar como tupla: validos, ignorados = resultado"""
        # Retornar tupla directamente sin astuple() para evitar errores de serialización
        # con objetos UploadFile que contienen streams no serializables
        return iter((self.archivos_validos, self.archivos_ignorados))


class ValidadorArchivos:
    """
    Valida archivos subidos según extensiones soportadas.

    Responsabilidades:
    - Filtrar archivos por extensión válida
    - Validar que haya al menos un archivo válido
    - Registrar archivos ignorados en logs

    Example:
        >>> validador = ValidadorArchivos()
        >>> resultado = validador.validar(archivos)
        >>> print(f"Válidos: {len(resultado.archivos_validos)}")
    """

    def __init__(self):
        """Inicializa el validador con extensiones soportadas"""
        self.extensiones_soportadas = EXTENSIONES_SOPORTADAS

    def validar(self, archivos: List[UploadFile]) -> ResultadoValidacionArchivos:
        """
        Valida archivos y filtra por extensión soportada.

        Args:
            archivos: Lista de archivos subidos

        Returns:
            ResultadoValidacionArchivos con archivos válidos e ignorados

        Raises:
            HTTPException: Si ningún archivo tiene extensión soportada
        """
        # Filtrar archivos por extensión
        archivos_validos, archivos_ignorados = self._filtrar_por_extension(archivos)

        # Validar que haya al menos un archivo válido
        self._validar_minimo_un_archivo(archivos_validos, archivos)

        # Logging de resumen
        self._log_resumen(archivos, archivos_validos, archivos_ignorados)

        return ResultadoValidacionArchivos(
            archivos_validos=archivos_validos,
            archivos_ignorados=archivos_ignorados
        )

    def _filtrar_por_extension(
        self,
        archivos: List[UploadFile]
    ) -> Tuple[List[UploadFile], List[str]]:
        """
        Filtra archivos separando válidos de ignorados por extensión.

        Args:
            archivos: Lista de archivos a filtrar

        Returns:
            Tupla (archivos_validos, archivos_ignorados)
        """
        archivos_validos = []
        archivos_ignorados = []

        for archivo in archivos:
            try:
                nombre_archivo = archivo.filename
                extension = self._extraer_extension(nombre_archivo)

                if extension in self.extensiones_soportadas:
                    archivos_validos.append(archivo)
                else:
                    archivos_ignorados.append(nombre_archivo)
                    logger.warning(
                        f" Archivo ignorado (extensión no soportada): "
                        f"{nombre_archivo} (.{extension})"
                    )
            except Exception as e:
                logger.warning(f" Error clasificando archivo {archivo.filename}: {e}")
                archivos_ignorados.append(archivo.filename)

        return archivos_validos, archivos_ignorados

    def _extraer_extension(self, nombre_archivo: str) -> str:
        """
        Extrae la extensión del nombre de archivo.

        Args:
            nombre_archivo: Nombre del archivo con extensión

        Returns:
            Extensión en minúsculas (sin punto)
        """
        return nombre_archivo.split('.')[-1].lower() if '.' in nombre_archivo else ''

    def _validar_minimo_un_archivo(
        self,
        archivos_validos: List[UploadFile],
        archivos_originales: List[UploadFile]
    ) -> None:
        """
        Valida que haya al menos un archivo válido.

        Args:
            archivos_validos: Lista de archivos con extensión válida
            archivos_originales: Lista original de archivos

        Raises:
            HTTPException: Si no hay archivos válidos
        """
        if not archivos_validos:
            logger.error(" Ningún archivo con extensión soportada fue recibido")
            logger.error(f" Archivos recibidos: {[a.filename for a in archivos_originales]}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "NO_VALID_FILES",
                    "mensaje": "Ninguno de los archivos recibidos tiene una extensión soportada",
                    "extensiones_soportadas": list(self.extensiones_soportadas),
                    "total_archivos_recibidos": len(archivos_originales)
                }
            )

    def _log_resumen(
        self,
        archivos: List[UploadFile],
        archivos_validos: List[UploadFile],
        archivos_ignorados: List[str]
    ) -> None:
        """
        Registra resumen de validación en logs.

        Args:
            archivos: Lista original de archivos
            archivos_validos: Archivos con extensión válida
            archivos_ignorados: Nombres de archivos ignorados
        """
        logger.info(
            f" Archivos recibidos: {len(archivos)} | "
            f"Válidos: {len(archivos_validos)} | "
            f"Ignorados: {len(archivos_ignorados)}"
        )
        if archivos_ignorados:
            logger.info(f" Archivos ignorados: {archivos_ignorados}")
