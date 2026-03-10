"""
EXTRACTOR DE ADJUNTOS EMBEBIDOS
================================

SRP: Responsabilidad unica - extraer archivos adjuntos binarios de emails .msg y .eml.
OCP: Extensible para nuevos tipos de contenedores de email.

No realiza procesamiento del contenido: solo extrae bytes y metadata.
El procesamiento posterior (upload a Files API, preprocesamiento Excel, etc.)
es responsabilidad de quien consuma esta clase.
"""
import email
import logging
import tempfile
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class AdjuntoExtraido:
    """Representa un archivo adjunto extraido de un email."""
    nombre: str
    contenido: bytes
    extension: str  # sin punto, en minusculas: 'pdf', 'xlsx', 'jpg', etc.


class ExtractorAdjuntos:
    """
    Extrae adjuntos binarios de emails .msg y .eml.

    Responsabilidades (SRP):
    - Extraer bytes de adjuntos embebidos en .msg via extract_msg
    - Extraer bytes de adjuntos embebidos en .eml via stdlib email
    - Normalizar nombre y extension de cada adjunto

    NO responsable de:
    - Subir PDFs a Files API
    - Preprocesar Excel
    - Extraer texto de adjuntos
    """

    EXTENSION_DESCONOCIDA = "bin"

    def extraer_de_msg(self, contenido: bytes, nombre_msg: str) -> List[AdjuntoExtraido]:
        """
        Extrae adjuntos de un archivo .msg.

        Args:
            contenido: Bytes del archivo .msg
            nombre_msg: Nombre del .msg para logging

        Returns:
            Lista de AdjuntoExtraido con nombre, bytes y extension
        """
        try:
            import extract_msg
        except ImportError:
            logger.warning("extract-msg no disponible, no se pueden extraer adjuntos de .msg")
            return []

        adjuntos: List[AdjuntoExtraido] = []
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(suffix='.msg', delete=False) as temp_file:
                temp_file.write(contenido)
                temp_path = temp_file.name

            msg = extract_msg.Message(temp_path)

            if not hasattr(msg, 'attachments') or not msg.attachments:
                logger.info(f"MSG sin adjuntos: {nombre_msg}")
                return []

            for attachment in msg.attachments:
                try:
                    adjunto = self._extraer_adjunto_msg(attachment)
                    if adjunto:
                        adjuntos.append(adjunto)
                        logger.info(f"Adjunto extraido de MSG '{nombre_msg}': {adjunto.nombre} ({len(adjunto.contenido)} bytes)")
                except Exception as e:
                    logger.warning(f"Error extrayendo adjunto de MSG '{nombre_msg}': {e}")

        except Exception as e:
            logger.error(f"Error procesando MSG para extraccion de adjuntos '{nombre_msg}': {e}")
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

        logger.info(f"MSG '{nombre_msg}': {len(adjuntos)} adjunto(s) extraido(s)")
        return adjuntos

    def extraer_de_eml(self, contenido: bytes, nombre_eml: str) -> List[AdjuntoExtraido]:
        """
        Extrae adjuntos de un archivo .eml.

        Args:
            contenido: Bytes del archivo .eml
            nombre_eml: Nombre del .eml para logging

        Returns:
            Lista de AdjuntoExtraido con nombre, bytes y extension
        """
        adjuntos: List[AdjuntoExtraido] = []

        try:
            msg = email.message_from_bytes(contenido)

            for part in msg.walk():
                content_disposition = part.get('Content-Disposition', '')
                if not content_disposition or 'attachment' not in content_disposition:
                    continue

                try:
                    adjunto = self._extraer_adjunto_eml(part)
                    if adjunto:
                        adjuntos.append(adjunto)
                        logger.info(f"Adjunto extraido de EML '{nombre_eml}': {adjunto.nombre} ({len(adjunto.contenido)} bytes)")
                except Exception as e:
                    logger.warning(f"Error extrayendo adjunto de EML '{nombre_eml}': {e}")

        except Exception as e:
            logger.error(f"Error procesando EML para extraccion de adjuntos '{nombre_eml}': {e}")

        logger.info(f"EML '{nombre_eml}': {len(adjuntos)} adjunto(s) extraido(s)")
        return adjuntos

    def _extraer_adjunto_msg(self, attachment) -> AdjuntoExtraido | None:
        """
        Extrae un adjunto individual de un objeto attachment de extract_msg.
        """
        nombre = (
            getattr(attachment, 'longFilename', None)
            or getattr(attachment, 'shortFilename', None)
            or 'adjunto_sin_nombre'
        )
        nombre = nombre.strip()

        datos = getattr(attachment, 'data', None)
        if not datos:
            logger.warning(f"Adjunto MSG sin datos: {nombre}")
            return None

        extension = Path(nombre).suffix.lstrip('.').lower() or self.EXTENSION_DESCONOCIDA

        return AdjuntoExtraido(
            nombre=nombre,
            contenido=datos,
            extension=extension
        )

    def _extraer_adjunto_eml(self, part) -> AdjuntoExtraido | None:
        """
        Extrae un adjunto individual de una parte de email EML.
        """
        nombre_raw = part.get_filename()
        if not nombre_raw:
            nombre = 'adjunto_sin_nombre'
        else:
            # Decodificar header si esta codificado (RFC 2047)
            decoded_parts = email.header.decode_header(nombre_raw)
            nombre_parts = []
            for fragment, charset in decoded_parts:
                if isinstance(fragment, bytes):
                    nombre_parts.append(fragment.decode(charset or 'utf-8', errors='replace'))
                else:
                    nombre_parts.append(fragment)
            nombre = ''.join(nombre_parts).strip()

        datos = part.get_payload(decode=True)
        if not datos:
            logger.warning(f"Adjunto EML sin datos: {nombre}")
            return None

        extension = Path(nombre).suffix.lstrip('.').lower() or self.EXTENSION_DESCONOCIDA

        return AdjuntoExtraido(
            nombre=nombre,
            contenido=datos,
            extension=extension
        )
