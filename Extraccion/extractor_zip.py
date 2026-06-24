"""
EXTRACTOR DE ARCHIVOS ZIP
==========================

SRP: Responsabilidad unica - extraer archivos contenidos en archivos .zip.
OCP: Extensible para nuevos tipos de contenedores comprimidos.

No realiza procesamiento del contenido: solo extrae bytes y metadata.
El procesamiento posterior (upload a Files API, preprocesamiento Excel, etc.)
es responsabilidad de quien consuma esta clase.
"""
import zipfile
import logging
from io import BytesIO
from pathlib import Path
from typing import List

from Extraccion.extractor_adjuntos import AdjuntoExtraido

logger = logging.getLogger(__name__)


class ExtractorZip:
    """
    Extrae archivos contenidos en archivos .zip en memoria.

    Responsabilidades (SRP):
    - Extraer bytes de archivos dentro de un .zip via stdlib zipfile
    - Normalizar nombre y extension de cada archivo extraido
    - Aplicar limites de seguridad (max archivos, max tamano, no ZIPs anidados)

    NO responsable de:
    - Subir archivos a Files API
    - Preprocesar Excel
    - Extraer texto de archivos
    - Deduplicar contra archivos externos
    """

    EXTENSION_DESCONOCIDA = "bin"
    MAX_ARCHIVOS_ZIP = 20
    MAX_TAMANO_TOTAL_BYTES = 100 * 1024 * 1024  # 100 MB
    EXTENSIONES_ZIP_ANIDADO = {'zip', 'rar', '7z', 'tar', 'gz'}

    def extraer_de_zip(self, contenido: bytes, nombre_zip: str) -> List[AdjuntoExtraido]:
        """
        Extrae archivos de un archivo .zip en memoria.

        Args:
            contenido: Bytes del archivo .zip
            nombre_zip: Nombre del .zip para logging

        Returns:
            Lista de AdjuntoExtraido con nombre, bytes y extension.
            Omite: directorios, ZIPs anidados, archivos que excedan limites.
        """
        adjuntos: List[AdjuntoExtraido] = []

        try:
            buffer = BytesIO(contenido)

            if not zipfile.is_zipfile(buffer):
                logger.warning(f"Archivo no es un ZIP valido: {nombre_zip}")
                return []

            buffer.seek(0)

            with zipfile.ZipFile(buffer, 'r') as zf:
                archivos_validos = [
                    info for info in zf.infolist()
                    if not info.is_dir()
                    and not info.filename.startswith('__MACOSX')
                ]

                if not archivos_validos:
                    logger.info(f"ZIP vacio (sin archivos): {nombre_zip}")
                    return []

                tamano_total = sum(info.file_size for info in archivos_validos)
                if tamano_total > self.MAX_TAMANO_TOTAL_BYTES:
                    logger.warning(
                        f"ZIP '{nombre_zip}' excede tamano maximo descomprimido: "
                        f"{tamano_total / (1024*1024):.1f} MB > "
                        f"{self.MAX_TAMANO_TOTAL_BYTES / (1024*1024):.0f} MB"
                    )
                    return []

                if len(archivos_validos) > self.MAX_ARCHIVOS_ZIP:
                    logger.warning(
                        f"ZIP '{nombre_zip}' contiene {len(archivos_validos)} archivos, "
                        f"excede maximo de {self.MAX_ARCHIVOS_ZIP}"
                    )
                    return []

                for info in archivos_validos:
                    try:
                        adjunto = self._extraer_archivo(zf, info, nombre_zip)
                        if adjunto:
                            adjuntos.append(adjunto)
                    except Exception as e:
                        logger.warning(
                            f"Error extrayendo '{info.filename}' de ZIP '{nombre_zip}': {e}"
                        )

        except zipfile.BadZipFile:
            logger.error(f"Archivo ZIP corrupto: {nombre_zip}")
        except Exception as e:
            logger.error(f"Error procesando ZIP '{nombre_zip}': {e}")

        logger.info(f"ZIP '{nombre_zip}': {len(adjuntos)} archivo(s) extraido(s)")
        return adjuntos

    def _extraer_archivo(
        self,
        zf: zipfile.ZipFile,
        info: zipfile.ZipInfo,
        nombre_zip: str
    ) -> AdjuntoExtraido | None:
        """
        Extrae un archivo individual de un ZipFile.
        Ignora archivos comprimidos anidados para evitar zip bombs.

        Args:
            zf: ZipFile abierto
            info: ZipInfo del archivo a extraer
            nombre_zip: Nombre del ZIP padre para logging

        Returns:
            AdjuntoExtraido o None si debe omitirse
        """
        nombre = Path(info.filename).name
        if not nombre:
            return None

        extension = Path(nombre).suffix.lstrip('.').lower() or self.EXTENSION_DESCONOCIDA

        if extension in self.EXTENSIONES_ZIP_ANIDADO:
            logger.info(
                f"Archivo comprimido anidado ignorado en '{nombre_zip}': {nombre}"
            )
            return None

        datos = zf.read(info.filename)
        if not datos:
            logger.warning(f"Archivo vacio en ZIP '{nombre_zip}': {nombre}")
            return None

        logger.info(
            f"Archivo extraido de ZIP '{nombre_zip}': {nombre} ({len(datos)} bytes)"
        )

        return AdjuntoExtraido(
            nombre=nombre,
            contenido=datos,
            extension=extension
        )
