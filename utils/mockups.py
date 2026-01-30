"""
MÓDULO MOCKUPS - RESPUESTAS ESTRUCTURADAS PARA VALIDACIONES

SRP: Responsabilidad única de generar respuestas mock cuando validaciones fallan
OCP: Fácil agregar nuevos impuestos sin modificar código existente
DIP: No depende de implementaciones concretas, solo retorna estructuras de datos

Autor: Miguel Angel Jaramillo Durango
Versión: 2.9.4
"""

from datetime import datetime
from typing import Dict, List, Any


def _crear_mock_retefuente(codigo_negocio: int) -> Dict:
    """
    Crea estructura mock para Retención en la Fuente cuando código no parametrizado.

    Args:
        codigo_negocio: Código del negocio no encontrado

    Returns:
        dict: Estructura estándar de retefuente con aplica=False
    """
    mensaje = f"el código de negocio {codigo_negocio} no esta parametrizado, no aplica impuesto"

    return {
        "aplica": False,
        "estado": "no_aplica_impuesto",
        "valor_factura_sin_iva": 0.0,
        "valor_retencion": 0,
        "valor_base": 0,
        "conceptos_aplicados": [],
        "observaciones": [mensaje]
    }


def _crear_mock_estampilla_universidad(codigo_negocio: int) -> Dict:
    """
    Crea estructura mock para Estampilla Pro Universidad Nacional cuando código no parametrizado.

    Args:
        codigo_negocio: Código del negocio no encontrado

    Returns:
        dict: Estructura estándar de estampilla universidad con aplica=False
    """
    mensaje = f"el código de negocio {codigo_negocio} no esta parametrizado, no aplica impuesto"

    return {
        "aplica": False,
        "estado": "no_aplica_impuesto",
        "valor_estampilla": 0,
        "tarifa_aplicada": 0,
        "valor_factura_sin_iva": 0,
        "rango_uvt": "",
        "valor_contrato_pesos": 0,
        "valor_contrato_uvt": 0,
        "mensajes_error": [mensaje],
        "razon": mensaje
    }


def _crear_mock_contribucion_obra_publica(codigo_negocio: int) -> Dict:
    """
    Crea estructura mock para Contribución a Obra Pública 5% cuando código no parametrizado.

    Args:
        codigo_negocio: Código del negocio no encontrado

    Returns:
        dict: Estructura estándar de obra pública con aplica=False
    """
    mensaje = f"el código de negocio {codigo_negocio} no esta parametrizado, no aplica impuesto"

    return {
        "aplica": False,
        "estado": "no_aplica_impuesto",
        "tarifa_aplicada": 0.0,
        "valor_contribucion": 0,
        "valor_factura_sin_iva": 0,
        "mensajes_error": [mensaje],
        "razon": mensaje
    }


def _crear_mock_iva_reteiva(codigo_negocio: int) -> Dict:
    """
    Crea estructura mock para IVA y ReteIVA cuando código no parametrizado.

    Args:
        codigo_negocio: Código del negocio no encontrado

    Returns:
        dict: Estructura estándar de IVA/ReteIVA con aplica=False
    """
    mensaje = f"el código de negocio {codigo_negocio} no esta parametrizado, no aplica impuesto"

    return {
        "aplica": False,
        "valor_iva_identificado": 0.0,
        "valor_subtotal_sin_iva": 0.0,
        "valor_reteiva": 0.0,
        "porcentaje_iva": 0.0,
        "tarifa_reteiva": 0.0,
        "es_fuente_nacional": False,
        "estado_liquidacion": "no_aplica_impuesto",
        "es_responsable_iva": False,
        "observaciones": [mensaje],
        "calculo_exitoso": True
    }


def _crear_mock_estampilla_individual(nombre: str, codigo_negocio: int) -> Dict:
    """
    Crea estructura mock para una estampilla general individual.

    Args:
        nombre: Nombre de la estampilla
        codigo_negocio: Código del negocio no encontrado

    Returns:
        dict: Estructura individual de estampilla con aplica=False
    """
    mensaje = f"el código de negocio {codigo_negocio} no esta parametrizado, no aplica impuesto"

    return {
        "nombre": nombre,
        "aplica": False,
        "estado": "no_aplica_impuesto",
        "informacion_identificada": {
            "porcentaje": 0,
            "valor_base": 0,
            "valor_pesos": 0,
            "fuente_informacion": None
        },
        "observaciones": mensaje,
        "requiere_atencion": False
    }


