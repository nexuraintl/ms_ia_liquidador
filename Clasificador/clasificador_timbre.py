"""
CLASIFICADOR IMPUESTO AL TIMBRE
================================

Modulo para analizar documentos y determinar si aplica el Impuesto al Timbre
usando Google Gemini.

Responsabilidad (SRP): Solo analisis de timbre mediante IA
Reutiliza funciones del ProcesadorGemini existente
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
from fastapi import UploadFile

# Utilidades compartidas (NUEVO v3.0)
from utils.utils_archivos import obtener_nombre_archivo

from .clasificador import ProcesadorGemini
from prompts.prompt_timbre import (
    PROMPT_ANALISIS_TIMBRE_OBSERVACIONES,
    PROMPT_EXTRACCION_CONTRATO_TIMBRE
)

logger = logging.getLogger(__name__)


class ClasificadorTimbre:
    """
    Clasificador especializado para Impuesto al Timbre.

    Responsabilidad (SRP): Solo analisis de timbre con Gemini
    Dependencia (DIP): Usa ProcesadorGemini como dependencia
    """

    def __init__(self, procesador_gemini: ProcesadorGemini):
        """
        Inicializa el clasificador con dependencia inyectada.

        Args:
            procesador_gemini: Instancia de ProcesadorGemini para reutilizar funciones
        """
        self.procesador = procesador_gemini
        logger.info("ClasificadorTimbre inicializado con ProcesadorGemini")

    async def analizar_observaciones_timbre(self, observaciones: str) -> Dict[str, Any]:
        """
        Analiza el campo observaciones de PGD para determinar si aplica timbre.

        Primera llamada a Gemini (paralela con otros impuestos).

        Args:
            observaciones: Campo observaciones del endpoint de PGD

        Returns:
            Dict con:
                - aplica_timbre: bool
                - base_gravable_obs: float
                - observaciones_analisis: str (observaciones tecnicas)
        """
        logger.info("Analizando observaciones para Impuesto al Timbre...")

        try:
            # Generar prompt
            prompt = PROMPT_ANALISIS_TIMBRE_OBSERVACIONES(observaciones)

            # Llamar a Gemini reutilizando funcion del procesador
            respuesta = await self.procesador._llamar_gemini(prompt, usar_modelo_consorcio=False)

            # Extraer JSON de la respuesta
            resultado_json = self._extraer_json_respuesta(respuesta)

            # Validar estructura
            if not isinstance(resultado_json, dict):
                raise ValueError("La respuesta no es un diccionario valido")

            # Validar campos requeridos
            if "aplica_timbre" not in resultado_json or "base_gravable_obs" not in resultado_json:
                raise ValueError("Faltan campos requeridos en la respuesta: aplica_timbre, base_gravable_obs")

            # Guardar JSON de respuesta para monitoreo
            self._guardar_json_gemini(resultado_json, "timbre_observaciones")

            # Preparar resultado
            resultado = {
                "aplica_timbre": bool(resultado_json.get("aplica_timbre", False)),
                "base_gravable_obs": float(resultado_json.get("base_gravable_obs", 0.0)),
                "observaciones_analisis": f"IA analizo observaciones - aplica_timbre: {resultado_json.get('aplica_timbre', False)}"
            }

            logger.info(f"Analisis de observaciones completado: aplica_timbre={resultado['aplica_timbre']}, base_obs={resultado['base_gravable_obs']}")

            return resultado

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de observaciones timbre: {e}")
            logger.error(f"Respuesta problematica: {respuesta}")
            raise ValueError(f"Error parseando respuesta de IA para observaciones timbre: {str(e)}")
        except Exception as e:
            logger.error(f"Error en analisis de observaciones timbre: {e}")
            raise ValueError(f"Error analizando observaciones timbre: {str(e)}")

    async def extraer_datos_contrato(
        self,
        documentos_clasificados: Dict[str, Dict],
        archivos_directos: List[UploadFile] = None,
        cache_archivos: Dict[str, bytes] = None
    ) -> Dict[str, Any]:
        """
        Extrae datos del contrato necesarios para calcular timbre.

        Segunda llamada a Gemini (secuencial, despues de validar aplica_timbre).

        Args:
            documentos_clasificados: Diccionario con documentos clasificados
            archivos_directos: Lista de archivos UploadFile
            cache_archivos: Cache de archivos en bytes

        Returns:
            Dict con:
                - id_contrato: str
                - fecha_suscripcion: str (formato YYYY-MM-DD)
                - valor_inicial_contrato: float
                - valor_total_contrato: float
                - adiciones: List[Dict] con valor_adicion y fecha_adicion
                - observaciones_extraccion: str
        """
        logger.info("Extrayendo datos del contrato para Impuesto al Timbre...")

        try:
            # Extraer textos de documentos
            factura_texto = documentos_clasificados.get("FACTURA", {}).get("texto", "")
            rut_texto = documentos_clasificados.get("RUT", {}).get("texto", "")
            anexos_texto = documentos_clasificados.get("ANEXO", {}).get("texto", "")
            cotizacion_texto = documentos_clasificados.get("COTIZACION", {}).get("texto", "")
            otros_texto = documentos_clasificados.get("OTRO", {}).get("texto", "")

            # USAR CACHE SI ESTÁ DISPONIBLE (para workers paralelos)
            if cache_archivos:
                logger.info(f"Usando cache de archivos para extracción timbre (workers paralelos): {len(cache_archivos)} archivos")
                archivos_directos = self.procesador._obtener_archivos_clonados_desde_cache(cache_archivos)
                total_archivos_directos = len(archivos_directos)
            else:
                total_archivos_directos = len(archivos_directos) if archivos_directos else 0
                logger.info(f"Usando archivos directos originales (sin cache): {total_archivos_directos} archivos")

            total_textos_preprocesados = len(documentos_clasificados)

            if total_archivos_directos > 0:
                logger.info(f"Extracción timbre HÍBRIDO: {total_archivos_directos} directos + {total_textos_preprocesados} preprocesados")
            else:
                logger.info(f"Extracción timbre TRADICIONAL: {total_textos_preprocesados} textos preprocesados")

            # Obtener nombres de archivos directos para el prompt (NUEVO v3.0: soporta Files API)
            nombres_archivos = []
            if archivos_directos:
                nombres_archivos = [obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]

            # Generar prompt
            prompt = PROMPT_EXTRACCION_CONTRATO_TIMBRE(
                factura_texto=factura_texto,
                rut_texto=rut_texto,
                anexos_texto=anexos_texto,
                cotizacion_texto=cotizacion_texto,
                otros_texto=otros_texto,
                nombres_archivos_directos=nombres_archivos
            )

            # Llamar a Gemini en modo hibrido si hay archivos directos
            if archivos_directos and len(archivos_directos) > 0:
                logger.info(f"Llamando a Gemini en modo HÍBRIDO con {len(archivos_directos)} archivos directos")
                respuesta = await self.procesador._llamar_gemini_hibrido_factura(prompt, archivos_directos)
            else:
                logger.info("Llamando a Gemini en modo TEXTO (sin archivos directos)")
                respuesta = await self.procesador._llamar_gemini(prompt, usar_modelo_consorcio=False)

            # Extraer JSON de la respuesta
            resultado_json = self._extraer_json_respuesta(respuesta)

            # Validar estructura
            if not isinstance(resultado_json, dict):
                raise ValueError("La respuesta no es un diccionario valido")

            # Validar campos requeridos
            campos_requeridos = ["id_contrato", "fecha_suscripcion", "valor_inicial_contrato", "valor_total_contrato", "adiciones"]
            for campo in campos_requeridos:
                if campo not in resultado_json:
                    raise ValueError(f"Falta campo requerido en la respuesta: {campo}")

            # Guardar JSON de respuesta para monitoreo
            self._guardar_json_gemini(resultado_json, "timbre_extraccion_contrato")

            # Preparar resultado con valores por defecto seguros
            resultado = {
                "id_contrato": str(resultado_json.get("id_contrato", "")),
                "fecha_suscripcion": str(resultado_json.get("fecha_suscripcion", "0000-00-00")),
                "valor_inicial_contrato": float(resultado_json.get("valor_inicial_contrato", 0.0)),
                "valor_factura_sin_iva": float(resultado_json.get("valor_factura_sin_iva", 0.0)),
                "valor_total_contrato": float(resultado_json.get("valor_total_contrato", 0.0)),
                "adiciones": self._validar_adiciones(resultado_json.get("adiciones", [])),
                "observaciones_extraccion": f" IA extrajo datos del contrato - ID: {resultado_json.get('id_contrato', 'NO_ENCONTRADO')}"
            }

            logger.info(f"Extraccion completada: ID={resultado['id_contrato']}, Fecha={resultado['fecha_suscripcion']}, Adiciones={len(resultado['adiciones'])}")

            return resultado

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de extraccion contrato: {e}")
            logger.error(f"Respuesta problematica: {respuesta}")
            raise ValueError(f"Error parseando respuesta de IA para extraccion contrato: {str(e)}")
        except Exception as e:
            logger.error(f"Error en extraccion de datos del contrato: {e}")
            raise ValueError(f"Error extrayendo datos del contrato: {str(e)}")

    def _validar_adiciones(self, adiciones_raw: List) -> List[Dict[str, Any]]:
        """
        Valida y normaliza la lista de adiciones.

        Args:
            adiciones_raw: Lista de adiciones sin validar

        Returns:
            Lista de adiciones validadas con estructura correcta
        """
        adiciones_validadas = []

        if not isinstance(adiciones_raw, list):
            logger.warning(f"Adiciones no es una lista, devolviendo lista vacia")
            return []

        for idx, adicion in enumerate(adiciones_raw):
            if not isinstance(adicion, dict):
                logger.warning(f"Adicion {idx} no es un diccionario, omitiendo")
                continue

            # Validar y normalizar adicion
            adicion_validada = {
                "valor_adicion": float(adicion.get("valor_adicion", 0.0)),
                "fecha_adicion": str(adicion.get("fecha_adicion", "0000-00-00"))
            }

            adiciones_validadas.append(adicion_validada)

        logger.info(f"Validadas {len(adiciones_validadas)} adiciones de {len(adiciones_raw)} originales")
        return adiciones_validadas

    def _extraer_json_respuesta(self, respuesta: str) -> Dict[str, Any]:
        """
        Extrae JSON de la respuesta de Gemini, manejando bloques de codigo.

        Reutiliza logica del procesador original.

        Args:
            respuesta: Respuesta cruda de Gemini

        Returns:
            Dict parseado desde JSON
        """
        respuesta_limpia = respuesta.strip()

        # Intentar extraer JSON de bloque de codigo
        if "```json" in respuesta_limpia:
            inicio = respuesta_limpia.find("```json") + 7
            fin = respuesta_limpia.find("```", inicio)
            if fin != -1:
                respuesta_limpia = respuesta_limpia[inicio:fin].strip()
        elif "```" in respuesta_limpia:
            inicio = respuesta_limpia.find("```") + 3
            fin = respuesta_limpia.find("```", inicio)
            if fin != -1:
                respuesta_limpia = respuesta_limpia[inicio:fin].strip()

        # Parsear JSON
        try:
            resultado = json.loads(respuesta_limpia)
            return resultado
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON: {e}")
            logger.error(f"Respuesta limpia: {respuesta_limpia[:500]}...")
            raise

    def _guardar_json_gemini(self, datos: Dict[str, Any], tipo_analisis: str) -> None:
        """
        Guarda el JSON de respuesta de Gemini en la carpeta Results para monitoreo.

        Args:
            datos: Datos JSON a guardar
            tipo_analisis: Tipo de analisis (timbre_observaciones o timbre_extraccion_contrato)
        """
        try:
            # Crear estructura de carpetas con fecha
            fecha_actual = datetime.now()
            carpeta_fecha = fecha_actual.strftime("%Y-%m-%d")
            timestamp = fecha_actual.strftime("%H-%M-%S")

            # Ruta base
            ruta_base = Path("Results") / carpeta_fecha
            ruta_base.mkdir(parents=True, exist_ok=True)

            # Nombre del archivo
            nombre_archivo = f"{tipo_analisis}_{timestamp}.json"
            ruta_archivo = ruta_base / nombre_archivo

            # Guardar JSON con formato legible
            with open(ruta_archivo, 'w', encoding='utf-8') as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)

            logger.info(f"JSON de Gemini guardado en: {ruta_archivo}")

        except Exception as e:
            logger.warning(f"No se pudo guardar JSON de Gemini para monitoreo: {e}")
            # No lanzar excepcion, solo advertencia
