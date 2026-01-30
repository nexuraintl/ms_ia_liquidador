"""
LIQUIDADOR ICA (INDUSTRIA Y COMERCIO)
=====================================

Módulo para calcular la retención de ICA basándose en el análisis
del clasificador ICA. Realiza los cálculos finales según tarifas
parametrizadas en la base de datos.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo cálculos de ICA
- DIP: Depende de abstracciones (database_manager)
- OCP: Abierto para extensión (nuevas tarifas/reglas)
- LSP: Puede sustituirse por otras implementaciones

ARQUITECTURA:
- Clasificador: Identifica y valida datos
- Liquidador: Calcula valores finales

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

import logging
from typing import Dict, List, Any
from datetime import datetime

# Importar módulo Conversor TRM para conversión USD a COP
from Conversor import ConversorTRM
from Conversor.exceptions import TRMServiceError, TRMValidationError

# Configuración de logging
logger = logging.getLogger(__name__)


class LiquidadorICA:
    """
    Liquidador especializado para retención de ICA.

    RESPONSABILIDADES (SRP):
    - Recibir datos validados del clasificador
    - Consultar tarifas de la base de datos
    - Realizar cálculos finales de ICA
    - Generar resultado estructurado

    DEPENDENCIAS (DIP):
    - database_manager: Para consultas de tarifas
    """

    def __init__(self, database_manager: Any):
        """
        Inicializa el liquidador ICA con inyección de dependencias.

        Args:
            database_manager: Gestor de base de datos (abstracción)
        """
        self.database_manager = database_manager
        logger.info("LiquidadorICA inicializado siguiendo principios SOLID")

    def _convertir_resultado_ica_usd_a_cop(self, resultado: Dict[str, Any], trm_valor: float) -> Dict[str, Any]:
        """
        Convierte todos los valores monetarios de ICA de USD a COP.

        SRP: Solo responsable de convertir valores monetarios usando la TRM

        Args:
            resultado: Diccionario con resultado de ICA en USD
            trm_valor: Valor de la TRM para conversión

        Returns:
            Diccionario con todos los valores convertidos a COP
        """
        logger.info(f"Convirtiendo resultado ICA de USD a COP usando TRM: {trm_valor}")

        # Convertir valores principales
        if "valor_total_ica" in resultado:
            resultado["valor_total_ica"] = resultado["valor_total_ica"] * trm_valor

        if "valor_factura_sin_iva" in resultado:
            resultado["valor_factura_sin_iva"] = resultado["valor_factura_sin_iva"] * trm_valor

        # Convertir valores en cada actividad relacionada
        if "actividades_relacionadas" in resultado:
            for actividad in resultado["actividades_relacionadas"]:
                if "base_gravable_ubicacion" in actividad:
                    actividad["base_gravable_ubicacion"] = actividad["base_gravable_ubicacion"] * trm_valor
                if "valor_ica" in actividad:
                    actividad["valor_ica"] = actividad["valor_ica"] * trm_valor

        # Agregar mensaje de conversión
        if "observaciones" not in resultado:
            resultado["observaciones"] = []

        mensaje_conversion = f"Valores convertidos de USD a COP usando TRM: ${trm_valor:,.2f}"
        if mensaje_conversion not in resultado["observaciones"]:
            resultado["observaciones"].append(mensaje_conversion)

        logger.info(f"Conversión ICA completada. Total ICA en COP: ${resultado.get('valor_total_ica', 0):,.2f}")
        return resultado

    def liquidar_ica(self, analisis_clasificador: Dict[str, Any], estructura_contable: int, tipoMoneda: str = "COP") -> Dict[str, Any]:
        """
        Liquida ICA basándose en el análisis del clasificador (NUEVO FORMATO v3.0).

        FLUJO:
        1. Validar estado del análisis
        2. Para cada actividad relacionada:
           - Calcular base_gravable_ubicacion = valor_factura_sin_iva * porcentaje_ubicacion
           - Obtener tarifa de la BD
           - Calcular valor_ica = base_gravable_ubicacion * tarifa
        3. Sumar todos los valores
        4. Generar resultado estructurado con nuevo formato
        5. Si tipoMoneda es USD, convertir todos los valores a COP usando TRM

        Args:
            analisis_clasificador: Resultado del ClasificadorICA (NUEVO FORMATO v3.0)
            estructura_contable: Código de estructura contable
            tipoMoneda: Tipo de moneda ("COP" o "USD"), por defecto "COP"

        Returns:
            Dict con resultado final de liquidación ICA (valores en COP)
        """
        logger.info("Iniciando liquidación ICA (NUEVO FORMATO v3.0)...")

        # Resultado base (ESTRUCTURA COMPLETA v3.0)
        resultado = {
            "aplica": False,
            "estado": "no_aplica_impuesto",
            "valor_total_ica": 0.0,
            "actividades_facturadas": [],
            "actividades_relacionadas": [],
            "valor_factura_sin_iva": 0.0,  # NUEVO FORMATO v3.0 - consistencia
            "autorretenedor_ica": False,  # NUEVO 
            "observaciones": analisis_clasificador.get("observaciones", []),
            "fecha_liquidacion": datetime.now().isoformat()
        }

        try:
            # PASO 1: Validar que el análisis del clasificador es válido
            if not analisis_clasificador.get("aplica", False):
                resultado["estado"] = analisis_clasificador.get("estado", "no_aplica_impuesto")
                logger.info(f"ICA no aplica - Estado: {resultado['estado']}")
                # Convertir si es USD (aunque no aplica, puede tener valor_factura)
                if tipoMoneda and tipoMoneda.upper() == "USD":
                    try:
                        with ConversorTRM(timeout=30) as conversor:
                            trm_valor = conversor.obtener_trm_valor()
                            resultado = self._convertir_resultado_ica_usd_a_cop(resultado, trm_valor)
                    except Exception as e:
                        logger.warning(f"No se pudo convertir resultado ICA (no aplica): {e}")
                return resultado

            if analisis_clasificador.get("estado") != "Validado - Listo para liquidación":
                resultado["aplica"] = True  # Aplica pero no se puede liquidar
                resultado["estado"] = analisis_clasificador.get("estado", "preliquidacion_sin_finalizar")
                logger.warning(f"No se puede liquidar - Estado: {resultado['estado']}")
                # Convertir si es USD
                if tipoMoneda and tipoMoneda.upper() == "USD":
                    try:
                        with ConversorTRM(timeout=30) as conversor:
                            trm_valor = conversor.obtener_trm_valor()
                            resultado = self._convertir_resultado_ica_usd_a_cop(resultado, trm_valor)
                    except Exception as e:
                        logger.warning(f"No se pudo convertir resultado ICA (sin finalizar): {e}")
                return resultado

            # PASO 2: Extraer datos validados (NUEVO FORMATO v3.0)
            actividades_facturadas = analisis_clasificador.get("actividades_facturadas", [])
            actividades_relacionadas = analisis_clasificador.get("actividades_relacionadas", [])
            valor_factura_sin_iva = analisis_clasificador.get("valor_factura_sin_iva", 0.0)
            ubicaciones_identificadas = analisis_clasificador.get("ubicaciones_identificadas", [])
            autorretenedor_ica = analisis_clasificador.get("autorretenedor_ica", False)
            
            if autorretenedor_ica:
                resultado["estado"] = "no_aplica_impuesto"
                resultado["observaciones"].append("El sujeto pasivo es autorretenedor de ICA, no aplica retención.")
                resultado["actividades_facturadas"] = actividades_facturadas
                resultado["valor_factura_sin_iva"] = valor_factura_sin_iva  # Preservar estructura completa
                resultado["autorretenedor_ica"] = autorretenedor_ica
                logger.info("Sujeto pasivo es autorretenedor de ICA, no aplica retención.")
                # Convertir si es USD
                if tipoMoneda and tipoMoneda.upper() == "USD":
                    try:
                        with ConversorTRM(timeout=30) as conversor:
                            trm_valor = conversor.obtener_trm_valor()
                            resultado = self._convertir_resultado_ica_usd_a_cop(resultado, trm_valor)
                    except Exception as e:
                        logger.warning(f"No se pudo convertir resultado ICA (autorretenedor): {e}")
                return resultado

            if not actividades_relacionadas:
                resultado["estado"] = "preliquidacion_sin_finalizar"
                resultado["observaciones"].append("No hay actividades relacionadas para liquidar")
                resultado["actividades_facturadas"] = actividades_facturadas
                resultado["valor_factura_sin_iva"] = valor_factura_sin_iva  # Preservar estructura completa
                logger.error("No hay actividades relacionadas")
                # Convertir si es USD
                if tipoMoneda and tipoMoneda.upper() == "USD":
                    try:
                        with ConversorTRM(timeout=30) as conversor:
                            trm_valor = conversor.obtener_trm_valor()
                            resultado = self._convertir_resultado_ica_usd_a_cop(resultado, trm_valor)
                    except Exception as e:
                        logger.warning(f"No se pudo convertir resultado ICA (sin actividades): {e}")
                return resultado

            logger.info(f"Liquidando {len(actividades_relacionadas)} actividades relacionadas con valor factura: ${valor_factura_sin_iva:,.2f}")

            # PASO 3: Procesar cada actividad relacionada
            actividades_liquidadas = []
            valor_total_ica = 0.0

            for act_rel in actividades_relacionadas:
                actividad_liquidada = self._liquidar_actividad_facturada(
                    act_rel,
                    valor_factura_sin_iva,
                    ubicaciones_identificadas,
                    estructura_contable
                )

                if actividad_liquidada:
                    # Extraer observaciones de esta actividad y agregarlas al resultado
                    if actividad_liquidada.get("observaciones"):
                        resultado["observaciones"].extend(actividad_liquidada["observaciones"])

                    # Agregar actividad a la lista (sin el campo observaciones interno)
                    actividad_para_resultado = {
                        "nombre_act_rel": actividad_liquidada["nombre_act_rel"],
                        "codigo_actividad": actividad_liquidada["codigo_actividad"],
                        "codigo_ubicacion": actividad_liquidada["codigo_ubicacion"],
                        "nombre_ubicacion": actividad_liquidada["nombre_ubicacion"],
                        "base_gravable_ubicacion": actividad_liquidada["base_gravable_ubicacion"],
                        "tarifa": actividad_liquidada["tarifa"],
                        "porc_ubicacion": actividad_liquidada["porc_ubicacion"],
                        "valor_ica": actividad_liquidada["valor_ica"]
                    }
                    actividades_liquidadas.append(actividad_para_resultado)
                    valor_total_ica += actividad_liquidada["valor_ica"]

            # PASO 4: Validar que se liquidó al menos una actividad
            if not actividades_liquidadas:
                resultado["estado"] = "preliquidacion_sin_finalizar"
                resultado["observaciones"].append(
                    "No se pudo liquidar ninguna actividad (problemas obteniendo tarifas de BD)"
                )
                resultado["actividades_facturadas"] = actividades_facturadas
                resultado["valor_factura_sin_iva"] = valor_factura_sin_iva  # Preservar estructura completa
                logger.error("No se liquidó ninguna actividad")
                # Convertir si es USD
                if tipoMoneda and tipoMoneda.upper() == "USD":
                    try:
                        with ConversorTRM(timeout=30) as conversor:
                            trm_valor = conversor.obtener_trm_valor()
                            resultado = self._convertir_resultado_ica_usd_a_cop(resultado, trm_valor)
                    except Exception as e:
                        logger.warning(f"No se pudo convertir resultado ICA (ninguna liquidada): {e}")
                return resultado

            # PASO 5: Generar resultado final exitoso (NUEVO FORMATO v3.0)
            resultado["aplica"] = True
            resultado["estado"] = "preliquidado"
            resultado["valor_total_ica"] = round(valor_total_ica, 2)
            resultado["actividades_facturadas"] = actividades_facturadas
            resultado["actividades_relacionadas"] = actividades_liquidadas
            resultado["valor_factura_sin_iva"] = valor_factura_sin_iva  # Preservar estructura completa

            logger.info(f"Liquidación ICA exitosa - Total: ${valor_total_ica:,.2f}")

            # PASO 6: Convertir de USD a COP si es necesario
            if tipoMoneda and tipoMoneda.upper() == "USD":
                logger.info("Moneda detectada: USD - Iniciando conversión ICA a COP usando TRM...")
                try:
                    with ConversorTRM(timeout=30) as conversor:
                        trm_valor = conversor.obtener_trm_valor()
                        logger.info(f"TRM obtenida exitosamente: ${trm_valor:,.2f} COP/USD")
                        resultado = self._convertir_resultado_ica_usd_a_cop(resultado, trm_valor)
                except (TRMServiceError, TRMValidationError) as e:
                    logger.error(f"Error al obtener TRM para conversión ICA: {e}")
                    resultado["observaciones"].append(
                        f"ADVERTENCIA: No se pudo convertir de USD a COP (Error TRM: {str(e)}). Valores mostrados en USD."
                    )
                except Exception as e:
                    logger.error(f"Error inesperado en conversión USD a COP (ICA): {e}")
                    resultado["observaciones"].append(
                        f"ADVERTENCIA: Error inesperado en conversión de moneda. Valores mostrados en USD."
                    )
            else:
                logger.info(f"Moneda: {tipoMoneda or 'COP'} - No se requiere conversión ICA")

            return resultado

        except Exception as e:
            logger.error(f"Error en liquidación ICA: {e}")
            resultado["estado"] = "preliquidacion_sin_finalizar"
            resultado["observaciones"].append(f"Error en liquidación: {str(e)}")

            # Preservar estructura completa con datos del clasificador si están disponibles
            resultado["actividades_facturadas"] = analisis_clasificador.get("actividades_facturadas", [])
            resultado["actividades_relacionadas"] = analisis_clasificador.get("actividades_relacionadas", [])
            resultado["valor_factura_sin_iva"] = analisis_clasificador.get("valor_factura_sin_iva", 0.0)

            # Convertir valores USD a COP si es necesario
            if tipoMoneda and tipoMoneda.upper() == "USD":
                try:
                    with ConversorTRM(timeout=30) as conversor:
                        trm_valor = conversor.obtener_trm_valor()
                        resultado = self._convertir_resultado_ica_usd_a_cop(resultado, trm_valor)
                        resultado["observaciones"].append(f"Valores convertidos de USD a COP (TRM: {trm_valor})")
                except (TRMServiceError, TRMValidationError) as e_trm:
                    logger.warning(f"No se pudo obtener TRM para conversión (error handler): {e_trm}")
                    resultado["observaciones"].append(f"ADVERTENCIA: No se pudo convertir de USD a COP - {str(e_trm)}")
                except Exception as e_conv:
                    logger.warning(f"Error inesperado al convertir resultado ICA (error handler): {e_conv}")
                    resultado["observaciones"].append(f"ADVERTENCIA: Error al convertir valores USD - {str(e_conv)}")

            return resultado

    def _liquidar_actividad_facturada(
        self,
        actividad_relacionada: Dict[str, Any],
        valor_factura_sin_iva: float,
        ubicaciones_identificadas: List[Dict[str, Any]],
        estructura_contable: int
    ) -> Dict[str, Any]:
        """
        Liquida una actividad relacionada (NUEVO FORMATO v3.0).

        RESPONSABILIDAD (SRP):
        - Solo calcula valores para una actividad relacionada
        - Usa valor_factura_sin_iva como base única
        - Calcula base_gravable_ubicacion según porcentaje de participación
        - Delega consulta de tarifas a método específico
        - Acumula observaciones de tarifas duplicadas

        CÁLCULOS:
        - base_gravable_ubicacion = valor_factura_sin_iva * (porcentaje_ubicacion / 100)
        - valor_ica = base_gravable_ubicacion * (tarifa / 100)

        Args:
            actividad_relacionada: Actividad relacionada con BD
            valor_factura_sin_iva: Valor total de factura sin IVA
            ubicaciones_identificadas: Ubicaciones validadas con porcentajes

        Returns:
            Dict con actividad liquidada y observaciones:
            {
                "nombre_act_rel": str,
                "codigo_actividad": int,
                "codigo_ubicacion": int,
                "nombre_ubicacion": str,
                "base_gravable_ubicacion": float,
                "tarifa": float,
                "porc_ubicacion": float,
                "valor_ica": float,
                "observaciones": List[str]
            }
        """
        nombre_act_rel = actividad_relacionada.get("nombre_act_rel", "").strip()
        codigo_actividad = actividad_relacionada.get("codigo_actividad", 0)
        codigo_ubicacion = actividad_relacionada.get("codigo_ubicacion", 0)

        logger.info(f"Liquidando actividad relacionada: {nombre_act_rel} (Código: {codigo_actividad}, Ubicación: {codigo_ubicacion})")

        actividad_liquidada = {
            "nombre_act_rel": nombre_act_rel,
            "codigo_actividad": codigo_actividad,
            "codigo_ubicacion": codigo_ubicacion,
            "nombre_ubicacion": "",
            "base_gravable_ubicacion": 0.0,
            "tarifa": 0.0,
            "porc_ubicacion": 0.0,
            "valor_ica": 0.0,
            "observaciones": []
        }

        # Saltar si no hay relación
        if not nombre_act_rel:
            logger.warning("Actividad sin nombre, saltando...")
            return None

        # Obtener porcentaje de ubicación
        porcentaje_ubicacion = self._obtener_porcentaje_ubicacion(
            codigo_ubicacion, ubicaciones_identificadas
        )

        if porcentaje_ubicacion <= 0:
            logger.warning(f"No se encontró porcentaje para ubicación {codigo_ubicacion}")
            return None

        # Calcular base gravable para esta ubicación
        base_gravable_ubicacion = valor_factura_sin_iva * (porcentaje_ubicacion / 100.0)

        logger.info(f"  Base gravable ubicación: ${valor_factura_sin_iva:,.2f} x {porcentaje_ubicacion}% = ${base_gravable_ubicacion:,.2f}")

        # Obtener tarifa de la BD
        resultado_tarifa = self._obtener_tarifa_bd(codigo_ubicacion, codigo_actividad, estructura_contable)

        if resultado_tarifa["tarifa"] is None:
            logger.error(
                f"No se pudo obtener tarifa para actividad {codigo_actividad} "
                f"en ubicación {codigo_ubicacion}"
            )
            return None

        # Extraer tarifa y observación
        tarifa_bd = resultado_tarifa["tarifa"]
        observacion_tarifa = resultado_tarifa["observacion"]

        # Si hay observación de duplicado, agregarla
        if observacion_tarifa:
            actividad_liquidada["observaciones"].append(observacion_tarifa)

        # Obtener nombre de ubicación
        nombre_ubicacion = self._obtener_nombre_ubicacion(
            codigo_ubicacion, ubicaciones_identificadas
        )

        # CÁLCULO FINAL: valor_ica = base_gravable_ubicacion * (tarifa / 100)
        tarifa_decimal = tarifa_bd / 100.0
        valor_ica = base_gravable_ubicacion * tarifa_decimal

        logger.info(
            f"  Cálculo ICA: ${base_gravable_ubicacion:,.2f} x {tarifa_bd}% = ${valor_ica:,.2f}"
        )

        # Actualizar resultado
        actividad_liquidada["nombre_ubicacion"] = nombre_ubicacion
        actividad_liquidada["base_gravable_ubicacion"] = round(base_gravable_ubicacion, 2)
        actividad_liquidada["tarifa"] = tarifa_decimal 
        actividad_liquidada["porc_ubicacion"] = porcentaje_ubicacion
        actividad_liquidada["valor_ica"] = round(valor_ica, 2)

        return actividad_liquidada

    def _obtener_tarifa_bd(
        self,
        codigo_ubicacion: int,
        codigo_actividad: int,
        estructura_contable: int
    ) -> Dict[str, Any]:
        """
        Obtiene la tarifa de ICA de la base de datos.

        RESPONSABILIDAD (SRP):
        - Solo consulta tarifa de la BD
        - Detecta duplicados y genera observaciones
        - No calcula ni valida lógica de negocio

        Args:
            codigo_ubicacion: Código de ubicación
            codigo_actividad: Código de actividad

        Returns:
            Dict con estructura:
            {
                "tarifa": float | None,  # Tarifa en porcentaje (ej: 9.66)
                "observacion": str | None  # Mensaje si hay duplicados o error
            }
        """
        try:
            # Usar método abstracto de la interfaz DatabaseInterface
            resultado = self.database_manager.obtener_tarifa_ica(
                codigo_ubicacion=codigo_ubicacion,
                codigo_actividad=codigo_actividad,
                estructura_contable=estructura_contable
            )

            # VALIDACIÓN 1: Sin registros encontrados
            if not resultado['success']:
                logger.warning(
                    f"No se encontró tarifa para actividad {codigo_actividad} "
                    f"en ubicación {codigo_ubicacion}"
                )
                return {"tarifa": None, "observacion": None}

            # Obtener datos de la tarifa desde resultado
            tarifa_data = resultado['data']
            tarifa = tarifa_data['porcentaje_ica']
            descripcion = tarifa_data['descripcion_actividad']

            logger.info(
                f"Tarifa obtenida: {tarifa}% para actividad '{descripcion}' "
                f"(cod: {codigo_actividad}, ubic: {codigo_ubicacion})"
            )

            # Convertir tarifa manejando formato con coma decimal (5,0 -> 5.0)
            tarifa_convertida = float(str(tarifa).replace(',', '.')) if tarifa is not None else 0.0

            return {
                "tarifa": tarifa_convertida,
                "observacion": None
            }

        except Exception as e:
            logger.error(f"Error consultando tarifa de BD: {e}")
            return {"tarifa": None, "observacion": None}

    def _obtener_porcentaje_ubicacion(
        self,
        codigo_ubicacion: int,
        ubicaciones_identificadas: List[Dict[str, Any]]
    ) -> float:
        """
        Obtiene el porcentaje de ejecución para una ubicación.

        RESPONSABILIDAD (SRP):
        - Solo busca el porcentaje en la lista
        - No valida ni calcula

        Args:
            codigo_ubicacion: Código de ubicación
            ubicaciones_identificadas: Ubicaciones con porcentajes

        Returns:
            float: Porcentaje de ejecución (ej: 60.0 para 60%)
        """
        for ubicacion in ubicaciones_identificadas:
            if ubicacion.get("codigo_ubicacion") == codigo_ubicacion:
                return ubicacion.get("porcentaje_ejecucion", 0.0)

        logger.warning(f"No se encontró porcentaje para ubicación {codigo_ubicacion}")
        return 0.0

    def _obtener_nombre_ubicacion(
        self,
        codigo_ubicacion: int,
        ubicaciones_identificadas: List[Dict[str, Any]]
    ) -> str:
        """
        Obtiene el nombre de una ubicación.

        RESPONSABILIDAD (SRP):
        - Solo busca el nombre en la lista
        - No valida ni procesa

        Args:
            codigo_ubicacion: Código de ubicación
            ubicaciones_identificadas: Ubicaciones

        Returns:
            str: Nombre de la ubicación
        """
        for ubicacion in ubicaciones_identificadas:
            if ubicacion.get("codigo_ubicacion") == codigo_ubicacion:
                return ubicacion.get("nombre_ubicacion", "")

        logger.warning(f"No se encontró nombre para ubicación {codigo_ubicacion}")
        return ""


# ===============================
# FUNCIÓN DE CONVENIENCIA
# ===============================

def crear_liquidador_ica(database_manager: Any) -> LiquidadorICA:
    """
    Factory function para crear instancia de LiquidadorICA.

    PRINCIPIO: Factory Pattern para creación simplificada

    Args:
        database_manager: Gestor de base de datos

    Returns:
        LiquidadorICA: Instancia configurada
    """
    return LiquidadorICA(database_manager)
