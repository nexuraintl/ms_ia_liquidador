"""
LIQUIDADOR DE ESTAMPILLAS GENERALES
==================================

Módulo especializado para validar y presentar información de las 6 estampillas generales:
1. Procultura
2. Bienestar  
3. Adulto Mayor
4. Prouniversidad Pedagógica
5. Francisco José de Caldas
6. Prodeporte

Este módulo solo hace VALIDACIÓN y PRESENTACIÓN, NO cálculos.
Los análisis vienen de Gemini a través del clasificador.

Autor: Miguel Angel Jaramillo Durango
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

# Configuración de logging
logger = logging.getLogger(__name__)

# ===============================
# MODELOS DE DATOS PYDANTIC
# ===============================

class EstampillaGeneral(BaseModel):
    """
    Modelo para una estampilla general individual.

    NOTA: Gemini solo proporciona valores numéricos (0 si no encuentra).
    El estado se asigna por validaciones Python después.
    """
    nombre_estampilla: str
    porcentaje: float = 0.0  # Default 0 si Gemini no encuentra
    valor_base: float = 0.0  # Default 0 si Gemini no encuentra
    valor: float = 0.0       # Default 0 si Gemini no encuentra
    estado: Optional[str] = None  # Se asigna por Python después de validaciones
    texto_referencia: Optional[str] = None
    observaciones: Optional[str] = None

class ResumenAnalisisEstampillas(BaseModel):
    """
    Modelo para el resumen del análisis de estampillas.
    NOTA: Solo para uso interno (logging y validaciones).
    NO se incluye en el resultado final JSON.
    """
    total_estampillas_identificadas: int
    estampillas_completas: int
    estampillas_incompletas: int
    estampillas_no_aplican: int
    documentos_revisados: List[str]

class ResultadoEstampillasGenerales(BaseModel):
    """
    Modelo completo para el resultado de estampillas generales.
    NOTA: resumen_analisis es opcional, solo para uso interno, no aparece en JSON final.
    """
    estampillas_generales: List[EstampillaGeneral]
    resumen_analisis: Optional[ResumenAnalisisEstampillas] = None  # Opcional, solo uso interno
    procesamiento_exitoso: bool = True
    fecha_procesamiento: str = ""
    observaciones_generales: List[str] = []

# ===============================
# FUNCIONES PRINCIPALES
# ===============================

def validar_formato_estampillas_generales(respuesta_gemini: Dict[str, Any]) -> Dict[str, Any]:
    """
     Valida que el formato de salida de Gemini coincida con el modelo pydantic.
    
    Args:
        respuesta_gemini: Respuesta JSON de Gemini para estampillas generales
        
    Returns:
        Dict con resultado de validación y datos corregidos si es necesario
    """
    logger.info(" Validando formato de respuesta de estampillas generales")
    
    try:
        validacion = {
            "formato_valido": True,
            "errores": [],
            "advertencias": [],
            "datos_corregidos": False,
            "respuesta_validada": respuesta_gemini.copy()
        }
        
        # Validar estructura principal
        if "estampillas_generales" not in respuesta_gemini:
            validacion["errores"].append("Campo 'estampillas_generales' faltante")
            validacion["formato_valido"] = False
            validacion["respuesta_validada"]["estampillas_generales"] = _obtener_estampillas_default()
            validacion["datos_corregidos"] = True

        # Validar que sean exactamente 6 estampillas
        estampillas = validacion["respuesta_validada"]["estampillas_generales"]
        nombres_esperados = {
            "Procultura", "Bienestar", "Adulto Mayor", 
            "Prouniversidad Pedagógica", "Francisco José de Caldas", "Prodeporte"
        }
        
        if len(estampillas) != 6:
            validacion["errores"].append(f"Se esperan 6 estampillas, encontradas: {len(estampillas)}")
            validacion["formato_valido"] = False
            # Completar estampillas faltantes
            estampillas_encontradas = {e.get("nombre_estampilla", "") for e in estampillas}
            for nombre_faltante in nombres_esperados - estampillas_encontradas:
                estampillas.append({
                    "nombre_estampilla": nombre_faltante,
                    "porcentaje": 0.0,  # Default 0
                    "valor_base": 0.0,   # Default 0
                    "valor": 0.0,        # Default 0
                    "texto_referencia": None,
                    "observaciones": "Estampilla agregada automáticamente por validación"
                })
            validacion["datos_corregidos"] = True

        # Validar cada estampilla individual (solo formato y tipos)
        for i, estampilla in enumerate(estampillas):
            errores_estampilla = _validar_estampilla_individual(estampilla, i)
            if errores_estampilla:
                validacion["errores"].extend(errores_estampilla)
                validacion["formato_valido"] = False

        # NUEVO: Asignar estados a cada estampilla según reglas de validación
        logger.info(" Asignando estados a estampillas según validaciones Python")
        for estampilla in estampillas:
            _asignar_estado_estampilla(estampilla)
        
        # Validar usando modelo Pydantic
        try:
            resultado_validado = ResultadoEstampillasGenerales(**validacion["respuesta_validada"])
            logger.info(" Validación Pydantic exitosa para estampillas generales")
        except Exception as e:
            validacion["errores"].append(f"Error en validación Pydantic: {str(e)}")
            validacion["formato_valido"] = False
        
        # Log final
        if validacion["formato_valido"]:
            logger.info(f" Formato válido para estampillas generales. Corregido: {validacion['datos_corregidos']}")
        else:
            logger.error(f" Formato inválido para estampillas generales. Errores: {len(validacion['errores'])}")
        
        return validacion
        
    except Exception as e:
        logger.error(f"Error validando formato de estampillas: {e}")
        return {
            "formato_valido": False,
            "errores": [f"Error crítico en validación: {str(e)}"],
            "advertencias": [],
            "datos_corregidos": True,
            "respuesta_validada": {
                "estampillas_generales": _obtener_estampillas_default(),
                "resumen_analisis": {
                    "total_estampillas_identificadas": 0,
                    "estampillas_completas": 0,
                    "estampillas_incompletas": 0,
                    "estampillas_no_aplican": 6,
                    "documentos_revisados": ["ERROR"]
                }
            }
        }

def presentar_resultado_estampillas_generales(respuesta_validada: Dict[str, Any]) -> Dict[str, Any]:
    """
     Presenta toda la información de estampillas generales en el formato correcto para el JSON final.
    
    Args:
        respuesta_validada: Respuesta ya validada de Gemini
        
    Returns:
        Dict con formato final para resultado_final.json
    """
    logger.info(" Presentando resultado final de estampillas generales")
    
    try:
        # Extraer datos principales
        estampillas = respuesta_validada.get("estampillas_generales", [])

        # Calcular contadores para logging (sin incluir en resultado final)
        completas = sum(1 for e in estampillas if e.get("estado") == "preliquidado")
        incompletas = sum(1 for e in estampillas if e.get("estado") == "preliquidacion_sin_finalizar")

        # Crear resultado final estructurado (SIMPLIFICADO - SIN RESUMEN)
        resultado_final = {
            "estampillas_generales": {
                "procesamiento_exitoso": True,
                "fecha_procesamiento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_estampillas_analizadas": 6,
                "estampillas": {}
            }
        }

        # Procesar cada estampilla SOLO UNA VEZ (sin duplicar)
        for estampilla in estampillas:
            nombre = estampilla.get("nombre_estampilla", "Desconocida")
            estado = estampilla.get("estado", "no_aplica_impuesto")

            # Estructura individual por estampilla (SIMPLIFICADA)
            detalle_estampilla = {
                "nombre": nombre,
                "aplica": estado in ["preliquidado", "preliquidacion_sin_finalizar"],
                "estado": estado,
                "informacion_identificada": {
                    "porcentaje": round(estampilla.get("porcentaje") / 100, 8), # Convertir a decimal
                    "valor_base": estampilla.get("valor_base", 0.0),
                    "valor_pesos": estampilla.get("valor"),
                    "fuente_informacion": estampilla.get("texto_referencia")
                },
                "observaciones": estampilla.get("observaciones"),
                "requiere_atencion": estado == "preliquidacion_sin_finalizar"
            }

            # Agregar SOLO a estructura por nombre (sin duplicar en lista)
            nombre_clave = nombre.lower().replace(" ", "_").replace("ó", "o").replace("é", "e")
            resultado_final["estampillas_generales"]["estampillas"][nombre_clave] = detalle_estampilla

        # Agregar observaciones generales si hay estampillas incompletas
        observaciones_generales = []
        if incompletas > 0:
            observaciones_generales.append(f"Se encontraron {incompletas} estampillas con información incompleta")
            observaciones_generales.append("Revise los documentos para obtener porcentajes y valores faltantes")

        if completas > 0:
            observaciones_generales.append(f"Se identificaron correctamente {completas} estampillas con información completa")

        resultado_final["estampillas_generales"]["observaciones_generales"] = observaciones_generales

        # Log informativo
        logger.info(f" Resultado final presentado - {completas} completas, {incompletas} incompletas")

        return resultado_final
        
    except Exception as e:
        logger.error(f" Error presentando resultado de estampillas: {e}")
        return {
            "estampillas_generales": {
                "procesamiento_exitoso": False,
                "fecha_procesamiento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(e),
                "observaciones_generales": [
                    "Error procesando estampillas generales",
                    "Contacte al administrador del sistema"
                ]
            }
        }

# ===============================
# FUNCIONES AUXILIARES
# ===============================

def _validar_estampilla_individual(estampilla: Dict[str, Any], indice: int) -> List[str]:
    """
    Valida formato y tipos de datos de una estampilla individual.

    NOTA: Solo valida formato. La asignación de estados se hace en _asignar_estado_estampilla().

    Validaciones aplicadas:
    - Campo obligatorio: nombre_estampilla
    - Tipos de datos numéricos correctos para porcentaje, valor_base, valor
    - Asigna valores default (0) si faltan campos numéricos

    Args:
        estampilla: Datos de la estampilla (puede ser modificado para agregar defaults)
        indice: Índice en la lista

    Returns:
        Lista de errores encontrados
    """
    errores = []

    # Validar campo obligatorio
    if "nombre_estampilla" not in estampilla or not estampilla["nombre_estampilla"]:
        errores.append(f"Estampilla {indice}: 'nombre_estampilla' faltante o vacío")

    # Asignar valores default para campos numéricos si faltan
    if "porcentaje" not in estampilla:
        estampilla["porcentaje"] = 0.0
    if "valor_base" not in estampilla:
        estampilla["valor_base"] = 0.0
    if "valor" not in estampilla:
        estampilla["valor"] = 0.0

    # Validar tipos de datos numéricos
    porcentaje = estampilla.get("porcentaje")
    valor = estampilla.get("valor")
    valor_base = estampilla.get("valor_base")

    if porcentaje is not None and not isinstance(porcentaje, (int, float)):
        errores.append(f"Estampilla {indice}: 'porcentaje' debe ser numérico")
        estampilla["porcentaje"] = 0.0  # Corregir a default

    if valor is not None and not isinstance(valor, (int, float)):
        errores.append(f"Estampilla {indice}: 'valor' debe ser numérico")
        estampilla["valor"] = 0.0  # Corregir a default

    if valor_base is not None and not isinstance(valor_base, (int, float)):
        errores.append(f"Estampilla {indice}: 'valor_base' debe ser numérico")
        estampilla["valor_base"] = 0.0  # Corregir a default

    return errores

def _asignar_estado_estampilla(estampilla: Dict[str, Any]) -> None:
    """
    Asigna el estado de una estampilla según reglas de validación.

    Responsabilidad: Python asigna estados, NO Gemini.

    Reglas aplicadas:
    1. Si valor_base == 0 AND porcentaje == 0 AND valor == 0 → no_aplica_impuesto
    2. Si valor_base > 0 AND porcentaje > 0 AND valor > 0:
       - Validar coherencia matemática
       - Si pasa → preliquidado
       - Si falla → preliquidacion_sin_finalizar
    3. Si valor > 0 → Validar que porcentaje > 0 AND valor_base > 0
    4. Si porcentaje > 0 → Validar que valor > 0 AND valor_base > 0
    5. Si valor_base > 0 → Validar que valor > 0 AND porcentaje > 0

    Args:
        estampilla: Dict con datos de la estampilla (se modifica in-place)

    Returns:
        None (modifica estampilla directamente)
    """
    nombre = estampilla.get("nombre_estampilla", "Desconocida")
    porcentaje = estampilla.get("porcentaje", 0)
    valor_base = estampilla.get("valor_base", 0)
    valor = estampilla.get("valor", 0)

    # Convertir None a 0 si es necesario
    porcentaje = porcentaje if porcentaje is not None else 0
    valor_base = valor_base if valor_base is not None else 0
    valor = valor if valor is not None else 0

    # REGLA 1: Todos en 0 → no_aplica_impuesto
    if valor_base == 0 and porcentaje == 0 and valor == 0:
        estampilla["estado"] = "no_aplica_impuesto"
        logger.info(f"Estado asignado para {nombre}: no_aplica_impuesto (sin información)")
        return

    # REGLA 2: Todos > 0 → Validar matemáticamente
    if valor_base > 0 and porcentaje > 0 and valor > 0:
        # Calcular valor esperado
        valor_esperado = valor_base * (porcentaje / 100)
        diferencia = abs(valor - valor_esperado)

        # Tolerancia de ±1 peso
        if diferencia <= 1:
            estampilla["estado"] = "preliquidado"
            logger.info(
                f"Estado asignado para {nombre}: preliquidado "
                f"(validación matemática correcta: ${valor_base:,.0f} * {porcentaje}% = ${valor:,.0f})"
            )
        else:
            estampilla["estado"] = "preliquidacion_sin_finalizar"
            observacion = (
                f"Incoherencia matemática: base ${valor_base:,.0f} * {porcentaje}% = "
                f"${valor_esperado:,.2f} esperado, pero valor reportado es ${valor:,.0f} "
                f"(diferencia: ${diferencia:,.2f})"
            )
            _agregar_observacion(estampilla, observacion)
            logger.warning(f"Estado asignado para {nombre}: preliquidacion_sin_finalizar - {observacion}")
        return

    # REGLA 3: Si valor > 0 → Validar dependencias
    if valor > 0:
        faltantes = []
        if porcentaje == 0:
            faltantes.append("porcentaje")
        if valor_base == 0:
            faltantes.append("base gravable")

        if faltantes:
            estampilla["estado"] = "preliquidacion_sin_finalizar"
            observacion = f"No se identificó el {' ni el '.join(faltantes)} en los documentos para esta estampilla"
            _agregar_observacion(estampilla, observacion)
            logger.warning(f"Estado asignado para {nombre}: preliquidacion_sin_finalizar - Faltan: {', '.join(faltantes)}")
            return

    # REGLA 4: Si porcentaje > 0 → Validar dependencias
    if porcentaje > 0:
        faltantes = []
        if valor == 0:
            faltantes.append("valor")
        if valor_base == 0:
            faltantes.append("base gravable")

        if faltantes:
            estampilla["estado"] = "preliquidacion_sin_finalizar"
            observacion = f"No se identificó el {' ni el '.join(faltantes)} en los documentos para esta estampilla"
            _agregar_observacion(estampilla, observacion)
            logger.warning(f"Estado asignado para {nombre}: preliquidacion_sin_finalizar - Faltan: {', '.join(faltantes)}")
            return

    # REGLA 5: Si valor_base > 0 → Validar dependencias
    if valor_base > 0:
        faltantes = []
        if valor == 0:
            faltantes.append("valor")
        if porcentaje == 0:
            faltantes.append("porcentaje")

        if faltantes:
            estampilla["estado"] = "preliquidacion_sin_finalizar"
            observacion = f"No se identificó el {' ni el '.join(faltantes)} en los documentos para esta estampilla"
            _agregar_observacion(estampilla, observacion)
            logger.warning(f"Estado asignado para {nombre}: preliquidacion_sin_finalizar - Faltan: {', '.join(faltantes)}")
            return

    # Caso por defecto (no debería llegar aquí, pero por seguridad)
    estampilla["estado"] = "preliquidacion_sin_finalizar"
    _agregar_observacion(estampilla, "Estado indeterminado - revisar información")
    logger.warning(f"Estado asignado para {nombre}: preliquidacion_sin_finalizar (caso por defecto)")

def _agregar_observacion(estampilla: Dict[str, Any], nueva_observacion: str) -> None:
    """
    Agrega o actualiza observaciones en una estampilla.

    Args:
        estampilla: Dict con datos de la estampilla
        nueva_observacion: Observación a agregar

    Returns:
        None (modifica estampilla directamente)
    """
    if estampilla.get("observaciones"):
        estampilla["observaciones"] += f" | {nueva_observacion}"
    else:
        estampilla["observaciones"] = nueva_observacion

def _obtener_estampillas_default() -> List[Dict[str, Any]]:
    """
    Obtiene estructura por defecto para las 6 estampillas.

    NOTA: Los estados se asignan después mediante _asignar_estado_estampilla().

    Returns:
        Lista con estructura por defecto (sin estado)
    """
    estampillas_nombres = [
        "Procultura",
        "Bienestar",
        "Adulto Mayor",
        "Prouniversidad Pedagógica",
        "Francisco José de Caldas",
        "Prodeporte"
    ]

    return [
        {
            "nombre_estampilla": nombre,
            "porcentaje": 0.0,  # Default 0
            "valor_base": 0.0,   # Default 0
            "valor": 0.0,        # Default 0
            "texto_referencia": None,
            "observaciones": None  # Se asignará por _asignar_estado_estampilla()
        }
        for nombre in estampillas_nombres
    ]

def _generar_resumen_automatico(estampillas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Genera resumen automático basado en la lista de estampillas.

    Args:
        estampillas: Lista de estampillas

    Returns:
        Dict con resumen generado
    """
    completas = sum(1 for e in estampillas if e.get("estado") == "preliquidado")
    incompletas = sum(1 for e in estampillas if e.get("estado") == "preliquidacion_sin_finalizar")
    no_aplican = sum(1 for e in estampillas if e.get("estado") == "no_aplica_impuesto")

    return {
        "total_estampillas_identificadas": completas + incompletas,
        "estampillas_completas": completas,
        "estampillas_incompletas": incompletas,
        "estampillas_no_aplican": no_aplican,
        "documentos_revisados": ["FACTURA", "ANEXOS", "ANEXO_CONTRATO", "RUT"]
    }

