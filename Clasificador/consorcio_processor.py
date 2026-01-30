"""
PROCESADOR DE CONSORCIOS - RETEFUENTE
===================================

Módulo especializado para procesar facturas de consorcios y calcular 
retenciones en la fuente individuales para cada consorciado.

Funcionalidades:
- Detección automática de consorcios
- Extracción de consorciados y porcentajes
- Normalización de porcentajes de participación
- Cálculo individual de retenciones por consorciado
- Validaciones específicas por naturaleza de tercero

Autor: Miguel Angel Jaramillo Durango
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel

# Configuración de logging
logger = logging.getLogger(__name__)

# ===============================
# MODELOS DE DATOS PARA CONSORCIOS
# ===============================

class Consorciado(BaseModel):
    """Modelo para un consorciado individual"""
    nombre: str
    nit: str
    porcentaje_participacion: float
    valor_proporcional: float
    naturaleza_tercero: Optional[Dict[str, Any]] = None  # 🔧 CORREGIDO: Permite null
    articulo_383: Optional[Dict[str, Any]] = None  # NUEVO: Información del Artículo 383
    aplica_retencion: bool
    valor_retencion: float
    tarifa_aplicada: Optional[float] = None  # NUEVO: Tarifa aplicada (convencional o Art. 383)
    tipo_calculo: Optional[str] = None  # NUEVO: "CONVENCIONAL" o "ARTICULO_383"
    razon_no_retencion: Optional[str] = None

class ConsorcioInfo(BaseModel):
    """Información general del consorcio"""
    nombre_consorcio: str
    nit_consorcio: str
    total_consorciados: int

class ResumenRetencion(BaseModel):
    """Resumen de retenciones del consorcio"""
    valor_total_factura: float
    iva_total: float
    total_retenciones: float
    consorciados_con_retencion: int
    consorciados_sin_retencion: int
    consorciados_art383: Optional[int] = 0  # NUEVO: Consorciados con Art. 383
    consorciados_convencional: Optional[int] = 0  # NUEVO: Consorciados con tarifa convencional
    suma_porcentajes_original: float
    porcentajes_normalizados: bool

class AnalisisConsorcio(BaseModel):
    """Análisis completo de un consorcio"""
    es_consorcio: bool
    consorcio_info: ConsorcioInfo
    consorciados: List[Consorciado]
    conceptos_identificados: List[Dict[str, Any]]
    resumen_retencion: ResumenRetencion
    es_facturacion_exterior: bool
    observaciones: List[str]

# ===============================
# PROCESADOR DE CONSORCIOS
# ===============================

class ProcesadorConsorcios:
    """Procesador especializado para manejar consorcios"""
    
    def __init__(self):
        """Inicializar procesador de consorcios"""
        logger.info("ProcesadorConsorcios inicializado")
    
    def detectar_consorcio(self, respuesta_clasificacion: Dict[str, Any]) -> bool:
        """
        Detecta si se trata de un consorcio basado en la respuesta de clasificación.
        
        Args:
            respuesta_clasificacion: Respuesta de Gemini de la clasificación
            
        Returns:
            bool: True si es consorcio, False si no
        """
        try:
            # Verificar si Gemini detectó consorcio
            es_consorcio = respuesta_clasificacion.get("es_consorcio", False)
            
            if es_consorcio:
                indicadores = respuesta_clasificacion.get("indicadores_consorcio", [])
                logger.info(f"Consorcio detectado. Indicadores: {indicadores}")
                return True
            
            logger.info("No se detectó consorcio")
            return False
            
        except Exception as e:
            logger.error(f"Error detectando consorcio: {e}")
            return False
    
    def procesar_respuesta_consorcio(self, respuesta_gemini: Dict[str, Any]) -> AnalisisConsorcio:
        """
        Procesa la respuesta de Gemini para análisis de consorcio.
        
        Args:
            respuesta_gemini: Respuesta completa de Gemini para consorcios
            
        Returns:
            AnalisisConsorcio: Análisis estructurado del consorcio
            
        Raises:
            ValueError: Si la respuesta no es válida
        """
        try:
            logger.info("Procesando respuesta de consorcio")
            
            # Validar estructura mínima requerida
            self._validar_estructura_minima(respuesta_gemini)
            
            # Normalizar porcentajes si es necesario
            respuesta_normalizada = self._normalizar_porcentajes(respuesta_gemini)
            
            # Validar datos básicos
            self._validar_datos_consorcio(respuesta_normalizada)
            
            # Completar campos faltantes con valores por defecto
            respuesta_completa = self._completar_campos_faltantes(respuesta_normalizada)
            
            # Crear análisis estructurado
            analisis = AnalisisConsorcio(**respuesta_completa)
            
            logger.info(f"Consorcio procesado: {analisis.consorcio_info.total_consorciados} consorciados")
            return analisis
            
        except Exception as e:
            logger.error(f"Error procesando respuesta de consorcio: {e}")
            raise ValueError(f"Error procesando consorcio: {str(e)}")
    
    def _validar_estructura_minima(self, respuesta: Dict[str, Any]):
        """
        Valida que la respuesta tenga la estructura mínima necesaria.
        
        Args:
            respuesta: Respuesta de Gemini
            
        Raises:
            ValueError: Si falta estructura esencial
        """
        campos_requeridos = ['es_consorcio', 'consorcio_info', 'consorciados']
        for campo in campos_requeridos:
            if campo not in respuesta:
                raise ValueError(f"Campo requerido '{campo}' no encontrado en la respuesta")
        
        if not isinstance(respuesta.get('consorciados'), list):
            raise ValueError("'consorciados' debe ser una lista")
    
    def _completar_campos_faltantes(self, respuesta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Completa campos faltantes con valores por defecto.
        
        Args:
            respuesta: Respuesta normalizada
            
        Returns:
            Dict: Respuesta con campos completos
        """
        # Asegurar que existen todos los campos necesarios
        if 'conceptos_identificados' not in respuesta:
            respuesta['conceptos_identificados'] = [{
                'concepto': 'CONCEPTO_NO_IDENTIFICADO',
                'tarifa_retencion': 0.0,
                'base_gravable': 0.0,
                'base_minima': 0.0
            }]
        
        if 'resumen_retencion' not in respuesta:
            respuesta['resumen_retencion'] = {
                'valor_total_factura': 0.0,
                'iva_total': 0.0,
                'total_retenciones': 0.0,
                'consorciados_con_retencion': 0,
                'consorciados_sin_retencion': len(respuesta.get('consorciados', [])),
                'consorciados_art383': 0,  # NUEVO
                'consorciados_convencional': 0,  # NUEVO
                'suma_porcentajes_original': 0.0,
                'porcentajes_normalizados': False
            }
        
        # Asegurar que existen los nuevos campos del Art. 383 en el resumen
        if 'consorciados_art383' not in respuesta['resumen_retencion']:
            respuesta['resumen_retencion']['consorciados_art383'] = 0
        if 'consorciados_convencional' not in respuesta['resumen_retencion']:
            respuesta['resumen_retencion']['consorciados_convencional'] = 0
        
        # Completar campos del Art. 383 en cada consorciado
        for consorciado in respuesta.get('consorciados', []):
            if 'articulo_383' not in consorciado:
                consorciado['articulo_383'] = {
                    'aplica': False,
                    'condiciones_cumplidas': {
                        'es_persona_natural': False,
                        'concepto_aplicable': False,
                        'es_primer_pago': False,
                        'planilla_seguridad_social': False,
                        'cuenta_cobro': False
                    },
                    'deducciones_identificadas': {
                        'intereses_vivienda': {'valor': 0.0, 'tiene_soporte': False, 'limite_aplicable': 0.0},
                        'dependientes_economicos': {'valor': 0.0, 'tiene_soporte': False, 'limite_aplicable': 0.0},
                        'medicina_prepagada': {'valor': 0.0, 'tiene_soporte': False, 'limite_aplicable': 0.0},
                        'rentas_exentas': {'valor': 0.0, 'tiene_soporte': False, 'limite_aplicable': 0.0}
                    },
                    'calculo': {
                        'ingreso_bruto': 0.0,
                        'aportes_seguridad_social': 0.0,
                        'total_deducciones': 0.0,
                        'deducciones_limitadas': 0.0,
                        'base_gravable_final': 0.0,
                        'base_gravable_uvt': 0.0,
                        'tarifa_aplicada': 0.0,
                        'valor_retencion_art383': 0.0
                    }
                }
            if 'tarifa_aplicada' not in consorciado:
                consorciado['tarifa_aplicada'] = 0.0
            if 'tipo_calculo' not in consorciado:
                consorciado['tipo_calculo'] = 'CONVENCIONAL'
        
        if 'es_facturacion_exterior' not in respuesta:
            respuesta['es_facturacion_exterior'] = False
        
        if 'observaciones' not in respuesta:
            respuesta['observaciones'] = ['Procesado con campos por defecto']
        
        return respuesta
    
    def calcular_retenciones_consorcio(self, analisis: AnalisisConsorcio, 
                                     conceptos_retefuente: Dict[str, Dict]) -> AnalisisConsorcio:
        """
        Calcula las retenciones individuales para cada consorciado.
        
        Args:
            analisis: Análisis del consorcio
            conceptos_retefuente: Diccionario de conceptos con tarifas y bases
            
        Returns:
            AnalisisConsorcio: Análisis actualizado con cálculos finales
        """
        try:
            logger.info("Calculando retenciones por consorciado")
            
            if not analisis.conceptos_identificados:
                logger.warning("No hay conceptos identificados")
                return analisis
            
            concepto_principal = analisis.conceptos_identificados[0]
            nombre_concepto = concepto_principal.get("concepto")
            
            if nombre_concepto == "CONCEPTO_NO_IDENTIFICADO":
                logger.warning("Concepto no identificado, no se pueden calcular retenciones")
                return analisis
            
            # Obtener datos del concepto
            datos_concepto = conceptos_retefuente.get(nombre_concepto)
            if not datos_concepto:
                logger.error(f"Concepto no encontrado en diccionario: {nombre_concepto}")
                return analisis
            
            base_minima = datos_concepto.get("base_pesos", 0)
            tarifa = datos_concepto.get("tarifa_retencion", 0)
            
            # Calcular retenciones por consorciado (ACTUALIZADO PARA ART. 383)
            total_retenciones = 0
            consorciados_con_retencion = 0
            consorciados_sin_retencion = 0
            consorciados_art383 = 0
            consorciados_convencional = 0
            
            for i, consorciado in enumerate(analisis.consorciados):
                # Determinar tipo de cálculo y tarifa a aplicar
                resultado_calculo = self._calcular_retencion_consorciado(
                    consorciado, base_minima, tarifa, analisis.es_facturacion_exterior
                )
                
                # Actualizar datos del consorciado
                analisis.consorciados[i].valor_retencion = resultado_calculo['valor_retencion']
                analisis.consorciados[i].aplica_retencion = resultado_calculo['aplica_retencion']
                analisis.consorciados[i].tarifa_aplicada = resultado_calculo['tarifa_aplicada']
                analisis.consorciados[i].tipo_calculo = resultado_calculo['tipo_calculo']
                analisis.consorciados[i].razon_no_retencion = resultado_calculo['razon_no_retencion']
                
                # Contabilizar resultados
                if resultado_calculo['aplica_retencion']:
                    total_retenciones += resultado_calculo['valor_retencion']
                    consorciados_con_retencion += 1
                    
                    if resultado_calculo['tipo_calculo'] == 'ARTICULO_383':
                        consorciados_art383 += 1
                    else:
                        consorciados_convencional += 1
                else:
                    consorciados_sin_retencion += 1
            
            # Actualizar resumen
            analisis.resumen_retencion.total_retenciones = total_retenciones
            analisis.resumen_retencion.consorciados_con_retencion = consorciados_con_retencion
            analisis.resumen_retencion.consorciados_sin_retencion = consorciados_sin_retencion
            analisis.resumen_retencion.consorciados_art383 = consorciados_art383
            analisis.resumen_retencion.consorciados_convencional = consorciados_convencional
            
            logger.info(f"Retenciones calculadas: ${total_retenciones:,.2f} total")
            return analisis
            
        except Exception as e:
            logger.error(f"Error calculando retenciones: {e}")
            return analisis
    
    def convertir_a_formato_compatible(self, analisis: AnalisisConsorcio) -> Dict[str, Any]:
        """
        Convierte el análisis de consorcio al formato compatible con el frontend.
        
        Args:
            analisis: Análisis del consorcio
            
        Returns:
            Dict: Respuesta en formato compatible con estructura actual
        """
        try:
            # Crear respuesta compatible expandiendo la estructura actual
            respuesta = {
                "aplica_retencion": analisis.resumen_retencion.total_retenciones > 0,
                "es_consorcio": True,
                "valor_total_factura": analisis.resumen_retencion.valor_total_factura,
                "iva_total": analisis.resumen_retencion.iva_total,
                "valor_retencion": analisis.resumen_retencion.total_retenciones,
                
                # Información del concepto principal
                "concepto": analisis.conceptos_identificados[0].get("concepto") if analisis.conceptos_identificados else "CONCEPTO_NO_IDENTIFICADO",
                "tarifa_retencion": analisis.conceptos_identificados[0].get("tarifa_retencion") if analisis.conceptos_identificados else 0,
                
                # Información específica del consorcio
                "consorcio_info": analisis.consorcio_info.dict(),
                "consorciados": [c.dict() for c in analisis.consorciados],
                "resumen_retencion": analisis.resumen_retencion.dict(),
                
                # Campos estándar
                "es_facturacion_exterior": analisis.es_facturacion_exterior,
                "observaciones": analisis.observaciones,
                
                # Metadatos
                "tipo_procesamiento": "CONSORCIO",
                "timestamp": self._obtener_timestamp()
            }
            
            logger.info("Respuesta convertida a formato compatible")
            return respuesta
            
        except Exception as e:
            logger.error(f"Error convirtiendo formato: {e}")
            return {
                "aplica_retencion": False,
                "es_consorcio": True,
                "error": f"Error procesando consorcio: {str(e)}",
                "observaciones": ["Error en procesamiento de consorcio"]
            }
    
    def _normalizar_porcentajes(self, respuesta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza los porcentajes de participación para que sumen exactamente 100%.
        
        Args:
            respuesta: Respuesta de Gemini
            
        Returns:
            Dict: Respuesta con porcentajes normalizados
        """
        try:
            if "consorciados" not in respuesta:
                return respuesta
            
            consorciados = respuesta["consorciados"]
            
            # Calcular suma total de porcentajes
            suma_original = sum(c.get("porcentaje_participacion", 0) for c in consorciados)
            
            if abs(suma_original - 100.0) < 0.01:  # Ya están normalizados
                respuesta["resumen_retencion"]["suma_porcentajes_original"] = suma_original
                respuesta["resumen_retencion"]["porcentajes_normalizados"] = False
                return respuesta
            
            # Normalizar porcentajes
            if suma_original > 0:
                factor_normalizacion = 100.0 / suma_original
                
                for consorciado in consorciados:
                    porcentaje_original = consorciado.get("porcentaje_participacion", 0)
                    porcentaje_normalizado = porcentaje_original * factor_normalizacion
                    consorciado["porcentaje_participacion"] = porcentaje_normalizado
                    
                    # Recalcular valor proporcional
                    valor_total = respuesta.get("resumen_retencion", {}).get("valor_total_factura", 0)
                    consorciado["valor_proporcional"] = valor_total * (porcentaje_normalizado / 100.0)
                
                respuesta["resumen_retencion"]["suma_porcentajes_original"] = suma_original
                respuesta["resumen_retencion"]["porcentajes_normalizados"] = True
                
                logger.info(f"Porcentajes normalizados: {suma_original:.5f}% → 100.000%")
            
            return respuesta
            
        except Exception as e:
            logger.error(f"Error normalizando porcentajes: {e}")
            return respuesta
    
    def _validar_datos_consorcio(self, respuesta: Dict[str, Any]):
        """
        Valida que los datos del consorcio sean consistentes.
        
        Args:
            respuesta: Respuesta normalizada
            
        Raises:
            ValueError: Si los datos no son válidos
        """
        if not respuesta.get("es_consorcio", False):
            raise ValueError("La respuesta no corresponde a un consorcio")
        
        if not respuesta.get("consorciados"):
            raise ValueError("No se encontraron consorciados")
        
        if not respuesta.get("consorcio_info"):
            raise ValueError("Información del consorcio incompleta")
        
        if len(respuesta["consorciados"]) != respuesta["consorcio_info"].get("total_consorciados", 0):
            logger.warning("Discrepancia en número de consorciados")
    
    def _calcular_retencion_consorciado(self, consorciado: Consorciado, 
                                       base_minima: float, tarifa_convencional: float, es_exterior: bool) -> Dict[str, Any]:
        """
        Calcula la retención para un consorciado específico (Artículo 383 o convencional).
        
        Args:
            consorciado: Datos del consorciado
            base_minima: Base mínima del concepto
            tarifa_convencional: Tarifa convencional del concepto
            es_exterior: Si es facturación exterior
            
        Returns:
            Dict: Resultado del cálculo con valor_retencion, tipo_calculo, etc.
        """
        try:
            # Estructura de retorno por defecto
            resultado = {
                'aplica_retencion': False,
                'valor_retencion': 0.0,
                'tarifa_aplicada': 0.0,
                'tipo_calculo': 'CONVENCIONAL',
                'razon_no_retencion': None
            }
            
            # Validación 1: Facturación exterior
            if es_exterior:
                resultado['razon_no_retencion'] = "Facturación exterior"
                return resultado
            
            # Validación 2: Naturaleza del tercero
            if consorciado.naturaleza_tercero is None:
                resultado['razon_no_retencion'] = "NATURALEZA_NO_DETERMINADA"
                return resultado
            
            # Validación 3: Responsable de IVA
            if not consorciado.naturaleza_tercero.get("es_responsable_iva", True):
                resultado['razon_no_retencion'] = "No responsable de IVA"
                return resultado
            
            # Validación 4: Autorretenedor
            if consorciado.naturaleza_tercero.get("es_autorretenedor", False):
                resultado['razon_no_retencion'] = "Es autorretenedor"
                return resultado
            
            # Validación 5: Régimen simple
            if consorciado.naturaleza_tercero.get("regimen_tributario") == "SIMPLE":
                resultado['razon_no_retencion'] = "Régimen simple de tributación"
                return resultado
            
            # Validación 6: Base mínima total del consorcio
            if consorciado.valor_proporcional < base_minima:
                resultado['razon_no_retencion'] = f"No supera base mínima individual (${base_minima:,.0f})"
                return resultado
            
            # VALIDACIÓN ARTÍCULO 383 PARA PERSONAS NATURALES
            es_persona_natural = consorciado.naturaleza_tercero.get("es_persona_natural", False)
            
            if es_persona_natural and hasattr(consorciado, 'articulo_383') and consorciado.articulo_383:
                # Verificar si aplica Artículo 383
                info_art383 = consorciado.articulo_383
                if info_art383.get('aplica', False):
                    # Usar cálculo del Artículo 383
                    calculo_art383 = info_art383.get('calculo', {})
                    valor_retencion_art383 = calculo_art383.get('valor_retencion_art383', 0.0)
                    tarifa_art383 = calculo_art383.get('tarifa_aplicada', 0.0)
                    
                    resultado.update({
                        'aplica_retencion': True,
                        'valor_retencion': valor_retencion_art383,
                        'tarifa_aplicada': tarifa_art383,
                        'tipo_calculo': 'ARTICULO_383',
                        'razon_no_retencion': None
                    })
                    
                    logger.info(f"Consorciado {consorciado.nombre}: Art. 383 aplicado - ${valor_retencion_art383:,.0f} ({tarifa_art383:.1f}%)")
                    return resultado
            
            # CÁLCULO CONVENCIONAL (si no aplica Art. 383)
            valor_retencion = consorciado.valor_proporcional * tarifa_convencional
            tarifa_porcentaje = tarifa_convencional * 100
            
            resultado.update({
                'aplica_retencion': True,
                'valor_retencion': valor_retencion,
                'tarifa_aplicada': tarifa_porcentaje,
                'tipo_calculo': 'CONVENCIONAL',
                'razon_no_retencion': None
            })
            
            logger.info(f"Consorciado {consorciado.nombre}: Tarifa convencional - ${valor_retencion:,.0f} ({tarifa_porcentaje:.1f}%)")
            return resultado
            
        except Exception as e:
            logger.error(f"Error calculando retención consorciado: {e}")
            return {
                'aplica_retencion': False,
                'valor_retencion': 0.0,
                'tarifa_aplicada': 0.0,
                'tipo_calculo': 'ERROR',
                'razon_no_retencion': f"Error en cálculo: {str(e)}"
            }
    
    def _obtener_timestamp(self) -> str:
        """Obtiene timestamp actual"""
        from datetime import datetime
        return datetime.now().isoformat()
