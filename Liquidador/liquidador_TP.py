"""
LIQUIDADOR TASA PRODEPORTE
===========================

Responsabilidad SRP: Solo liquidacion y validaciones manuales de Tasa Prodeporte.
Implementa TODA la logica de negocio con validaciones manuales en Python.

Arquitectura: Separacion IA-Validacion
- Gemini: Solo identificacion de datos
- Python: Todas las validaciones, calculos y logica de negocio

"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from pydantic import BaseModel
import unicodedata

if TYPE_CHECKING:
    from database.database import DatabaseInterface

# Configuracion de logging
logger = logging.getLogger(__name__)

# ===============================
# MODELOS DE DATOS PYDANTIC
# ===============================

class ParametrosTasaProdeporte(BaseModel):
    """
    Modelo Pydantic para los parametros de entrada del endpoint.

    SRP: Solo estructura de parametros de entrada
    """
    observaciones: Optional[str] = None
    genera_presupuesto: Optional[str] = None
    rubro: Optional[str] = None
    centro_costos: Optional[int] = None
    numero_contrato: Optional[str] = None
    valor_contrato_municipio: Optional[float] = None


class ResultadoTasaProdeporte(BaseModel):
    """
    Modelo Pydantic para el resultado de la liquidacion.

    SRP: Solo estructura de resultado
    """
    estado: str  # "preliquidado" | "preliquidacion_sin_finalizar" | "no_aplica_impuesto"
    aplica: bool
    valor_imp: float = 0.0
    tarifa: float = 0.0
    valor_convenio_sin_iva: float = 0.0
    porcentaje_convenio: float = 0.0
    valor_contrato_municipio: float = 0.0
    factura_sin_iva: float = 0.0
    factura_con_iva: float = 0.0
    municipio_dept: str = ""
    numero_contrato: str = ""
    observaciones: str = ""
    fecha_calculo: str = ""


# ===============================
# CLASE LIQUIDADOR
# ===============================

class LiquidadorTasaProdeporte:
    """
    Liquidador de Tasa Prodeporte con validaciones manuales Python.

    SRP: Solo liquidacion de Tasa Prodeporte
    Toda la logica de negocio esta en Python, no en Gemini
    """

    def __init__(self, db_interface: 'DatabaseInterface'):
        """
        Inicializa liquidador con inyeccion de dependencias.

        DIP: Depende de abstraccion DatabaseInterface, no de implementacion.
        OCP: Permite cambiar implementacion de BD sin modificar liquidador.

        Args:
            db_interface: Instancia de DatabaseInterface (Supabase/Nexura)

        Raises:
            ValueError: Si db_interface es None
        """
        if db_interface is None:
            raise ValueError(
                "LiquidadorTasaProdeporte requiere db_interface. "
                "Pase una instancia de DatabaseInterface."
            )

        self.db = db_interface
        logger.info("LiquidadorTasaProdeporte inicializado con DatabaseInterface")

    def normalizar_texto(self, texto: str) -> str:
        """
        Normaliza un texto removiendo acentos y convirtiendolo a minusculas.

        SRP: Solo normalizacion de texto

        Args:
            texto: Texto a normalizar

        Returns:
            str: Texto normalizado
        """
        if not texto:
            return ""

        # Convertir a minusculas
        texto_lower = texto.lower()

        # Remover acentos
        texto_normalizado = ''.join(
            c for c in unicodedata.normalize('NFD', texto_lower)
            if unicodedata.category(c) != 'Mn'
        )

        return texto_normalizado.strip()

    def validar_parametros_completos(self, parametros: ParametrosTasaProdeporte) -> tuple[bool, List[str]]:
        """
        Valida que TODOS los parametros opcionales esten presentes.

        SRP: Solo validacion de completitud de parametros

        Args:
            parametros: Parametros de entrada

        Returns:
            tuple: (son_completos, lista_campos_faltantes)
        """
        campos_faltantes = []

        if not parametros.observaciones or parametros.observaciones.strip() == "":
            campos_faltantes.append("observaciones")

        if not parametros.genera_presupuesto or parametros.genera_presupuesto.strip() == "":
            campos_faltantes.append("genera_presupuesto")

        if parametros.rubro is None:
            campos_faltantes.append("rubro")

        if parametros.centro_costos is None:
            campos_faltantes.append("centro_costos")

        if not parametros.numero_contrato or parametros.numero_contrato.strip() == "":
            campos_faltantes.append("numero_contrato")

        if parametros.valor_contrato_municipio is None or parametros.valor_contrato_municipio <= 0:
            campos_faltantes.append("valor_contrato_municipio")

        if campos_faltantes:
            return False, campos_faltantes

        return True, []

    def liquidar(self, parametros: ParametrosTasaProdeporte, analisis_gemini: Dict[str, Any]) -> ResultadoTasaProdeporte:
        """
        Liquida Tasa Prodeporte con validaciones manuales Python.

        SRP: Solo coordina el flujo de liquidacion

        FLUJO DE VALIDACIONES MANUALES:
        0. Verificar si hay error en el analisis de Gemini
        1. Validar parametros completos
        2. Formatear datos
        3. Validar aplica_tasa_prodeporte (Gemini)
        4. Validar factura_sin_iva > 0
        5. Validar genera_presupuesto == "si"
        6. Validar primeros 2 digitos rubro == "28"
        7. Validar rubro existe en diccionario
        8. Extraer tarifa, centro_costo, municipio
        9. Validar centro_costos (advertencia si no coincide)
        10. Calcular porcentaje_convenio, valor_convenio_sin_iva
        11. Calcular valor tasa prodeporte

        Args:
            parametros: Parametros de entrada del endpoint
            analisis_gemini: Resultado del analisis de Gemini

        Returns:
            ResultadoTasaProdeporte: Resultado de la liquidacion
        """
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        resultado = ResultadoTasaProdeporte(
            estado="preliquidacion_sin_finalizar",
            aplica=False,
            numero_contrato=parametros.numero_contrato or "",
            fecha_calculo=fecha_actual
        )

        try:
            # VALIDACION 0: Verificar si hay error en el analisis de Gemini
            if "error" in analisis_gemini:
                error_gemini = analisis_gemini.get("error", "Error desconocido en el analisis")
                resultado.estado = "preliquidacion_sin_finalizar"
                resultado.observaciones = f"Error en el procesamiento de Tasa Prodeporte: {error_gemini}"
                logger.error(f"Tasa Prodeporte: Error en analisis de Gemini - {error_gemini}")
                return resultado

            # VALIDACION 1: Parametros completos
            parametros_completos, campos_faltantes = self.validar_parametros_completos(parametros)

            if not parametros_completos:
                resultado.estado = "no_aplica_impuesto"
                resultado.observaciones = f"Faltan los siguientes campos requeridos: {', '.join(campos_faltantes)}"
                logger.warning(f"Tasa Prodeporte: Faltan campos - {campos_faltantes}")
                return resultado

            # VALIDACION 2: Formatear datos
            genera_presupuesto_normalizado = self.normalizar_texto(parametros.genera_presupuesto)
            rubro_str = str(parametros.rubro)

            logger.info(f"Procesando Tasa Prodeporte - Contrato: {parametros.numero_contrato}")

            # VALIDACION 3: Aplica tasa prodeporte (segun Gemini)
            aplica_tasa_gemini = analisis_gemini.get("aplica_tasa_prodeporte", False)

            if not aplica_tasa_gemini:
                resultado.estado = "no_aplica_impuesto"
                resultado.observaciones = "El campo observaciones no menciona la aplicacion de Tasa Pro deporte"
                logger.info("Tasa Prodeporte: No se menciona en observaciones")
                return resultado

            # VALIDACION 4: Factura sin IVA > 0
            factura_sin_iva = analisis_gemini.get("factura_sin_iva", 0.0)
            factura_con_iva = analisis_gemini.get("factura_con_iva", 0.0)
            iva = analisis_gemini.get("iva", 0.0)

            # Intentar calcular si no se identifico
            if factura_sin_iva <= 0:
                if factura_con_iva > 0 and iva > 0:
                    factura_sin_iva = factura_con_iva - iva
                    logger.info(f"Factura sin IVA calculada: ${factura_sin_iva:,.2f}")

            if factura_sin_iva <= 0:
                resultado.estado = "preliquidacion_sin_finalizar"
                resultado.observaciones = "No se pudo identificar el valor de la factura sin IVA"
                logger.warning("Tasa Prodeporte: Factura sin IVA no identificada")
                return resultado

            # VALIDACION 5: Genera presupuesto == "si"
            if genera_presupuesto_normalizado != "si":
                resultado.estado = "no_aplica_impuesto"
                resultado.observaciones = "La transaccion no genera Presupuesto"
                logger.info(f"Tasa Prodeporte: No genera presupuesto ({parametros.genera_presupuesto})")
                return resultado
            
            logger.info("Genera presupuesto confirmado marcado como si ")
            
            # VALIDACION 6: Primeros 2 digitos del rubro == "28"
            if not rubro_str.startswith("28"):
                resultado.estado = "no_aplica_impuesto"
                resultado.observaciones = f"El codigo del rubro presupuestal no inicia con 28: {rubro_str}"
                logger.info(f"Tasa Prodeporte: Rubro no inicia con 28 ({rubro_str})")
                return resultado
            
            logger.info(f"Rubro presupuestal valido: {rubro_str} incia con 28 ")


            # VALIDACION 7+8 COMBINADAS: Consultar rubro en Base de Datos
            logger.info(f"Consultando rubro presupuestal {rubro_str} en Base de Datos...")

            respuesta_bd = self.db.obtener_datos_rubro_tasa_prodeporte(rubro_str)

            if not respuesta_bd['success']:
                # Rubro no encontrado o error de BD
                resultado.estado = "preliquidacion_sin_finalizar"
                resultado.observaciones = respuesta_bd['message']
                logger.warning(
                    f"Tasa Prodeporte: Rubro {rubro_str} no encontrado. "
                    f"Razon: {respuesta_bd['message']}"
                )
                return resultado

            # Extraer datos validados de la BD
            datos_rubro = respuesta_bd['data']
            tarifa = datos_rubro['tarifa']
            centro_costo_esperado = datos_rubro['centro_costo']
            municipio_dict = datos_rubro['municipio_departamento']

            logger.info(
                f"Rubro {rubro_str} encontrado -> "
                f"Tarifa: {tarifa*100}%, Centro: {centro_costo_esperado}, "
                f"Municipio: '{municipio_dict}'"
            )

            # VALIDACION 9: Validar centro de costos (advertencia si no coincide)
            advertencias = []
            if parametros.centro_costos != centro_costo_esperado:
                advertencia = f"Incongruencia: Centro de costos recibido ({parametros.centro_costos}) " \
                            f"no coincide con el esperado ({centro_costo_esperado})"
                advertencias.append(advertencia)
                logger.warning(f"Tasa Prodeporte: {advertencia}")

            # VALIDACION 10: Calcular porcentaje convenio y valor convenio sin IVA
            porcentaje_convenio = parametros.valor_contrato_municipio / factura_con_iva
            valor_convenio_sin_iva = factura_sin_iva * porcentaje_convenio

            logger.info(f"Porcentaje convenio: {porcentaje_convenio*100:.2f}%")
            logger.info(f"Valor convenio sin IVA: ${valor_convenio_sin_iva:,.2f}")

            # VALIDACION 11: Calcular valor tasa prodeporte
            valor_tasa_prodeporte = valor_convenio_sin_iva * tarifa

            logger.info(f"Tasa Prodeporte calculada: ${valor_tasa_prodeporte:,.2f} ({tarifa*100}%)")

            # Determinar municipio final (Gemini o diccionario)
            municipio_gemini = analisis_gemini.get("municipio_identificado", "")
            municipio_final = municipio_gemini if municipio_gemini else municipio_dict

            # RESULTADO EXITOSO
            resultado.estado = "preliquidado"
            resultado.aplica = True
            resultado.valor_imp = valor_tasa_prodeporte
            resultado.tarifa = tarifa
            resultado.valor_convenio_sin_iva = valor_convenio_sin_iva
            resultado.porcentaje_convenio = porcentaje_convenio
            resultado.valor_contrato_municipio = parametros.valor_contrato_municipio
            resultado.factura_sin_iva = factura_sin_iva
            resultado.factura_con_iva = factura_con_iva
            resultado.municipio_dept = municipio_final
            resultado.observaciones = "; ".join(advertencias) if advertencias else "Calculo exitoso"

            logger.info(f"Tasa Prodeporte liquidada exitosamente: ${valor_tasa_prodeporte:,.2f}")

            return resultado

        except Exception as e:
            logger.error(f"Error liquidando Tasa Prodeporte: {e}")
            resultado.estado = "preliquidacion_sin_finalizar"
            resultado.observaciones = f"Error tecnico: {str(e)}"
            return resultado


# ===============================
# FUNCIONES DE UTILIDAD
# ===============================

def crear_liquidador_tasa_prodeporte() -> LiquidadorTasaProdeporte:
    """
    Factory function para crear instancia del liquidador.

    SRP: Solo creacion de instancias

    Returns:
        LiquidadorTasaProdeporte: Instancia del liquidador
    """
    return LiquidadorTasaProdeporte()