# ===============================
# FUNCIÓN DE DIAGNÓSTICO
# ===============================

def diagnosticar_estampillas_generales() -> Dict[str, Any]:
    """
    Función de diagnóstico para verificar el estado del módulo.
    
    Returns:
        Dict con información de diagnóstico
    """
    try:
        # Probar creación de modelos
        estampilla_test = EstampillaGeneral(
            nombre_estampilla="Test",
            estado="no_aplica_impuesto"
        )
        
        resumen_test = ResumenAnalisisEstampillas(
            total_estampillas_identificadas=0,
            estampillas_completas=0,
            estampillas_incompletas=0,
            estampillas_no_aplican=6,
            documentos_revisados=["TEST"]
        )
        
        resultado_test = ResultadoEstampillasGenerales(
            estampillas_generales=[estampilla_test],
            resumen_analisis=resumen_test
        )
        
        return {
            "estado": "OK",
            "modulos_funcionando": True,
            "pydantic_models": "OK",
            "funciones_principales": ["validar_formato_estampillas_generales", "presentar_resultado_estampillas_generales"],
            "estampillas_soportadas": 6,
            "nombres_estampillas": [
                "Procultura", "Bienestar", "Adulto Mayor",
                "Prouniversidad Pedagógica", "Francisco José de Caldas", "Prodeporte"
            ],
            "fecha_diagnostico": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except Exception as e:
        return {
            "estado": "ERROR",
            "error": str(e),
            "fecha_diagnostico": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