def _crear_mock_estampillas_generales(codigo_negocio: int) -> Dict:
    """
    Crea estructura mock para las 6 Estampillas Generales cuando código no parametrizado.

    Args:
        codigo_negocio: Código del negocio no encontrado

    Returns:
        dict: Estructura completa de estampillas generales con todas marcadas como no aplica
    """
    return {
        "estampillas_generales": {
            "procesamiento_exitoso": False,
            "fecha_procesamiento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_estampillas_analizadas": 0,
            "procultura": _crear_mock_estampilla_individual("Procultura", codigo_negocio),
            "bienestar": _crear_mock_estampilla_individual("Bienestar", codigo_negocio),
            "adulto_mayor": _crear_mock_estampilla_individual("Adulto Mayor", codigo_negocio),
            "prouniversidad_pedagogica": _crear_mock_estampilla_individual(
                "Prouniversidad Pedagógica", codigo_negocio
            ),
            "francisco_jose_de_caldas": _crear_mock_estampilla_individual(
                "Francisco José de Caldas", codigo_negocio
            ),
            "prodeporte": _crear_mock_estampilla_individual("Prodeporte", codigo_negocio)
        },
        "observaciones_generales": []
    }


def _crear_mock_ica(codigo_negocio: int) -> Dict:
    """
    Crea estructura mock para ICA (Impuesto de Industria y Comercio) cuando código no parametrizado.

    Nota: ICA tiene aplica=True pero estado='no_aplica_impuesto' en el output esperado.

    Args:
        codigo_negocio: Código del negocio no encontrado

    Returns:
        dict: Estructura estándar de ICA con estado no_aplica_impuesto
    """
    mensaje = f"el código de negocio {codigo_negocio} no esta parametrizado, no aplica impuesto"

    return {
        "aplica": False,
        "estado": "no_aplica_impuesto",
        "valor_total_ica": 0.0,
        "actividades_facturadas": [],
        "actividades_relacionadas": [],
        "valor_factura_sin_iva": 0.0,
        "observaciones": [mensaje],
        "fecha_liquidacion": datetime.now().isoformat()
    }


def _crear_mock_sobretasa_bomberil(codigo_negocio: int) -> Dict:
    """
    Crea estructura mock para Sobretasa Bomberil cuando código no parametrizado.

    Nota: observaciones es string directo (no lista).

    Args:
        codigo_negocio: Código del negocio no encontrado

    Returns:
        dict: Estructura estándar de sobretasa bomberil con aplica=False
    """
    mensaje = f"el código de negocio {codigo_negocio} no esta parametrizado, no aplica impuesto"

    return {
        "aplica": False,
        "estado": "no_aplica_impuesto",
        "valor_total_sobretasa": 0,
        "ubicaciones": [],
        "observaciones": mensaje,
        "fecha_liquidacion": datetime.now().isoformat()
    }


def _crear_mock_timbre(codigo_negocio: int) -> Dict:
    """
    Crea estructura mock para Impuesto al Timbre cuando código no parametrizado.

    Nota: observaciones es string directo (no lista).

    Args:
        codigo_negocio: Código del negocio no encontrado

    Returns:
        dict: Estructura estándar de timbre con aplica=False
    """
    mensaje = f"el código de negocio {codigo_negocio} no esta parametrizado, no aplica impuesto"

    return {
        "aplica": False,
        "estado": "no_aplica_impuesto",
        "valor": 0,
        "tarifa": 0,
        "tipo_cuantia": "",
        "base_gravable": 0,
        "ID_contrato": "",
        "observaciones": mensaje
    }


