"""
Módulo de extracción híbrida de archivos.
Combina procesamiento multimodal (directo a Gemini) con preprocesamiento local.
"""
import logging
from dataclasses import dataclass
from typing import List, Dict
from fastapi import UploadFile
from Extraccion import ProcesadorArchivos, preprocesar_excel_limpio
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

    def __init__(self):
        """Inicializa el extractor con procesadores necesarios"""
        self.extractor = ProcesadorArchivos()
        self.validador = ValidadorArchivos()

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

        # Procesar archivos locales
        textos_archivos_original = await self._procesar_archivos_locales(archivos_preprocesamiento)

        # Preprocesamiento adicional para Excel
        textos_preprocesados = await self._preprocesar_excel(
            textos_archivos_original,
            archivos_preprocesamiento
        )

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
                        texto_preprocesado = preprocesar_excel_limpio(
                            contenido_binario,
                            nombre_archivo
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
