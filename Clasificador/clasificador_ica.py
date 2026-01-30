"""
CLASIFICADOR ICA (INDUSTRIA Y COMERCIO)
=======================================

Módulo para analizar facturas y determinar retención de ICA según ubicaciones
y actividades económicas. Combina análisis de IA (Gemini) con validaciones
manuales exhaustivas en Python.

ARQUITECTURA SEPARADA (v3.0):
- Gemini: SOLO identifica datos (ubicaciones, actividades)
- Python: TODAS las validaciones según normativa

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo análisis de ICA
- DIP: Depende de abstracciones (database_manager, gemini_model)
- OCP: Abierto para extensión (nuevas validaciones)
- LSP: Puede sustituirse por otras implementaciones

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture + Validaciones Manuales
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

# Utilidades compartidas (NUEVO v3.0)
from utils.utils_archivos import obtener_nombre_archivo, procesar_archivos_para_gemini

# Importar prompts especializados
from prompts.prompt_ica import (
    crear_prompt_identificacion_ubicaciones,
    crear_prompt_relacionar_actividades,
    limpiar_json_gemini,
    validar_estructura_ubicaciones,
    validar_estructura_actividades
)

# Configuración de logging
logger = logging.getLogger(__name__)


class ClasificadorICA:
    """
    Clasificador especializado para retención de ICA.

    RESPONSABILIDADES (SRP):
    - Obtener ubicaciones de la base de datos
    - Coordinar análisis de Gemini (2 llamadas)
    - Aplicar validaciones manuales según normativa
    - Generar resultado estructurado para el liquidador

    DEPENDENCIAS (DIP):
    - database_manager: Para consultas a tablas ICA
    - procesador_gemini: ProcesadorGemini completo para análisis con IA
    """

    def __init__(self, database_manager: Any, procesador_gemini: Any):
        """
        Inicializa el clasificador ICA con inyección de dependencias.

        Args:
            database_manager: Gestor de base de datos (abstracción)
            procesador_gemini: ProcesadorGemini completo para análisis
        """
        self.database_manager = database_manager
        self.procesador_gemini = procesador_gemini
        logger.info("ClasificadorICA inicializado siguiendo principios SOLID")

    def _guardar_respuesta_gemini(
        self,
        respuesta_texto: str,
        data_parseada: Dict[str, Any],
        tipo_llamada: str,
        nit_administrativo: str = None
    ) -> None:
        """
        Guarda las respuestas de Gemini en archivos JSON para trazabilidad.

        RESPONSABILIDAD (SRP):
        - Solo guarda respuestas en formato JSON
        - Crea estructura de carpetas si no existe
        - Genera nombres de archivo con timestamp

        Args:
            respuesta_texto: Respuesta cruda de Gemini
            data_parseada: JSON parseado y limpio
            tipo_llamada: "ubicaciones" o "actividades"
            nit_administrativo: NIT para organizar archivos (opcional)
        """
        try:
            # Crear carpeta para respuestas ICA
            fecha_actual = datetime.now()
            carpeta_fecha = fecha_actual.strftime("%Y-%m-%d")
            carpeta_base = Path("Results") / carpeta_fecha / "ICA_Respuestas_Gemini"
            
            if nit_administrativo:
                carpeta_base = carpeta_base / nit_administrativo
            
            carpeta_base.mkdir(parents=True, exist_ok=True)

            # Generar nombre de archivo con timestamp
            timestamp = fecha_actual.strftime("%H-%M-%S-%f")[:-3]  # Milisegundos
            nombre_base = f"ica_{tipo_llamada}_{timestamp}"

            # Guardar respuesta cruda
            archivo_crudo = carpeta_base / f"{nombre_base}_raw.txt"
            with open(archivo_crudo, 'w', encoding='utf-8') as f:
                f.write(respuesta_texto)

            # Guardar JSON parseado
            archivo_json = carpeta_base / f"{nombre_base}_parsed.json"
            with open(archivo_json, 'w', encoding='utf-8') as f:
                json.dump(data_parseada, f, ensure_ascii=False, indent=2)

            logger.info(f" Respuesta Gemini guardada: {tipo_llamada} → {archivo_json.name}")

        except Exception as e:
            logger.error(f" Error guardando respuesta Gemini ({tipo_llamada}): {e}")
            # No fallar el proceso si no se puede guardar el archivo

    async def analizar_ica(
        self,
        nit_administrativo: str,
        textos_documentos: Dict[str, str],
        estructura_contable: int,
        cache_archivos: Optional[Dict[str, bytes]] = None
    ) -> Dict[str, Any]:
        """
        Analiza una factura para determinar retención de ICA.

        FLUJO COMPLETO (SRP - Coordinación):
        1. Validar que el NIT aplica para ICA
        2. Obtener ubicaciones de la base de datos
        3. Primera llamada Gemini: identificar ubicaciones de la actividad (MULTIMODAL)
        4. Validaciones manuales de ubicaciones (Python)
        5. Consultar actividades por ubicación en la BD
        6. Segunda llamada Gemini: relacionar actividades (MULTIMODAL)
        7. Validaciones manuales de actividades (Python)
        8. Retornar resultado estructurado

        Args:
            nit_administrativo: NIT de la entidad administrativa
            textos_documentos: Diccionario con textos de documentos
            cache_archivos: Cache de archivos para procesamiento híbrido multimodal

        Returns:
            Dict con resultado completo del análisis ICA
        """
        logger.info(f"Iniciando análisis ICA para NIT: {nit_administrativo}")

        # MANEJO HÍBRIDO MULTIMODAL: Obtener archivos desde cache
        archivos_directos = []
        if cache_archivos:
            logger.info(f"ICA usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self.procesador_gemini._obtener_archivos_clonados_desde_cache(cache_archivos)
        else:
            logger.info("ICA sin archivos directos")

        resultado_base = {
            "aplica": False,
            "estado": "no_aplica_impuesto",
            "valor_total_ica": 0.0,
            "actividades_facturadas": [],
            "actividades_relacionadas": [],  # NUEVO FORMATO v3.0
            "valor_factura_sin_iva": 0.0,  # NUEVO FORMATO v3.0
            "observaciones": [],
            "fecha_analisis": datetime.now().isoformat()
        }

        try:
            # PASO 1: Validar NIT aplica ICA
            from config import nit_aplica_ICA

            if not nit_aplica_ICA(nit_administrativo):
                resultado_base["observaciones"].append(
                    f"El NIT administrado {nit_administrativo} no aplica ICA"
                )
                logger.warning(f"NIT {nit_administrativo} no aplica ICA")
                return resultado_base

            logger.info("NIT aplica ICA - continuando análisis")

            # PASO 2: Obtener ubicaciones de la BD
            ubicaciones_bd = self._obtener_ubicaciones_bd()
            if not ubicaciones_bd:
                resultado_base["estado"] = "preliquidacion_sin_finalizar"
                resultado_base["observaciones"].append(
                    "No se pudieron obtener ubicaciones de la base de datos"
                )
                logger.error("Error obteniendo ubicaciones de BD")
                return resultado_base

            logger.info(f"Ubicaciones obtenidas de BD: {len(ubicaciones_bd)}")

            # PASO 3: Primera llamada Gemini - Identificar ubicaciones (MULTIMODAL)
            ubicaciones_identificadas = await self._identificar_ubicaciones_gemini(
                ubicaciones_bd, textos_documentos, archivos_directos, nit_administrativo
            )

            if not ubicaciones_identificadas:
                resultado_base["estado"] = "preliquidacion_sin_finalizar"
                resultado_base["observaciones"].append(
                    "No se pudo identificar el municipio de la actividad gravada"
                )
                logger.error("Gemini no identificó ubicaciones")
                return resultado_base

            logger.info(f"Ubicaciones identificadas por Gemini: {len(ubicaciones_identificadas)}")

            # PASO 4: Validaciones manuales de ubicaciones (Python)
            validacion_ubicaciones = self._validar_ubicaciones_manualmente(
                ubicaciones_identificadas
            )

            if not validacion_ubicaciones["valido"]:
                resultado_base["estado"] = "preliquidacion_sin_finalizar"
                resultado_base["observaciones"].extend(validacion_ubicaciones["errores"])
                logger.warning(f"Validación de ubicaciones falló: {validacion_ubicaciones['errores']}")
                return resultado_base

            # Agregar observaciones no críticas
            if validacion_ubicaciones["advertencias"]:
                resultado_base["observaciones"].extend(validacion_ubicaciones["advertencias"])

            logger.info("Validaciones de ubicaciones exitosas")

            # PASO 5: Consultar actividades por ubicación en BD
            actividades_bd_por_ubicacion = self._obtener_actividades_por_ubicacion(
                ubicaciones_identificadas, estructura_contable
            )

            if not actividades_bd_por_ubicacion:
                resultado_base["estado"] = "preliquidacion_sin_finalizar"
                resultado_base["observaciones"].append(
                    "No se pudieron obtener actividades de la base de datos"
                )
                logger.error("Error obteniendo actividades de BD")
                return resultado_base

            logger.info(f"Actividades obtenidas para {len(actividades_bd_por_ubicacion)} ubicaciones")

            # PASO 6: Segunda llamada Gemini - Relacionar actividades (MULTIMODAL - NUEVO FORMATO v3.0)
            datos_actividades = await self._relacionar_actividades_gemini(
                ubicaciones_identificadas,
                actividades_bd_por_ubicacion,
                textos_documentos,
                archivos_directos,
                nit_administrativo
            )

            if not datos_actividades:
                resultado_base["estado"] = "preliquidacion_sin_finalizar"
                resultado_base["observaciones"].append(
                    "No se pudo identificar la actividad económica facturada"
                )
                logger.warning("Gemini no retornó datos de actividades")
                return resultado_base

            # Extraer datos del nuevo formato
            actividades_facturadas = datos_actividades.get("actividades_facturadas", [])
            actividades_relacionadas = datos_actividades.get("actividades_relacionadas", [])
            valor_factura_sin_iva = datos_actividades.get("valor_factura_sin_iva", 0.0)
            autorretenedor_ica = datos_actividades.get("autorretenedor_ica", False)

            logger.info(f"Actividades facturadas: {len(actividades_facturadas)}, Actividades relacionadas: {len(actividades_relacionadas)}")

            # PASO 7: Validaciones manuales de actividades (Python - NUEVO FORMATO v3.0)
            validacion_actividades = self._validar_actividades_manualmente(
                actividades_facturadas,
                actividades_relacionadas,
                valor_factura_sin_iva,
                ubicaciones_identificadas
            )

            if not validacion_actividades["valido"]:
                # Determinar estado según el tipo de error
                if validacion_actividades.get("todas_no_aplican", False):
                    resultado_base["estado"] = "no_aplica_impuesto"
                else:
                    resultado_base["estado"] = "preliquidacion_sin_finalizar"

                # Preservar estructura completa con datos extraídos
                resultado_base["actividades_facturadas"] = actividades_facturadas
                resultado_base["actividades_relacionadas"] = actividades_relacionadas
                resultado_base["valor_factura_sin_iva"] = valor_factura_sin_iva
                resultado_base["autorretenedor_ica"] = autorretenedor_ica   
                resultado_base["observaciones"].extend(validacion_actividades["errores"])
                resultado_base["observaciones"].extend(validacion_actividades.get("advertencias", []))
                logger.warning(f"Validación de actividades falló: {validacion_actividades['errores']}")
                return resultado_base

            # Agregar observaciones no críticas de actividades
            if validacion_actividades.get("advertencias"):
                resultado_base["observaciones"].extend(validacion_actividades["advertencias"])

            logger.info("Validaciones de actividades exitosas - pasando a liquidador")

            # PASO 8: Preparar datos validados para liquidador (NUEVO FORMATO v3.0)
            resultado_base["aplica"] = True
            resultado_base["estado"] = "Validado - Listo para liquidación"
            resultado_base["ubicaciones_identificadas"] = ubicaciones_identificadas
            resultado_base["actividades_facturadas"] = actividades_facturadas
            resultado_base["actividades_relacionadas"] = actividades_relacionadas
            resultado_base["valor_factura_sin_iva"] = valor_factura_sin_iva
            resultado_base["autorretenedor_ica"] = autorretenedor_ica
            
            logger.info(f"autorretenedor detectado: {autorretenedor_ica} ")

            # Aquí el liquidador se encargará del cálculo
            logger.info("Análisis ICA completado exitosamente")
            return resultado_base

        except Exception as e:
            logger.error(f"Error en análisis ICA: {e}")
            resultado_base["estado"] = "preliquidacion_sin_finalizar"
            resultado_base["observaciones"].append(f"Error en análisis: {str(e)}")
            return resultado_base

    def _obtener_ubicaciones_bd(self) -> List[Dict[str, Any]]:
        """
        Obtiene todas las ubicaciones de la tabla UBICACIONES ICA.

        RESPONSABILIDAD (SRP):
        - Solo obtiene ubicaciones de la base de datos
        - No valida ni procesa datos

        Returns:
            List[Dict]: Lista de ubicaciones con codigo y nombre
        """
        logger.info("Consultando tabla UBICACIONES ICA...")

        try:
            # Usar método abstracto de la interfaz DatabaseInterface
            resultado = self.database_manager.obtener_ubicaciones_ica()

            if not resultado['success']:
                logger.warning(f"No se encontraron ubicaciones en la BD: {resultado['message']}")
                return []

            ubicaciones = resultado['data']
            logger.info(f"Ubicaciones obtenidas exitosamente: {len(ubicaciones)}")
            return ubicaciones

        except Exception as e:
            logger.error(f"Error consultando UBICACIONES ICA: {e}")
            return []

    async def _procesar_archivos_para_gemini(self, archivos_directos: List[Any]) -> List[Any]:
        """
        Procesa archivos para convertirlos al formato esperado por Gemini (NUEVO SDK v3.0).

        DELEGACIÓN: Usa función compartida para evitar duplicación de código.

        Args:
            archivos_directos: Lista de archivos (File de Google, UploadFile, bytes o dict)

        Returns:
            List[types.Part]: Archivos en formato Gemini SDK v3.0
        """
        return await procesar_archivos_para_gemini(archivos_directos)

    async def _identificar_ubicaciones_gemini(
        self,
        ubicaciones_bd: List[Dict[str, Any]],
        textos_documentos: Dict[str, str],
        archivos_directos: List[Any],
        nit_administrativo: str = None
    ) -> List[Dict[str, Any]]:
        """
        Primera llamada a Gemini para identificar ubicaciones de la actividad (MULTIMODAL).

        RESPONSABILIDAD (SRP):
        - Solo coordina la llamada a Gemini
        - No valida resultados (eso lo hace _validar_ubicaciones_manualmente)

        PROCESAMIENTO HÍBRIDO:
        - Textos extraídos (Excel, Word) se incluyen en el prompt
        - Archivos directos (PDF, imágenes) se envían a Gemini para análisis multimodal

        Args:
            ubicaciones_bd: Ubicaciones de la base de datos
            textos_documentos: Textos de documentos preprocesados
            archivos_directos: Archivos clonados desde cache para procesamiento multimodal
            nit_administrativo: NIT para organizar archivos guardados (opcional)

        Returns:
            List[Dict]: Ubicaciones identificadas por Gemini
        """
        logger.info("Primera llamada Gemini: identificando ubicaciones (MULTIMODAL)...")

        try:
            # Preparar nombres de archivos directos para el prompt (NUEVO v3.0: usa función compartida)
            archivos_directos = archivos_directos or []
            nombres_archivos_directos = [obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]

            # Crear prompt con información de archivos directos
            prompt = crear_prompt_identificacion_ubicaciones(
                ubicaciones_bd=ubicaciones_bd,
                textos_documentos=textos_documentos,
                nombres_archivos_directos=nombres_archivos_directos if archivos_directos else None
            )

            # Preparar contenido para Gemini (MULTIMODAL)
            contenido_gemini = [prompt]

            # Agregar archivos directos para análisis multimodal
            if archivos_directos:
                # CORRECCIÓN: Procesar archivos al formato esperado por Gemini
                archivos_procesados = await self._procesar_archivos_para_gemini(archivos_directos)
                contenido_gemini.extend(archivos_procesados)
                logger.info(f"📎 ICA - Enviando {len(archivos_procesados)} archivos procesados a Gemini para identificar ubicaciones")

            # Llamar a Gemini con contexto completo (timeout 60 segundos) - NUEVO SDK v3.0
            loop = asyncio.get_event_loop()
            respuesta = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.procesador_gemini.client.models.generate_content(
                        model=self.procesador_gemini.model_name,
                        contents=contenido_gemini,
                        config=self.procesador_gemini.generation_config
                    )
                ),
                timeout=60.0
            )

            # Limpiar y parsear respuesta
            respuesta_texto = respuesta.text
            json_limpio = limpiar_json_gemini(respuesta_texto)
            data = json.loads(json_limpio)

            # 💾 GUARDAR RESPUESTA DE GEMINI (Primera llamada - ubicaciones)
            self._guardar_respuesta_gemini(
                respuesta_texto=respuesta_texto,
                data_parseada=data,
                tipo_llamada="ubicaciones",
                nit_administrativo=nit_administrativo
            )

            # Validar estructura
            if not validar_estructura_ubicaciones(data):
                logger.error("Estructura de JSON de ubicaciones inválida")
                return []

            ubicaciones = data.get("ubicaciones", [])
            logger.info(f"Gemini identificó {len(ubicaciones)} ubicaciones")
            return ubicaciones

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de Gemini (ubicaciones): {e}")
            return []
        except Exception as e:
            logger.error(f"Error en llamada a Gemini (ubicaciones): {e}")
            return []

    def _validar_ubicaciones_manualmente(
        self,
        ubicaciones_identificadas: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Valida manualmente las ubicaciones identificadas por Gemini.

        VALIDACIONES MANUALES (Python):
        1. Una ubicación sin nombre identificado
        2. Texto identificador vacío
        3. Código ubicación no encontrado en BD
        4. Múltiples ubicaciones sin porcentajes
        5. Suma de porcentajes != 100%

        Args:
            ubicaciones_identificadas: Ubicaciones de Gemini

        Returns:
            Dict con validación: {"valido": bool, "errores": List[str], "advertencias": List[str]}
        """
        logger.info("Aplicando validaciones manuales a ubicaciones...")

        errores = []
        advertencias = []

        # VALIDACIÓN 0: Debe haber al menos una ubicación
        if not ubicaciones_identificadas or len(ubicaciones_identificadas) == 0:
            errores.append("No se pudo identificar el municipio de la actividad gravada.")
            return {"valido": False, "errores": errores, "advertencias": advertencias}

        # Caso: Una sola ubicación
        if len(ubicaciones_identificadas) == 1:
            ubicacion = ubicaciones_identificadas[0]

            # VALIDACIÓN 1.1: Nombre ubicación vacío
            if not ubicacion.get("nombre_ubicacion") or ubicacion["nombre_ubicacion"].strip() == "":
                errores.append(
                    "No se pudo identificar el municipio de la actividad gravada."
                )
                return {"valido": False, "errores": errores, "advertencias": advertencias}

            # VALIDACIÓN 1.2: Asignar porcentaje 100% si no está asignado
            if ubicacion.get("porcentaje_ejecucion", 0.0) != 100.0:
                ubicacion["porcentaje_ejecucion"] = 100.0
                logger.info("Porcentaje asignado a 100% para única ubicación")

            # VALIDACIÓN 2: Texto identificador vacío
            if not ubicacion.get("texto_identificador") or ubicacion["texto_identificador"].strip() == "":
                errores.append(
                    "No se pudo identificar con certeza la ubicación de la actividad. "
                    "Por favor revisar la documentación manualmente"
                )
                return {"valido": False, "errores": errores, "advertencias": advertencias}

            # VALIDACIÓN 3: Código ubicación <= 0
            if ubicacion.get("codigo_ubicacion", 0) <= 0:
                advertencias.append(
                    f"La ubicación '{ubicacion['nombre_ubicacion']}' fue identificada "
                    "pero no está parametrizada en la base de datos"
                )
                errores.append(
                    f"La ubicación '{ubicacion['nombre_ubicacion']}' no está parametrizada "
                    "en la base de datos. Por favor agregar esta ubicación"
                )
                return {"valido": False, "errores": errores, "advertencias": advertencias}

            logger.info("Validaciones de ubicación única exitosas")
            return {"valido": True, "errores": [], "advertencias": advertencias}

        # Caso: Múltiples ubicaciones
        logger.info(f"Validando {len(ubicaciones_identificadas)} ubicaciones...")

        ubicaciones_sin_porcentaje = []
        ubicaciones_no_parametrizadas = []
        suma_porcentajes = 0.0

        for ubicacion in ubicaciones_identificadas:
            # VALIDACIÓN 1: Nombre ubicación vacío
            if not ubicacion.get("nombre_ubicacion") or ubicacion["nombre_ubicacion"].strip() == "":
                errores.append(
                    f"Una de las ubicaciones no tiene nombre identificado"
                )
                continue

            # VALIDACIÓN 2: Texto identificador vacío
            if not ubicacion.get("texto_identificador") or ubicacion["texto_identificador"].strip() == "":
                errores.append(
                    f"No se pudo identificar con certeza la ubicación '{ubicacion['nombre_ubicacion']}'. "
                    "Por favor revisar la documentación manualmente"
                )

            # VALIDACIÓN 3: Código ubicación <= 0
            if ubicacion.get("codigo_ubicacion", 0) <= 0:
                ubicaciones_no_parametrizadas.append(ubicacion['nombre_ubicacion'])
                advertencias.append(
                    f"La ubicación '{ubicacion['nombre_ubicacion']}' no está parametrizada en la base de datos"
                )

            # VALIDACIÓN 4: Porcentaje de ejecución
            porcentaje = ubicacion.get("porcentaje_ejecucion", 0.0)
            if porcentaje <= 0.0:
                ubicaciones_sin_porcentaje.append(ubicacion['nombre_ubicacion'])
            else:
                suma_porcentajes += porcentaje

        # VALIDACIÓN 4.1: Ubicaciones sin porcentaje
        if ubicaciones_sin_porcentaje:
            errores.append(
                f"No se identificó el porcentaje de ejecución para las ubicaciones: "
                f"{', '.join(ubicaciones_sin_porcentaje)}. "
                "Por favor revisar la documentación manualmente"
            )

        # VALIDACIÓN 4.2: Suma de porcentajes != 100%
        if abs(suma_porcentajes - 100.0) > 0.01:  # Tolerancia de 0.01%
            errores.append(
                f"Hay inconsistencia en la sumatoria de los porcentajes de participación "
                f"para cada ubicación (suma: {suma_porcentajes}%, esperado: 100%)"
            )

        # VALIDACIÓN 5: Ubicaciones no parametrizadas
        if ubicaciones_no_parametrizadas:
            errores.append(
                f"Las siguientes ubicaciones no están parametrizadas en la base de datos: "
                f"{', '.join(ubicaciones_no_parametrizadas)}"
            )

        # Determinar si las validaciones pasaron
        if errores:
            logger.warning(f"Validaciones de ubicaciones fallaron: {len(errores)} errores")
            return {"valido": False, "errores": errores, "advertencias": advertencias}

        logger.info("Validaciones de múltiples ubicaciones exitosas")
        return {"valido": True, "errores": [], "advertencias": advertencias}

    def _obtener_actividades_por_ubicacion(
        self,
        ubicaciones_identificadas: List[Dict[str, Any]],
        estructura_contable: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Obtiene actividades de la BD para cada ubicación identificada.

        RESPONSABILIDAD (SRP):
        - Solo obtiene actividades de la base de datos
        - No valida ni procesa datos

        Args:
            ubicaciones_identificadas: Ubicaciones validadas

        Returns:
            Dict: Actividades agrupadas por codigo_ubicacion
        """
        logger.info("Consultando actividades por ubicación...")

        actividades_por_ubicacion = {}

        try:
            for ubicacion in ubicaciones_identificadas:
                codigo_ubicacion = ubicacion.get("codigo_ubicacion")
                nombre_ubicacion = ubicacion.get("nombre_ubicacion")

                if codigo_ubicacion <= 0:
                    logger.warning(f"Saltando ubicación sin código: {nombre_ubicacion}")
                    continue

                # Usar método abstracto de la interfaz DatabaseInterface
                resultado = self.database_manager.obtener_actividades_ica(
                    codigo_ubicacion=codigo_ubicacion,
                    estructura_contable=estructura_contable
                )

                if not resultado['success']:
                    logger.warning(f"No se encontraron actividades para ubicación {codigo_ubicacion}: {resultado['message']}")
                    continue

                actividades = resultado['data']

                # Validar que el nombre de ubicación coincida
                if actividades and actividades[0]["nombre_ubicacion"] != nombre_ubicacion:
                    logger.error(
                        f"El nombre de ubicación de BD '{actividades[0]['nombre_ubicacion']}' "
                        f"no coincide con el identificado por Gemini '{nombre_ubicacion}'"
                    )
                    continue

                actividades_por_ubicacion[str(codigo_ubicacion)] = actividades
                logger.info(f"Actividades obtenidas para ubicación {codigo_ubicacion}: {len(actividades)}")

            return actividades_por_ubicacion

        except Exception as e:
            logger.error(f"Error consultando ACTIVIDADES IK: {e}")
            return {}

    async def _relacionar_actividades_gemini(
        self,
        ubicaciones_identificadas: List[Dict[str, Any]],
        actividades_bd_por_ubicacion: Dict[str, List[Dict[str, Any]]],
        textos_documentos: Dict[str, str],
        archivos_directos: List[Any] = None,
        nit_administrativo: str = None
    ) -> List[Dict[str, Any]]:
        """
        Segunda llamada a Gemini para relacionar actividades facturadas con BD (MULTIMODAL).

        RESPONSABILIDAD (SRP):
        - Solo coordina la llamada a Gemini
        - No valida resultados (eso lo hace _validar_actividades_manualmente)

        PROCESAMIENTO HÍBRIDO:
        - Textos extraídos (Excel, Word) se incluyen en el prompt
        - Archivos directos (PDF, imágenes) se envían a Gemini para análisis multimodal

        Args:
            ubicaciones_identificadas: Ubicaciones validadas
            actividades_bd_por_ubicacion: Actividades de BD por ubicación
            textos_documentos: Textos de documentos preprocesados
            archivos_directos: Archivos clonados desde cache para procesamiento multimodal (opcional)
            nit_administrativo: NIT para organizar archivos guardados (opcional)

        Returns:
            List[Dict]: Actividades facturadas relacionadas con BD
        """
        logger.info("Segunda llamada Gemini: relacionando actividades (MULTIMODAL)...")

        try:
            # Preparar nombres de archivos directos para el prompt (NUEVO v3.0: usa función compartida)
            archivos_directos = archivos_directos or []
            nombres_archivos_directos = [obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]

            # Crear prompt con información de archivos directos
            prompt = crear_prompt_relacionar_actividades(
                ubicaciones_identificadas=ubicaciones_identificadas,
                actividades_bd_por_ubicacion=actividades_bd_por_ubicacion,
                textos_documentos=textos_documentos,
                nombres_archivos_directos=nombres_archivos_directos if archivos_directos else None
            )

            # Preparar contenido para Gemini (MULTIMODAL)
            contenido_gemini = [prompt]

            # Agregar archivos directos para análisis multimodal
            if archivos_directos:
                # CORRECCIÓN: Procesar archivos al formato esperado por Gemini
                archivos_procesados = await self._procesar_archivos_para_gemini(archivos_directos)
                contenido_gemini.extend(archivos_procesados)
                logger.info(f" ICA - Enviando {len(archivos_procesados)} archivos procesados a Gemini para relacionar actividades")

            # Llamar a Gemini con contexto completo (timeout 60 segundos) - NUEVO SDK v3.0
            loop = asyncio.get_event_loop()
            respuesta = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.procesador_gemini.client.models.generate_content(
                        model=self.procesador_gemini.model_name,
                        contents=contenido_gemini,
                        config=self.procesador_gemini.generation_config
                    )
                ),
                timeout=60.0
            )

            # Limpiar y parsear respuesta
            respuesta_texto = respuesta.text
            json_limpio = limpiar_json_gemini(respuesta_texto)
            data = json.loads(json_limpio)

            #  GUARDAR RESPUESTA DE GEMINI (Segunda llamada - actividades)
            self._guardar_respuesta_gemini(
                respuesta_texto=respuesta_texto,
                data_parseada=data,
                tipo_llamada="actividades",
                nit_administrativo=nit_administrativo
            )

            # Validar estructura (NUEVO FORMATO v3.0)
            if not validar_estructura_actividades(data):
                logger.error("Estructura de JSON de actividades inválida")
                return {}

            # NUEVO FORMATO: Retornar el dict completo con actividades_facturadas, actividades_relacionadas y valor_factura_sin_iva
            actividades_facturadas = data.get("actividades_facturadas", [])
            actividades_relacionadas = data.get("actividades_relacionadas", [])
            valor_factura_sin_iva = data.get("valor_factura_sin_iva", 0.0)
            autorretenedor_ica = data.get("autorretenedor_ica", False)

            logger.info(f"Gemini identificó {len(actividades_facturadas)} actividades facturadas y {len(actividades_relacionadas)} actividades relacionadas")

            return {
                "actividades_facturadas": actividades_facturadas,
                "actividades_relacionadas": actividades_relacionadas,
                "valor_factura_sin_iva": valor_factura_sin_iva,
                "autorretenedor_ica": autorretenedor_ica
            }

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de Gemini (actividades): {e}")
            return {}
        except Exception as e:
            logger.error(f"Error en llamada a Gemini (actividades): {e}")
            return {}

    def _validar_actividades_manualmente(
        self,
        actividades_facturadas: List[str],
        actividades_relacionadas: List[Dict[str, Any]],
        valor_factura_sin_iva: float,
        ubicaciones_identificadas: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Valida manualmente las actividades identificadas por Gemini (NUEVO FORMATO v3.0).

        VALIDACIONES MANUALES (Python):
        1. actividades_facturadas no vacía
        2. valor_factura_sin_iva > 0
        3. nombre_act_rel no vacío (en cada actividad relacionada)
        4. codigo_actividad y codigo_ubicacion > 0
        5. codigos_ubicacion únicos (no puede haber múltiples actividades con mismo codigo_ubicacion)

        Args:
            actividades_facturadas: Lista simple de strings (actividades textuales de factura)
            actividades_relacionadas: Lista de actividades relacionadas con BD
            valor_factura_sin_iva: Valor de factura sin IVA
            ubicaciones_identificadas: Ubicaciones validadas

        Returns:
            Dict con validación: {"valido": bool, "errores": List[str], "advertencias": List[str]}
        """
        logger.info("Aplicando validaciones manuales a actividades (NUEVO FORMATO v3.0)...")

        errores = []
        advertencias = []

        # VALIDACIÓN 1: actividades_facturadas no vacía
        if not actividades_facturadas or len(actividades_facturadas) == 0:
            errores.append("No se pudo identificar las actividades economicas facturadas ")
            logger.warning("Validación 1 fallida: actividades_facturadas vacía")
            return {"valido": False, "errores": errores, "advertencias": advertencias}

        logger.info(f"Validación 1 exitosa: {len(actividades_facturadas)} actividades facturadas identificadas")

        # VALIDACIÓN 2: valor_factura_sin_iva > 0
        if valor_factura_sin_iva <= 0:
            errores.append("No se pudo identificar el valor de la factura sin IVA")
            logger.warning(f"Validación 2 fallida: valor_factura_sin_iva = {valor_factura_sin_iva}")
            return {"valido": False, "errores": errores, "advertencias": advertencias}

        logger.info(f"Validación 2 exitosa: valor_factura_sin_iva = ${valor_factura_sin_iva:,.2f}")

        # VALIDACIÓN 3: actividades_relacionadas no vacías y con nombre_act_rel válido
        if not actividades_relacionadas or len(actividades_relacionadas) == 0:
            errores.append(
                f"Las actividades facturadas: {', '.join(actividades_facturadas)} "
                f"no se encontró relación con las actividades de la base de datos"
            )
            logger.warning("Validación 3 fallida: actividades_relacionadas vacía")
            return {"valido": False, "errores": errores, "advertencias": advertencias, "todas_no_aplican": True}

        # Validar cada actividad relacionada
        ubicaciones_vistas = {}  # Para validar unicidad de codigo_ubicacion

        for idx, act_rel in enumerate(actividades_relacionadas):
            nombre_act_rel = act_rel.get("nombre_act_rel", "").strip()

            # VALIDACIÓN 3: nombre_act_rel no vacío
            if not nombre_act_rel:
                errores.append(
                    f"Las actividades facturadas: {', '.join(actividades_facturadas)} "
                    f"no se encontró relación con las actividades de la base de datos"
                )
                logger.warning(f"Validación 3 fallida: nombre_act_rel vacío en actividad {idx+1}")
                return {"valido": False, "errores": errores, "advertencias": advertencias, "todas_no_aplican": True}

            # VALIDACIÓN 4: codigo_actividad y codigo_ubicacion > 0
            codigo_actividad = act_rel.get("codigo_actividad", 0)
            codigo_ubicacion = act_rel.get("codigo_ubicacion", 0)

            if codigo_actividad <= 0 or codigo_ubicacion <= 0:
                errores.append(
                    f"No se pudo relacionar correctamente la actividad '{nombre_act_rel}' "
                    f"(codigo_actividad: {codigo_actividad}, codigo_ubicacion: {codigo_ubicacion})"
                )
                logger.warning(f"Validación 4 fallida: códigos inválidos para '{nombre_act_rel}'")
                return {"valido": False, "errores": errores, "advertencias": advertencias}

            # VALIDACIÓN 5: codigo_ubicacion único (no puede haber múltiples actividades con mismo codigo_ubicacion)
            if codigo_ubicacion in ubicaciones_vistas:
                errores.append(
                    f"Error en el análisis: Se encontraron múltiples actividades relacionadas "
                    f"para la misma ubicación {codigo_ubicacion}. "
                    f"Actividades: '{ubicaciones_vistas[codigo_ubicacion]}' y '{nombre_act_rel}'. "
                    f"Solo puede haber UNA actividad relacionada por ubicación"
                )
                logger.warning(f"Validación 5 fallida: codigo_ubicacion {codigo_ubicacion} duplicado")
                return {"valido": False, "errores": errores, "advertencias": advertencias}

            ubicaciones_vistas[codigo_ubicacion] = nombre_act_rel

        logger.info(f"Todas las validaciones exitosas: {len(actividades_relacionadas)} actividades relacionadas válidas")
        return {"valido": True, "errores": [], "advertencias": advertencias}