def _crear_mock_tasa_prodeporte(codigo_negocio: int) -> Dict:
    """
    Crea estructura mock para Tasa Prodeporte cuando código no parametrizado.

    Nota: observaciones es string directo (no lista).

    Args:
        codigo_negocio: Código del negocio no encontrado

    Returns:
        dict: Estructura estándar de tasa prodeporte con aplica=False
    """
    mensaje = f"el código de negocio {codigo_negocio} no esta parametrizado, no aplica impuesto"

    return {
        "estado": "no_aplica_impuesto",
        "aplica": False,
        "valor_imp": 0,
        "tarifa": 0,
        "valor_convenio_sin_iva": 0,
        "porcentaje_convenio": 0,
        "valor_contrato_municipio": 0,
        "factura_sin_iva": 0,
        "factura_con_iva": 0,
        "municipio_dept": "",
        "numero_contrato": "",
        "observaciones": mensaje,
        "fecha_calculo": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def crear_respuesta_negocio_no_parametrizado(codigo_del_negocio: int) -> Dict:
    """
    Crea respuesta completa cuando código de negocio no está parametrizado en base de datos.

    ARQUITECTURA SOLID:
    - SRP: Responsabilidad única de generar estructura de respuesta mock
    - OCP: Abierto para extensión (agregar nuevos impuestos)
    - DIP: No depende de implementaciones, solo genera datos

    Esta función se usa cuando la validación de código de negocio falla, permitiendo
    retornar una respuesta estructurada (200 OK) en lugar de un error HTTP (400).

    Args:
        codigo_del_negocio: Código del negocio consultado que no se encontró

    Returns:
        dict: Estructura JSONResponse completa con todos los impuestos marcados como no aplica

    Example:
        >>> respuesta = crear_respuesta_negocio_no_parametrizado(9003)
        >>> respuesta['impuestos']['retefuente']['aplica']
        False
        >>> respuesta['impuestos']['retefuente']['estado']
        'no_aplica_impuesto'
    """
    return {
        "impuestos_procesados": [],
        "nit_administrativo": "0",
        "nombre_entidad": "",
        "timestamp": datetime.now().isoformat(),
        "version": "2.9.3",
        "impuestos": {
            "retefuente": _crear_mock_retefuente(codigo_del_negocio),
            "estampilla_universidad": _crear_mock_estampilla_universidad(codigo_del_negocio),
            "contribucion_obra_publica": _crear_mock_contribucion_obra_publica(codigo_del_negocio),
            "iva_reteiva": _crear_mock_iva_reteiva(codigo_del_negocio),
            "estampillas_generales": _crear_mock_estampillas_generales(codigo_del_negocio),
            "ica": _crear_mock_ica(codigo_del_negocio),
            "sobretasa_bomberil": _crear_mock_sobretasa_bomberil(codigo_del_negocio),
            "timbre": _crear_mock_timbre(codigo_del_negocio),
            "tasa_prodeporte": _crear_mock_tasa_prodeporte(codigo_del_negocio)
        },
        "resumen_total": {
            "valor_total_impuestos": 0.0,
            "impuestos_liquidados": [],
            "procesamiento_exitoso": True
        },
        "timestamp_procesamiento": datetime.now().isoformat(),
        "es_consorcio": False,
        "es_facturacion_extranjera": False,
        "documentos_procesados": 0,
        "documentos_clasificados": [],
        "version_sistema": "2.4.0",
        "modulos_utilizados": ["Extraccion", "Clasificador", "Liquidador"]
    }


def crear_respuesta_error_validacion(
    errores_validacion: List[Dict[str, Any]],
    url_request: str = "",
    metodo_http: str = "POST"
) -> Dict:
    """
    Crea respuesta completa cuando hay errores de validación de parámetros FastAPI.

    ARQUITECTURA SOLID:
    - SRP: Responsabilidad única de generar estructura mock para errores de validación
    - OCP: Reutiliza funciones existentes sin modificarlas
    - DIP: No depende de implementaciones, solo genera datos

    Esta función se usa cuando la validación de parámetros Pydantic falla (error 422),
    permitiendo retornar una respuesta estructurada (200 OK) en lugar de error HTTP.

    Args:
        errores_validacion: Lista de errores extraídos por error_handlers.py
        url_request: URL del request que generó el error
        metodo_http: Método HTTP usado (GET, POST, etc.)

    Returns:
        dict: Estructura JSONResponse completa con todos los impuestos marcados como no aplica

    Example:
        >>> errores = [{"campo": "codigo_del_negocio", "tipo_error": "type_error.integer", ...}]
        >>> respuesta = crear_respuesta_error_validacion(errores)
        >>> respuesta['impuestos']['retefuente']['aplica']
        False
        >>> respuesta['impuestos']['retefuente']['observaciones'][0]
        "Error de validación: El parámetro 'codigo_del_negocio' debe ser un número..."
    """
    # Generar mensaje principal de error
    mensaje_error_principal = _generar_mensaje_error_desde_lista(errores_validacion)

    # Mensaje de observación principal
    mensaje_observacion = (
        f"Error de validación de parámetros: {mensaje_error_principal}. "
        f"Revise los tipos de datos enviados en la solicitud."
    )

    return {
        "impuestos_procesados": [],
        "nit_administrativo": "0",
        "nombre_entidad": "",
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0",
        "estado_procesamiento": "preliquidacion_sin_finalzar",
        "errores_validacion": {
            "detectados": True,
            "cantidad_errores": len(errores_validacion),
            "url_request": url_request,
            "metodo_http": metodo_http,
            "timestamp_error": datetime.now().isoformat(),
            "errores_detallados": errores_validacion,
            "mensaje_principal": mensaje_error_principal
        },
        "impuestos": {
            "retefuente": _crear_mock_retefuente_validacion(mensaje_observacion),
            "estampilla_universidad": _crear_mock_estampilla_universidad_validacion(mensaje_observacion),
            "contribucion_obra_publica": _crear_mock_contribucion_obra_publica_validacion(mensaje_observacion),
            "iva_reteiva": _crear_mock_iva_reteiva_validacion(mensaje_observacion),
            "estampillas_generales": _crear_mock_estampillas_generales_validacion(mensaje_observacion),
            "ica": _crear_mock_ica_validacion(mensaje_observacion),
            "sobretasa_bomberil": _crear_mock_sobretasa_bomberil_validacion(mensaje_observacion),
            "timbre": _crear_mock_timbre_validacion(mensaje_observacion),
            "tasa_prodeporte": _crear_mock_tasa_prodeporte_validacion(mensaje_observacion)
        },
        "resumen_total": {
            "valor_total_impuestos": 0.0,
            "impuestos_liquidados": [],
            "procesamiento_exitoso": False,
            "razon_fallo": "preliquidacion_sin_finalzar"
        },
        "timestamp_procesamiento": datetime.now().isoformat(),
        "es_consorcio": False,
        "es_facturacion_extranjera": False,
        "documentos_procesados": 0,
        "documentos_clasificados": [],
        "version_sistema": "3.0.0",
        "modulos_utilizados": ["ErrorHandlers"]
    }


def _generar_mensaje_error_desde_lista(errores: List[Dict[str, Any]]) -> str:
    """
    Genera mensaje consolidado de múltiples errores de validación.

    SRP: Responsabilidad única de formatear mensajes de error

    Args:
        errores: Lista de errores estructurados

    Returns:
        str: Mensaje consolidado
    """
    if not errores:
        return "Error de validación desconocido"

    if len(errores) == 1:
        error = errores[0]
        campo = error["campo"].replace("body.", "")
        return f"El parámetro '{campo}' tiene un valor inválido"
    else:
        campos = [e["campo"].replace("body.", "") for e in errores]
        return f"Múltiples parámetros con valores inválidos: {', '.join(campos)}"


# ============================================
# FUNCIONES AUXILIARES PARA MOCKS DE VALIDACIÓN
# ============================================

def _crear_mock_retefuente_validacion(mensaje: str) -> Dict:
    """Mock de retefuente para errores de validación"""
    return {
        "aplica": False,
        "estado": "preliquidacion_sin_finalizar",
        "valor_factura_sin_iva": 0.0,
        "valor_retencion": 0,
        "valor_base": 0,
        "conceptos_aplicados": [],
        "observaciones": [mensaje]
    }


def _crear_mock_estampilla_universidad_validacion(mensaje: str) -> Dict:
    """Mock de estampilla universidad para errores de validación"""
    return {
        "aplica": False,
        "estado": "preliquidacion_sin_finalzar",
        "valor_estampilla": 0,
        "tarifa_aplicada": 0,
        "valor_factura_sin_iva": 0,
        "rango_uvt": "",
        "valor_contrato_pesos": 0,
        "valor_contrato_uvt": 0,
        "mensajes_error": [mensaje],
        "razon": mensaje
    }


def _crear_mock_contribucion_obra_publica_validacion(mensaje: str) -> Dict:
    """Mock de obra pública para errores de validación"""
    return {
        "aplica": False,
        "estado": "preliquidacion_sin_finalzar",
        "tarifa_aplicada": 0.0,
        "valor_contribucion": 0,
        "valor_factura_sin_iva": 0,
        "mensajes_error": [mensaje],
        "razon": mensaje
    }


def _crear_mock_iva_reteiva_validacion(mensaje: str) -> Dict:
    """Mock de IVA/ReteIVA para errores de validación"""
    return {
        "aplica": False,
        "valor_iva_identificado": 0.0,
        "valor_subtotal_sin_iva": 0.0,
        "valor_reteiva": 0.0,
        "porcentaje_iva": 0.0,
        "tarifa_reteiva": 0.0,
        "es_fuente_nacional": False,
        "estado_liquidacion": "preliquidacion_sin_finalzar",
        "es_responsable_iva": False,
        "observaciones": [mensaje],
        "calculo_exitoso": False
    }


def _crear_mock_estampillas_generales_validacion(mensaje: str) -> Dict:
    """Mock de estampillas generales para errores de validación"""
    def crear_estampilla_individual(nombre: str) -> Dict:
        return {
            "nombre": nombre,
            "aplica": False,
            "estado": "preliquidacion_sin_finalzar",
            "informacion_identificada": {
                "porcentaje": 0,
                "valor_base": 0,
                "valor_pesos": 0,
                "fuente_informacion": None
            },
            "observaciones": mensaje,
            "requiere_atencion": False
        }

    return {
        "estampillas_generales": {
            "procesamiento_exitoso": False,
            "fecha_procesamiento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_estampillas_analizadas": 0,
            "procultura": crear_estampilla_individual("Procultura"),
            "bienestar": crear_estampilla_individual("Bienestar"),
            "adulto_mayor": crear_estampilla_individual("Adulto Mayor"),
            "prouniversidad_pedagogica": crear_estampilla_individual("Prouniversidad Pedagógica"),
            "francisco_jose_de_caldas": crear_estampilla_individual("Francisco José de Caldas"),
            "prodeporte": crear_estampilla_individual("Prodeporte")
        },
        "observaciones_generales": [mensaje]
    }


def _crear_mock_ica_validacion(mensaje: str) -> Dict:
    """Mock de ICA para errores de validación"""
    return {
        "aplica": False,
        "estado": "preliquidacion_sin_finalzar",
        "valor_total_ica": 0.0,
        "actividades_facturadas": [],
        "actividades_relacionadas": [],
        "valor_factura_sin_iva": 0.0,
        "observaciones": [mensaje],
        "fecha_liquidacion": datetime.now().isoformat()
    }


def _crear_mock_sobretasa_bomberil_validacion(mensaje: str) -> Dict:
    """Mock de sobretasa bomberil para errores de validación"""
    return {
        "aplica": False,
        "estado": "preliquidacion_sin_finalzar",
        "valor_total_sobretasa": 0,
        "ubicaciones": [],
        "observaciones": mensaje,
        "fecha_liquidacion": datetime.now().isoformat()
    }


def _crear_mock_timbre_validacion(mensaje: str) -> Dict:
    """Mock de timbre para errores de validación"""
    return {
        "aplica": False,
        "estado": "preliquidacion_sin_finalzar",
        "valor": 0,
        "tarifa": 0,
        "tipo_cuantia": "",
        "base_gravable": 0,
        "ID_contrato": "",
        "observaciones": mensaje
    }


def _crear_mock_tasa_prodeporte_validacion(mensaje: str) -> Dict:
    """Mock de tasa prodeporte para errores de validación"""
    return {
        "estado": "preliquidacion_sin_finalzar",
        "aplica": False,
        "valor_imp": 0,
        "tarifa": 0,
        "valor_convenio_sin_iva": 0,
        "porcentaje_convenio": 0,
        "valor_contrato_municipio": 0,
        "factura_sin_iva": 0,
        "factura_con_iva": 0,
        "municipio_dept": "",
        "numero_contrato": "",
        "observaciones": mensaje,
        "fecha_calculo": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
