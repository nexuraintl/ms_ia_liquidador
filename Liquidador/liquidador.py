"""
LIQUIDADOR DE RETENCIÓN EN LA FUENTE
===================================

Módulo para calcular retenciones en la fuente según normativa colombiana.
Aplica tarifas exactas y valida bases mínimas según CONCEPTOS_RETEFUENTE.

Autor: Miguel Angel Jaramillo Durango
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Importar módulo Conversor TRM para conversión USD a COP
from Conversor import ConversorTRM
from Conversor.exceptions import TRMServiceError, TRMValidationError

# Importar modelos desde Domain Layer (Clean Architecture - SRP)
from modelos import (
    # Modelos para Retencion General
    ConceptoIdentificado,
    DetalleConcepto,
    NaturalezaTercero,

    # Modelos para Articulo 383 - Deducciones Personales
    ConceptoIdentificadoArt383,
    CondicionesArticulo383,
    InteresesVivienda,
    DependientesEconomicos,
    MedicinaPrepagada,
    AFCInfo,
    PlanillaSeguridadSocial,
    DeduccionesArticulo383,
    InformacionArticulo383,

    # Modelos Agregadores - Entrada/Salida
    AnalisisFactura,
    ResultadoLiquidacion,
)

# Configuración de logging
logger = logging.getLogger(__name__)

# ===============================
# LIQUIDADOR DE RETENCIÓN
# ===============================

class LiquidadorRetencion:
    """
    Calcula retenciones en la fuente según normativa colombiana.
    
    Aplica tarifas exactas basadas en el diccionario CONCEPTOS_RETEFUENTE
    y valida todas las condiciones previas para determinar si aplica retención.
    """
    
    def __init__(self, estructura_contable: int = None, db_manager = None):
        """
        Inicializa el liquidador

        Args:
            estructura_contable: Código de estructura contable para consultas
            db_manager: Instancia de DatabaseManager para consultas a BD
        """
        self.estructura_contable = estructura_contable
        self.db_manager = db_manager
        logger.info("LiquidadorRetencion inicializado")
    
    def calcular_retencion(self, analisis: AnalisisFactura) -> ResultadoLiquidacion:
        """
        Calcula la retención en la fuente basada en el análisis de Gemini.
        
        Args:
            analisis: Resultado del análisis de factura de Gemini
            
        Returns:
            ResultadoLiquidacion: Resultado completo del cálculo de retención
        """
        logger.info("Iniciando cálculo de retención en la fuente")
        
        mensajes_error = []
        puede_liquidar = True

        # VALIDACIÓN 1: Conceptos facturados en documentos
        conceptos_sin_facturar = [
            c for c in analisis.conceptos_identificados
            if not c.concepto_facturado or c.concepto_facturado.strip() == ""
        ]

        if conceptos_sin_facturar:
            mensajes_error.append("No se identificaron conceptos facturados en los documentos")
            mensajes_error.append(f"Se encontraron {len(conceptos_sin_facturar)} concepto(s) sin concepto facturado")
            logger.error(f"Conceptos sin concepto_facturado: {len(conceptos_sin_facturar)}")
            return self._crear_resultado_no_liquidable(
                mensajes_error,
                estado="preliquidacion_sin_finalizar",
                valor_factura_sin_iva=analisis.valor_total or 0
            )

        # VALIDACIÓN 2: Naturaleza del tercero
        resultado_validacion = self._validar_naturaleza_tercero(analisis.naturaleza_tercero)
        if not resultado_validacion["puede_continuar"]:
            return self._crear_resultado_no_liquidable(
                resultado_validacion["mensajes"],
                estado=resultado_validacion.get("estado", "preliquidacion_sin_finalizar"),
                valor_factura_sin_iva=analisis.valor_total or 0
            )
        
        # Agregar advertencias de naturaleza del tercero (si las hay)
        mensajes_error.extend(resultado_validacion["advertencias"])
        
        # VALIDACIÓN 3: Conceptos identificados
        conceptos_identificados = [
            c for c in analisis.conceptos_identificados 
            if c.concepto != "CONCEPTO_NO_IDENTIFICADO"
        ]
        
        conceptos_no_identificados = [
            c for c in analisis.conceptos_identificados 
            if c.concepto == "CONCEPTO_NO_IDENTIFICADO"
        ]
        
        # Agregar advertencias por conceptos no identificados
        if conceptos_no_identificados:
            mensajes_error.append("El concepto facturado no se identifica en los soportes adjuntos. Validar soportes.")
            logger.warning(f"Conceptos no identificados: {len(conceptos_no_identificados)}")
        
        # Verificar si hay al menos un concepto identificado
        if not conceptos_identificados:
            mensajes_error.append("No se identificaron conceptos válidos para calcular retención")
            puede_liquidar = False
            logger.error("No hay conceptos identificados válidos")

        if not puede_liquidar:
            return self._crear_resultado_no_liquidable(
                mensajes_error,
                estado="preliquidacion_sin_finalizar",
                valor_factura_sin_iva=analisis.valor_total or 0
            )
        
        #  VALIDACIÓN SEPARADA: ARTÍCULO 383 PARA PERSONAS NATURALES
        # Verificar si se analizó Art 383 y si aplica
        if analisis.articulo_383 :
            logger.info(" Aplicando Artículo 383 - Tarifas progresivas para persona natural")
    
            # Usar función separada para Art 383
            resultado_art383 = self._calcular_retencion_articulo_383_separado(analisis)
            
            if resultado_art383["puede_liquidar"]:
                logger.info(f" Artículo 383 liquidado exitosamente: ${resultado_art383['resultado'].valor_retencion:,.2f}")
                return resultado_art383["resultado"]
            else:
                # Si falla el cálculo del Art. 383, continuar con cálculo tradicional
                mensajes_error.extend(resultado_art383["mensajes_error"])

                
                regimen_art383 = analisis.naturaleza_tercero.regimen_tributario if analisis.naturaleza_tercero else None
                
                logger.info(f"Régimen tributario del tercero: {regimen_art383}")
                
                if regimen_art383 == "SIMPLE":
                    mensajes_error.append("El tercero está en régimen SIMPLE, y no aplica Art. 383")
                    estado = "no_aplica_impuesto"
                    return self._crear_resultado_no_liquidable( mensajes_error,estado=estado,valor_factura_sin_iva=analisis.valor_total or 0)
                
                mensajes_error.append("Aplicando tarifa convencional porque no aplica Art. 383")
                logger.warning(" Fallback a tarifa convencional porque no aplica Art. 383")    

        else:
            # Explicar por qué no aplica Art. 383
            self._agregar_observaciones_art383_no_aplica(analisis.articulo_383, mensajes_error)
        
        # CÁLCULO DE RETENCIÓN CONVENCIONAL
        logger.info(f" Calculando retención para {len(conceptos_identificados)} concepto(s) con bases individuales")
        
        # Obtener conceptos de retefuente
        conceptos_retefuente = self._obtener_conceptos_retefuente()
        
        valor_base_total = analisis.valor_total or 0 # valor de la factura SIN IVA
        valor_retencion_total = 0
        conceptos_aplicados = []
        tarifas_aplicadas = []
        detalles_calculo = []
        
        # CORRECCIÓN CRÍTICA: Validar bases individuales por concepto
        conceptos_con_bases, conceptos_sin_base = self._validar_bases_individuales_conceptos(conceptos_identificados, valor_base_total)

        # Validar si hay conceptos sin base gravable
        if conceptos_sin_base:
            mensajes_error.append("No se extrajo la base gravable de los siguientes conceptos:")
            for concepto in conceptos_sin_base:
                mensajes_error.append(f"  • {concepto}")
            logger.error(f"Liquidación detenida: {len(conceptos_sin_base)} concepto(s) sin base gravable")
            return self._crear_resultado_no_liquidable(
                mensajes_error,
                estado="preliquidacion_sin_finalizar",
                valor_factura_sin_iva=analisis.valor_total or 0
            )

        # VALIDACIÓN: Sumatoria de bases gravables debe coincidir con valor total
        suma_bases_gravables = sum(c.base_gravable for c in conceptos_con_bases)
        tolerancia = 1.0  # Tolerancia de $1 peso por redondeos

        if abs(suma_bases_gravables - valor_base_total) > tolerancia:
            diferencia = suma_bases_gravables - valor_base_total
            mensajes_error.append("Error: La sumatoria de las bases gravables no coincide con el valor total de la factura")
            mensajes_error.append(f"  • Suma de bases gravables: ${suma_bases_gravables:,.2f}")
            mensajes_error.append(f"  • Valor total factura (sin IVA): ${valor_base_total:,.2f}")
            mensajes_error.append(f"  • Diferencia: ${diferencia:,.2f}")
            logger.error(f"Liquidación detenida: Suma bases (${suma_bases_gravables:,.2f}) != Valor total (${valor_base_total:,.2f})")
            return self._crear_resultado_no_liquidable(
                mensajes_error,
                estado="preliquidacion_sin_finalizar",
                valor_factura_sin_iva=analisis.valor_total or 0
            )

        for concepto_item in conceptos_con_bases:
            logger.info(f" Procesando concepto: {concepto_item.concepto} - Base: ${concepto_item.base_gravable:,.2f}")
            resultado_concepto = self._calcular_retencion_concepto(
                concepto_item, conceptos_retefuente
            )
            
            if resultado_concepto["aplica_retencion"]:
                valor_retencion_total += resultado_concepto["valor_retencion"]
                conceptos_aplicados.append(resultado_concepto["concepto"])
                tarifas_aplicadas.append(resultado_concepto["tarifa"])
                detalles_calculo.append(resultado_concepto["detalle"])
                logger.info(f"Retención aplicada: {resultado_concepto['concepto']} - ${resultado_concepto['valor_retencion']:,.0f}")
            else:
                mensajes_error.append(resultado_concepto["mensaje_error"])
                logger.warning(f"No aplica retención: {resultado_concepto['mensaje_error']}")
        
        # Verificar si se pudo calcular alguna retención
        if valor_retencion_total == 0 and not detalles_calculo:
            puede_liquidar = False
            if not mensajes_error:
                mensajes_error.append("No se pudo calcular retención para ningún concepto")
            logger.error("No se calculó retención para ningún concepto")

        # Si no se puede liquidar, devolver resultado vacío
        if not puede_liquidar:
            return self._crear_resultado_no_liquidable(
                mensajes_error,
                estado="no_aplica_impuesto",
                valor_factura_sin_iva=analisis.valor_total or 0
            )
        
        #  PREPARAR RESULTADO FINAL CON ESTRUCTURA MEJORADA
        # Crear lista de detalles por concepto
        detalles_conceptos = []
        conceptos_resumen = []
        
        # Agregar detalles del cálculo a los mensajes (mantener funcionalidad existente)
        if detalles_calculo:
            mensajes_error.append("Detalle del cálculo:")
            
            for detalle in detalles_calculo:
                # Agregar al mensaje de error como antes
                mensajes_error.append(
                    f"  • {detalle['concepto']}: ${detalle['base_gravable']:,.0f} x {detalle['tarifa']:.1f}% = ${detalle['valor_retencion']:,.0f}"
                )

                # Crear objeto DetalleConcepto para nueva estructura
                detalle_concepto = DetalleConcepto(
                    concepto=detalle['concepto'],
                    concepto_facturado=detalle.get('concepto_facturado', None),
                    tarifa_retencion=detalle['tarifa'],
                    base_gravable=detalle['base_gravable'],
                    valor_retencion=detalle['valor_retencion'],
                    codigo_concepto=detalle.get('codigo_concepto', None)
                )
                detalles_conceptos.append(detalle_concepto)
                
                # Crear resumen descriptivo para cada concepto
                conceptos_resumen.append(f"{detalle['concepto']} ({detalle['tarifa']:.1f}%)")
        
        # Generar resumen descriptivo completo
        resumen_descriptivo = " + ".join(conceptos_resumen) if conceptos_resumen else "No aplica retención"
        
        # Crear resultado con nueva estructura
        resultado = ResultadoLiquidacion(
            valor_base_retencion=valor_base_total,
            valor_retencion=valor_retencion_total,
            valor_factura_sin_iva=analisis.valor_total or 0,  # NUEVO: Valor total de la factura
            conceptos_aplicados=detalles_conceptos,  #  NUEVO: Lista de conceptos individuales
            resumen_conceptos=resumen_descriptivo,   #  NUEVO: Resumen descriptivo
            fecha_calculo=datetime.now().isoformat(),
            puede_liquidar=True,
            mensajes_error=mensajes_error,
            estado="preliquidado"  # NUEVO: Proceso completado exitosamente
        )
        
        logger.info(f"Retención calculada exitosamente: ${valor_retencion_total:,.0f}")
        return resultado
    

    
    def _calcular_retencion_articulo_383_separado(self, analisis: AnalisisFactura) -> Dict[str, Any]:
        """
         FUNCIÓN MODIFICADA: Cálculo del Artículo 383 con VALIDACIONES MANUALES.
    
        Gemini solo identifica datos, Python valida y calcula según normativa.
        
        Args:
            analisis: Análisis de factura que incluye el resultado del Art 383 de Gemini
            
        Returns:
            Dict[str, Any]: Resultado del cálculo separado del Art. 383
        """
        logger.info(" Iniciando cálculo Artículo 383 con validaciones manuales")
        
        try:
            # Verificar que existe información del Art 383
            if not analisis.articulo_383:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": ["No se puede calcular Art 383: no hay análisis disponible"]
                }
            
            art383 = analisis.articulo_383
            mensajes_error = []
            
            # Importar constantes del Artículo 383
            from datetime import datetime, timedelta
            from config import (
                UVT_2025, SMMLV_2025, obtener_tarifa_articulo_383, 
                calcular_limite_deduccion, LIMITES_DEDUCCIONES_ART383
            )
            
            # ===============================
            #  PASO 1: VALIDACIONES BÁSICAS OBLIGATORIAS
            # ===============================
            
            logger.info(" Paso 1: Validaciones básicas...")
            
            # Extraer datos identificados por Gemini
            condiciones = art383.condiciones_cumplidas if hasattr(art383, 'condiciones_cumplidas') else None
            deducciones = art383.deducciones_identificadas if hasattr(art383, 'deducciones_identificadas') else None
            
            if not condiciones:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": ["Art 383: No se pudieron extraer las condiciones del análisis de Gemini"]
                }
            
            # VALIDACIÓN 1.1: Persona natural
            es_persona_natural = getattr(condiciones, 'es_persona_natural', False)
            if not es_persona_natural:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": ["Art 383: NO APLICA - El tercero no es persona natural"]
                }
            logger.info(" Validación 1.1: Es persona natural")
            
            # VALIDACIÓN 1.2: Conceptos aplicables
            conceptos_aplicables = getattr(condiciones, 'conceptos_aplicables', False)
            if not conceptos_aplicables:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": ["Art 383: NO APLICA - Los conceptos identificados no son aplicables para Art. 383"]
                }
            logger.info(" Validación 1.2: Conceptos aplicables para Art. 383")
            
            # ===============================
            #  PASO 2: VALIDACIÓN DE PRIMER PAGO Y PLANILLA
            # ===============================
            
            logger.info(" Paso 2: Validación primer pago y planilla...")
            
            es_primer_pago = getattr(condiciones, 'es_primer_pago', False)
            planilla_seguridad_social = False
            fecha_planilla = "0000-00-00"
            IBC_seguridad_social = 0.0
            
            # Extraer información de planilla de seguridad social
            if deducciones and hasattr(deducciones, 'planilla_seguridad_social'):
                planilla_info = deducciones.planilla_seguridad_social
                planilla_seguridad_social = getattr(planilla_info, 'planilla_seguridad_social', False)
                fecha_planilla = getattr(planilla_info, 'fecha_de_planilla_seguridad_social', "0000-00-00")
                IBC_seguridad_social = getattr(planilla_info, 'IBC_seguridad_social', 0.0)
            
            # VALIDACIÓN 2.1: Si NO es primer pago, planilla es OBLIGATORIA
            if not es_primer_pago and not planilla_seguridad_social:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": [
                        "Art 383: NO APLICA - No es primer pago y no se encontró planilla de seguridad social",
                        "La planilla de seguridad social es OBLIGATORIA cuando no es primer pago"
                    ]
                }
            
            if es_primer_pago:
                logger.info(" Validación 2.1: Es primer pago - planilla no obligatoria")
            else:
                logger.info(" Validación 2.1: No es primer pago pero planilla presente")
            
            # ===============================
            #  PASO 3: VALIDACIÓN DE FECHA DE PLANILLA
            # ===============================
            
            if planilla_seguridad_social and fecha_planilla != "0000-00-00":
                logger.info(" Paso 3: Validación fecha de planilla...")

                try:
                    from dateutil.relativedelta import relativedelta
                    
                    # Parsear fecha de planilla
                    fecha_planilla_obj = datetime.strptime(fecha_planilla, "%Y-%m-%d")
                    fecha_actual = datetime.now()
                    
                    # Calcular diferencia exacta
                    diferencia = relativedelta(fecha_actual, fecha_planilla_obj)
                    diferencia_total_dias = (fecha_actual - fecha_planilla_obj).days
                    
                    # VALIDACIÓN 3.1: Planilla no debe tener más de 60 días de antigüedad
                    if diferencia_total_dias > 60:
                        mensajes_error.append(f" ALERTA: Planilla con {diferencia_total_dias} días de antigüedad")
                        mensajes_error.append(f"Detalle: {diferencia.years} años, {diferencia.months} meses, {diferencia.days} días extras")
                        mensajes_error.append("Art 383: NO APLICA - La planilla tiene más de 60 días de antigüedad")
                        mensajes_error.append("Normativa: La planilla debe ser reciente (máximo 60 días)")
                        return {
                            "puede_liquidar": False,
                            "mensajes_error": mensajes_error
                        }
                    
                    logger.info(f" Validación 3.1: Planilla válida ({diferencia_total_dias} días de antigüedad)")
                    logger.info(f"Detalle preciso: {diferencia.years} años, {diferencia.months} meses, {diferencia.days} días")
                    
                except ImportError:
                    # Fallback si dateutil no está disponible
                    logger.warning("dateutil no disponible, usando cálculo simple")
                    diferencia_dias_simple = (fecha_actual - fecha_planilla_obj).days
                    
                    if diferencia_dias_simple > 60:
                        mensajes_error.append(f" ALERTA: Planilla con {diferencia_dias_simple} días de antigüedad")
                        mensajes_error.append("Art 383: NO APLICA - La planilla tiene más de 60 días de antigüedad")
                        return {
                            "puede_liquidar": False,
                            "mensajes_error": mensajes_error
                        }

                    logger.info(f" Validación: Planilla válida ({diferencia_dias_simple} días de antigüedad)")

                except ValueError:
                    mensajes_error.append(f" ADVERTENCIA: No se pudo validar la fecha de planilla: {fecha_planilla}")
                    logger.warning(f"Fecha de planilla inválida: {fecha_planilla}")
            
            # ===============================
            #  PASO 4: EXTRACCIÓN Y VALIDACIÓN DEL INGRESO
            # ===============================
            
            logger.info(" Paso 4: Extracción del ingreso...")
            
            # Extraer ingreso identificado por Gemini
            ingreso_bruto = getattr(condiciones, 'ingreso', 0.0)
            
            # Si Gemini no identificó ingreso, intentar desde otros campos
            if ingreso_bruto <= 0:
                ingreso_bruto = analisis.valor_total or 0.0
                if ingreso_bruto <= 0:
                    # Intentar sumar desde TODOS los conceptos identificados
                    suma_bases_conceptos = 0.0
                    conceptos_con_base = []
                    
                    for concepto in analisis.conceptos_identificados:
                        if concepto.base_gravable and concepto.base_gravable > 0:
                            suma_bases_conceptos += concepto.base_gravable
                            conceptos_con_base.append(f"{concepto.concepto}: ${concepto.base_gravable:,.2f}")
                    
                    if suma_bases_conceptos > 0:
                        ingreso_bruto = suma_bases_conceptos
                        logger.info(f" Ingreso calculado sumando {len(conceptos_con_base)} conceptos: ${ingreso_bruto:,.2f}")
                        logger.info(f"   Detalle conceptos: {', '.join(conceptos_con_base)}")
                    else:
                        logger.warning("No se encontraron conceptos con base gravable válida")
            
            if ingreso_bruto <= 0:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": ["Art 383: NO se pudo determinar el ingreso bruto"]
                }
            
            logger.info(f" Ingreso bruto identificado: ${ingreso_bruto:,.2f}")
            
            # ===============================
            #  PASO 5: VALIDACIÓN DEL IBC (40% DEL INGRESO)
            # ===============================
            
            if planilla_seguridad_social and IBC_seguridad_social > 0:
                logger.info(" Paso 5: Validación IBC vs 40% del ingreso...")
                
                ibc_esperado = ingreso_bruto * 0.40  # 40% del ingreso
                diferencia_ibc = abs(IBC_seguridad_social - ibc_esperado)
                tolerancia = ibc_esperado * 0.01  # 1% de tolerancia

                # VALIDACIÓN 5.1: IBC debe ser aproximadamente 40% del ingreso
                if diferencia_ibc > tolerancia:
                    mensajes_error.append(f" ALERTA IBC: IBC identificado ${IBC_seguridad_social:,.2f} no coincide con 40% del ingreso ${ibc_esperado:,.2f}")
                    mensajes_error.append(f"Diferencia: ${diferencia_ibc:,.2f} (tolerancia: ${tolerancia:,.2f})")
                    mensajes_error.append("Se continúa con el cálculo usando el ingreso identificado")
                    logger.warning(f"IBC no coincide con 40% del ingreso. IBC: ${IBC_seguridad_social:,.2f}, Esperado: ${ibc_esperado:,.2f}")
                else:
                    logger.info(f" Validación 5.1: IBC válido (${IBC_seguridad_social:,.2f} ≈ 40% del ingreso)")
            
            # ===============================
            #  PASO 6: VALIDACIONES DE DEDUCCIONES MANUALES
            # ===============================

            logger.info(" Paso 6: Validaciones de deducciones...")

            deducciones_aplicables = {
                "intereses_vivienda": 0.0,
                "dependientes_economicos": 0.0,
                "medicina_prepagada": 0.0,
                "AFC": 0.0,
                "pensiones_voluntarias": 0.0
            }
            
            if deducciones:
                # VALIDACIÓN 6.1: Intereses corrientes por vivienda
                if hasattr(deducciones, 'intereses_vivienda'):
                    intereses_info = deducciones.intereses_vivienda
                    intereses_corrientes = getattr(intereses_info, 'intereses_corrientes', 0.0)
                    certificado_bancario = getattr(intereses_info, 'certificado_bancario', False)
                    
                    if intereses_corrientes > 0.0 and certificado_bancario:
                        # Dividir entre 12 (mensual) y limitar a 100 UVT
                        valor_mensual = intereses_corrientes / 12
                        limite_uvt = 100 * UVT_2025
                        deducciones_aplicables["intereses_vivienda"] = min(valor_mensual, limite_uvt)
                        logger.info(f" Intereses vivienda aplicados: ${deducciones_aplicables['intereses_vivienda']:,.2f}")
                    elif intereses_corrientes > 0.0 and not certificado_bancario:
                        mensajes_error.append(" Intereses vivienda identificados pero falta certificado bancario")
                
                # VALIDACIÓN 6.2: Dependientes económicos
                if hasattr(deducciones, 'dependientes_economicos'):
                    dependientes_info = deducciones.dependientes_economicos
                    declaracion_juramentada = getattr(dependientes_info, 'declaracion_juramentada', False)
                    
                    if declaracion_juramentada:
                        # Aplicar 10% del ingreso
                        deducciones_aplicables["dependientes_economicos"] = ingreso_bruto * 0.10
                        logger.info(f" Dependientes económicos aplicados: ${deducciones_aplicables['dependientes_economicos']:,.2f}")

                # VALIDACIÓN 6.3: Medicina prepagada
                if hasattr(deducciones, 'medicina_prepagada'):
                    medicina_info = deducciones.medicina_prepagada
                    valor_sin_iva = getattr(medicina_info, 'valor_sin_iva_med_prepagada', 0.0)
                    certificado_medicina = getattr(medicina_info, 'certificado_med_prepagada', False)
                    
                    if valor_sin_iva > 0.0 and certificado_medicina:
                        # Dividir entre 12 y limitar a 16 UVT
                        valor_mensual = valor_sin_iva / 12
                        limite_uvt = 16 * UVT_2025
                        deducciones_aplicables["medicina_prepagada"] = min(valor_mensual, limite_uvt)
                        logger.info(f" Medicina prepagada aplicada: ${deducciones_aplicables['medicina_prepagada']:,.2f}")
                    elif valor_sin_iva > 0.0 and not certificado_medicina:
                        mensajes_error.append(" Medicina prepagada identificada pero falta certificado")
                
                # VALIDACIÓN 6.4: AFC (Ahorro para Fomento a la Construcción)
                if hasattr(deducciones, 'AFC'):
                    afc_info = deducciones.AFC
                    valor_depositar = getattr(afc_info, 'valor_a_depositar', 0.0)
                    planilla_afc = getattr(afc_info, 'planilla_de_cuenta_AFC', False)
                    
                    if valor_depositar > 0.0 and planilla_afc:
                        # Limitar al 25% del ingreso y 316 UVT
                        limite_porcentaje = ingreso_bruto * 0.25
                        limite_uvt = 316 * UVT_2025
                        deducciones_aplicables["AFC"] = min(valor_depositar, limite_porcentaje, limite_uvt)
                        logger.info(f" AFC aplicado: ${deducciones_aplicables['AFC']:,.2f}")
                    elif valor_depositar > 0.0 and not planilla_afc:
                        mensajes_error.append(" AFC identificado pero falta planilla de cuenta")
                
                # VALIDACIÓN 6.5: Pensiones voluntarias
                if planilla_seguridad_social and IBC_seguridad_social >= (4 * SMMLV_2025):
                    # Solo si IBC >= 4 SMMLV
                    deducciones_aplicables["pensiones_voluntarias"] = IBC_seguridad_social * 0.01  # 1% del IBC
                    logger.info(f" Pensiones voluntarias aplicadas: ${deducciones_aplicables['pensiones_voluntarias']:,.2f}")
            
            # ===============================
            #  PASO 7: CÁLCULO FINAL CON VALIDACIONES
            # ===============================
            
            logger.info(" Paso 7: Cálculo final...")
            
            # Calcular aportes a seguridad social (40% del ingreso)
            aportes_seguridad_social = ingreso_bruto * LIMITES_DEDUCCIONES_ART383["seguridad_social_porcentaje"]
            
            # Sumar todas las deducciones aplicables
            total_deducciones = sum(deducciones_aplicables.values())
            
            # Aplicar límite máximo del 40% del ingreso bruto
            limite_maximo_deducciones = ingreso_bruto * LIMITES_DEDUCCIONES_ART383["deducciones_maximas_porcentaje"]
            deducciones_limitadas = min(total_deducciones, limite_maximo_deducciones)
            
            if total_deducciones > limite_maximo_deducciones:
                mensajes_error.append(f" Deducciones limitadas al 40% del ingreso: ${deducciones_limitadas:,.2f} (original: ${total_deducciones:,.2f})")
                logger.warning(f"Deducciones limitadas al 40%: ${deducciones_limitadas:,.2f}")
            
            # Calcular base gravable final
            base_gravable_final = ingreso_bruto - aportes_seguridad_social - deducciones_limitadas
            
            # Verificar que la base gravable no sea negativa
            if base_gravable_final < 0:
                logger.warning("Base gravable negativa, estableciendo en 0")
                base_gravable_final = 0
            
            # Convertir base gravable a UVT
            base_gravable_uvt = base_gravable_final / UVT_2025
            
            # Aplicar tarifa progresiva del Artículo 383
            tarifa_art383 = obtener_tarifa_articulo_383(base_gravable_final)
            valor_retencion_art383 = base_gravable_final * tarifa_art383
            
            logger.info(f" Cálculo completado:")
            logger.info(f"   - Ingreso bruto: ${ingreso_bruto:,.2f}")
            logger.info(f"   - Aportes seg. social: ${aportes_seguridad_social:,.2f}")
            logger.info(f"   - Deducciones: ${deducciones_limitadas:,.2f}")
            logger.info(f"   - Base gravable: ${base_gravable_final:,.2f}")
            logger.info(f"   - Tarifa: {tarifa_art383*100:.1f}%")
            logger.info(f"   - Retención: ${valor_retencion_art383:,.2f}")
            
            # ===============================
            #  PASO 8: PREPARAR RESULTADO FINAL
            # ===============================
            
            # Preparar mensajes explicativos
            mensajes_detalle = [
                " Cálculo Artículo 383 - VALIDACIONES MANUALES APLICADAS:",
                f" Validaciones básicas: Persona natural + Conceptos aplicables",
                f" Primer pago: {'SÍ' if es_primer_pago else 'NO'} - Planilla: {'Presente' if planilla_seguridad_social else 'No requerida'}",
                f" Ingreso bruto: ${ingreso_bruto:,.2f}",
                f" Aportes seguridad social (40%): ${aportes_seguridad_social:,.2f}",
                f" Deducciones aplicables: ${deducciones_limitadas:,.2f}"
            ]
            
            # Detallar deducciones aplicadas
            for tipo, valor in deducciones_aplicables.items():
                if valor > 0:
                    nombre_deduccion = tipo.replace("_", " ").title()
                    mensajes_detalle.append(f"   - {nombre_deduccion}: ${valor:,.2f}")
            
            mensajes_detalle.extend([
                f" Base gravable final: ${base_gravable_final:,.2f}",
                f" Base gravable en UVT: {base_gravable_uvt:.2f} UVT",
                f" Tarifa aplicada: {tarifa_art383*100:.1f}%",
                f" Retención calculada: ${valor_retencion_art383:,.2f}",
                " Cálculo completado con validaciones manuales"
            ])
            
            # Agregar mensajes de error/alertas al detalle
            if mensajes_error:
                mensajes_detalle.extend(["", " ALERTAS Y OBSERVACIONES:"] + mensajes_error)
            
            # Crear resultado con nueva estructura
            concepto_original = analisis.conceptos_identificados[0].concepto if analisis.conceptos_identificados else "Honorarios y servicios"
            concepto_art383_validado = f"ART 383 - {concepto_original}"
            concepto_fact = analisis.conceptos_identificados[0].concepto_facturado if analisis.conceptos_identificados else None
            # Crear detalle del concepto Art. 383 validado manualmente
            detalle_concepto_art383_validado = DetalleConcepto(
                concepto=concepto_art383_validado,
                concepto_facturado=concepto_fact,
                tarifa_retencion=tarifa_art383,
                base_gravable=base_gravable_final,
                valor_retencion=valor_retencion_art383,
                codigo_concepto=None  # Art 383 no tiene código de concepto específico
            )
            
            # Generar resumen descriptivo
            resumen_art383_validado = f"{concepto_art383_validado} ({tarifa_art383*100:.1f}%)"
            
            valor_factura_sin_iva = analisis.valor_total or 0.0
            
            resultado = ResultadoLiquidacion(
                valor_factura_sin_iva=valor_factura_sin_iva,
                valor_base_retencion=base_gravable_final,
                valor_retencion=valor_retencion_art383,
                conceptos_aplicados=[detalle_concepto_art383_validado],
                resumen_conceptos=resumen_art383_validado,
                fecha_calculo=datetime.now().isoformat(),
                puede_liquidar=True,
                mensajes_error=mensajes_detalle,
                estado="preliquidado"  # NUEVO: Artículo 383 validado completado exitosamente
            )
            
            return {
                "puede_liquidar": True,
                "resultado": resultado,
                "mensajes_error": []
            }
            
        except Exception as e:
            logger.error(f"💥 Error en cálculo Art. 383 con validaciones manuales: {e}")
            return {
                "puede_liquidar": False,
                "mensajes_error": [f"Error en cálculo validado Art. 383: {str(e)}"]
            }
    
    def _procesar_deducciones_art383(self, deducciones_identificadas, ingreso_bruto: float) -> Dict[str, float]:
        """
        Procesa las deducciones identificadas por Gemini y aplica límites según normativa.
        
        Args:
            deducciones_identificadas: Deducciones identificadas por Gemini
            ingreso_bruto: Ingreso bruto para calcular límites
            
        Returns:
            Dict[str, float]: Deducciones aplicables con límites aplicados
        """
        from config import calcular_limite_deduccion
        
        deducciones_aplicables = {
            "intereses_vivienda": 0.0,
            "dependientes_economicos": 0.0,
            "medicina_prepagada": 0.0,
            "rentas_exentas": 0.0
        }
        
        # Intereses por vivienda
        if (deducciones_identificadas.intereses_vivienda.tiene_soporte and 
            deducciones_identificadas.intereses_vivienda.valor > 0):
            deducciones_aplicables["intereses_vivienda"] = calcular_limite_deduccion(
                "intereses_vivienda", ingreso_bruto, deducciones_identificadas.intereses_vivienda.valor
            )
            logger.info(f" Intereses vivienda aplicados: ${deducciones_aplicables['intereses_vivienda']:,.2f}")
        
        # Dependientes económicos
        if (deducciones_identificadas.dependientes_economicos.tiene_soporte and 
            deducciones_identificadas.dependientes_economicos.valor > 0):
            deducciones_aplicables["dependientes_economicos"] = calcular_limite_deduccion(
                "dependientes_economicos", ingreso_bruto, deducciones_identificadas.dependientes_economicos.valor
            )
            logger.info(f" Dependientes económicos aplicados: ${deducciones_aplicables['dependientes_economicos']:,.2f}")
        
        # Medicina prepagada
        if (deducciones_identificadas.medicina_prepagada.tiene_soporte and 
            deducciones_identificadas.medicina_prepagada.valor > 0):
            deducciones_aplicables["medicina_prepagada"] = calcular_limite_deduccion(
                "medicina_prepagada", ingreso_bruto, deducciones_identificadas.medicina_prepagada.valor
            )
            logger.info(f" Medicina prepagada aplicada: ${deducciones_aplicables['medicina_prepagada']:,.2f}")
        
        # Rentas exentas
        if (deducciones_identificadas.rentas_exentas.tiene_soporte and 
            deducciones_identificadas.rentas_exentas.valor > 0):
            deducciones_aplicables["rentas_exentas"] = calcular_limite_deduccion(
                "rentas_exentas", ingreso_bruto, deducciones_identificadas.rentas_exentas.valor
            )
            logger.info(f" Rentas exentas aplicadas: ${deducciones_aplicables['rentas_exentas']:,.2f}")
        
        return deducciones_aplicables
    
    def _generar_mensajes_detalle_art383(self, ingreso_bruto: float, aportes_seguridad_social: float, 
                                        deducciones_limitadas: float, deducciones_aplicables: Dict[str, float],
                                        base_gravable_final: float, base_gravable_uvt: float, 
                                        tarifa_art383: float, valor_retencion_art383: float) -> List[str]:
        """
        Genera mensajes detallados explicando el cálculo del Artículo 383.
        
        Returns:
            List[str]: Lista de mensajes explicativos
        """
        mensajes_detalle = [
            "📜 Cálculo bajo Artículo 383 del Estatuto Tributario (ANÁLISIS SEPARADO):",
            f"  • Ingreso bruto: ${ingreso_bruto:,.2f}",
            f"  • Aportes seguridad social (40%): ${aportes_seguridad_social:,.2f}",
            f"  • Deducciones aplicables: ${deducciones_limitadas:,.2f}"
        ]
        
        # Detallar deducciones aplicadas
        for tipo, valor in deducciones_aplicables.items():
            if valor > 0:
                nombre_deduccion = tipo.replace("_", " ").title()
                mensajes_detalle.append(f"    - {nombre_deduccion}: ${valor:,.2f}")
        
        mensajes_detalle.extend([
            f"  • Base gravable final: ${base_gravable_final:,.2f}",
            f"  • Base gravable en UVT: {base_gravable_uvt:.2f} UVT",
            f"  • Tarifa aplicada: {tarifa_art383*100:.1f}%",
            f"  • Retención calculada: ${valor_retencion_art383:,.2f}",
            "✅ Cálculo completado con análisis separado de Gemini"
        ])
        
        return mensajes_detalle
    
    def _agregar_observaciones_art383_no_aplica(self, articulo_383, mensajes_error: List[str]) -> None:
        """
         NUEVA FUNCIÓN: Agrega observaciones cuando el Artículo 383 no aplica.
        
        Args:
            articulo_383: Información del Art 383 del análisis
            mensajes_error: Lista de mensajes a la que agregar observaciones
        """
        condiciones = articulo_383.condiciones_cumplidas
        razones_no_aplica = []
        
        if not condiciones.es_persona_natural:
            razones_no_aplica.append("no es persona natural")
        if not condiciones.concepto_aplicable:
            razones_no_aplica.append("concepto no aplicable para Art. 383")
        if not condiciones.cuenta_cobro:
            razones_no_aplica.append("falta cuenta de cobro")
        if not condiciones.planilla_seguridad_social:
            razones_no_aplica.append("falta planilla de seguridad social")
        if not condiciones.es_primer_pago:
            razones_no_aplica.append("no es primer pago y falta planilla")
        
        if razones_no_aplica:
            mensajes_error.append(f" Art. 383 no aplica: {', '.join(razones_no_aplica)}")
            mensajes_error.append(" Aplicando tarifas convencionales de retefuente")
            logger.info(f" Art. 383 no aplica: {', '.join(razones_no_aplica)}")
    
    def _validar_bases_individuales_conceptos(self, conceptos_identificados: List[ConceptoIdentificado], valor_base_total: float) -> Tuple[List[ConceptoIdentificado], List[str]]:
        """
        SRP: SOLO valida que conceptos tengan base gravable.

        La responsabilidad de obtener tarifa y base mínima está en _calcular_retencion_concepto.

        Args:
            conceptos_identificados: Lista de conceptos identificados por Gemini
            valor_base_total: Valor total de la factura para validaciones

        Returns:
            Tuple[List[ConceptoIdentificado], List[str]]:
                - conceptos_validos: Conceptos con base gravable válida
                - conceptos_sin_base: Nombres de conceptos sin base (para mensajes)
        """

        # VALIDACIÓN: Identificar conceptos con y sin base gravable
        conceptos_sin_base = []
        conceptos_validos = []

        for concepto in conceptos_identificados:
            if not concepto.base_gravable or concepto.base_gravable <= 0:
                conceptos_sin_base.append(concepto.concepto)
                logger.error(f"Concepto sin base gravable: {concepto.concepto}")
            else:
                conceptos_validos.append(concepto)
                logger.info(f"Concepto válido: {concepto.concepto} = ${concepto.base_gravable:,.2f}")

        # Retornar ambas listas para que el llamador decida qué hacer
        return conceptos_validos, conceptos_sin_base
    
    
    
    def _validar_naturaleza_tercero(self, naturaleza: Optional[NaturalezaTercero]) -> Dict[str, Any]:
        """
        Valida la naturaleza del tercero y determina si puede continuar el cálculo.

        Args:
            naturaleza: Información del tercero

        Returns:
            Dict con puede_continuar, mensajes, advertencias y estado
        """
        resultado = {
            "puede_continuar": True,
            "mensajes": [],
            "advertencias": [],
            "estado": None  # NUEVO: Se asignará según validaciones
        }
        
        # 🔧 VALIDACIÓN MEJORADA: Manejar None correctamente
        if not naturaleza or naturaleza is None:
            resultado["advertencias"].append("No se pudo identificar la naturaleza del tercero. Por favor adjunte el RUT actualizado.")
            logger.warning("Naturaleza del tercero no identificada o es None")
            return resultado
        
        #  VALIDACIÓN SEGURA: Verificar que el objeto tiene atributos antes de acceder
        try:
            # Validar autorretenedor
            if hasattr(naturaleza, 'es_autorretenedor') and naturaleza.es_autorretenedor is True:
                resultado["puede_continuar"] = False
                resultado["mensajes"].append("El tercero es autorretenedor - NO se debe practicar retención")
                resultado["estado"] = "no_aplica_impuesto"  # NUEVO
                logger.info("Tercero es autorretenedor - no aplica retención")
                return resultado

            # Ya no se valida responsable de IVA porque aplica retención igual

            # Validar régimen simple
            if hasattr(naturaleza, 'regimen_tributario') and naturaleza.regimen_tributario == "SIMPLE" and hasattr(naturaleza, 'es_persona_natural') and naturaleza.es_persona_natural == False:
                resultado["puede_continuar"] = False
                resultado["mensajes"].append("Régimen Simple de Tributación - Persona Jurídica - NO aplica retención en la fuente")
                resultado["estado"] = "no_aplica_impuesto"  # NUEVO
                logger.info("Régimen Simple detectado - no aplica retención")
                return resultado
            
            # Validar datos faltantes de forma segura
            datos_faltantes = []
          
            if not hasattr(naturaleza, 'regimen_tributario') or naturaleza.regimen_tributario is None:
                datos_faltantes.append("régimen tributario")
            if not hasattr(naturaleza, 'es_autorretenedor') or naturaleza.es_autorretenedor is None:
                datos_faltantes.append("condición de autorretenedor")

            
            if datos_faltantes:
                resultado["advertencias"].append(
                    f"Faltan datos: {', '.join(datos_faltantes)}. "
                    "Por favor adjunte el RUT actualizado para completar la información."
                )
                resultado["puede_continuar"] = False
                resultado["mensajes"].append(f"No se identificaron los siguientes datos : {datos_faltantes} de la naturaleza del proveedor, Por favor adjunte el RUT actualizado")
                resultado["estado"] = "preliquidacion_sin_finalizar"  # NUEVO
                logger.warning(f"Datos faltantes de la naturaleza del tercero: {datos_faltantes}")
                return resultado
                
            
        except AttributeError as e:
            logger.error(f"Error accediendo a atributos de naturaleza_tercero: {e}")
            resultado["advertencias"].append("Error procesando información del tercero. Verifique que el RUT esté adjunto.")
        except Exception as e:
            logger.error(f"Error inesperado validando naturaleza del tercero: {e}")
            resultado["advertencias"].append("Error procesando información del tercero.")
        
        return resultado
    
    def _calcular_retencion_concepto(self, concepto_item: ConceptoIdentificado,
                                   conceptos_retefuente: Dict) -> Dict[str, Any]:
        """
        SRP: Responsable de obtener tarifa/base mínima (BD o diccionario) Y calcular retención.

        Args:
            concepto_item: Concepto identificado por Gemini con base_gravable y concepto_index
            conceptos_retefuente: Diccionario de conceptos (fallback legacy)

        Returns:
            Dict con resultado del cálculo para este concepto
        """
        concepto_aplicado = concepto_item.concepto
        base_concepto = concepto_item.base_gravable

        # VALIDACIÓN ESPECIAL: Base cero por falta de valor disponible
        if base_concepto <= 0:
            return {
                "aplica_retencion": False,
                "mensaje_error": f"{concepto_aplicado}: Sin base gravable disponible (${base_concepto:,.2f})",
                "concepto": concepto_aplicado
            }

        # RESPONSABILIDAD: Obtener tarifa, base mínima y código de concepto
        tarifa = None
        base_minima = None
        codigo_concepto = None

        # ESTRATEGIA 1: Si tiene concepto_index, consultar BD
        if concepto_item.concepto_index and self.db_manager and self.estructura_contable is not None:
            try:
                logger.info(f"Consultando BD para concepto_index={concepto_item.concepto_index}")
                resultado_bd = self.db_manager.obtener_concepto_por_index(
                    concepto_item.concepto_index,
                    self.estructura_contable
                )

                if resultado_bd['success']:
                    porcentaje_bd = resultado_bd['data']['porcentaje']
                    base_minima_bd = resultado_bd['data']['base']
                    codigo_concepto = resultado_bd['data'].get('codigo_concepto', None)

                    tarifa = porcentaje_bd  # Ya viene como 11 (porcentaje directo)
                    base_minima = base_minima_bd

                    logger.info(f"Datos obtenidos de BD: tarifa={tarifa}%, base_minima=${base_minima:,.2f}, codigo={codigo_concepto}")
                else:
                    logger.warning(f"No se pudo obtener datos de BD: {resultado_bd['message']}")
            except Exception as e:
                logger.error(f"Error consultando BD: {e}")

        # ESTRATEGIA 2: Fallback a diccionario legacy si no se obtuvo de BD
        if tarifa is None or base_minima is None:
            if concepto_aplicado not in conceptos_retefuente:
                return {
                    "aplica_retencion": False,
                    "mensaje_error": f"Concepto '{concepto_aplicado}' no encontrado en BD ni en diccionario",
                    "concepto": concepto_aplicado
                }

            datos_concepto = conceptos_retefuente[concepto_aplicado]
            tarifa = datos_concepto["tarifa_retencion"] * 100  # Convertir a porcentaje
            base_minima = datos_concepto["base_pesos"]
            logger.info(f"Usando diccionario legacy: tarifa={tarifa}%, base_minima=${base_minima:,.2f}")

        # Verificar base mínima
        if base_concepto < base_minima:
            return {
                "aplica_retencion": False,
                "mensaje_error": f"{concepto_aplicado}: Base ${base_concepto:,.0f} no supera mínimo de ${base_minima:,.0f}",
                "concepto": concepto_aplicado
            }

        # RESPONSABILIDAD: Calcular retención
        valor_retencion_concepto = (base_concepto * tarifa) / 100

        return {
            "aplica_retencion": True,
            "valor_retencion": valor_retencion_concepto,
            "concepto": concepto_aplicado,
            "tarifa": tarifa /100,  # Convertir a decimal
            "codigo_concepto": codigo_concepto,  # Código del concepto desde BD
            "detalle": {
                "concepto": concepto_aplicado,
                "concepto_facturado": concepto_item.concepto_facturado,
                "base_gravable": base_concepto,
                "tarifa": tarifa / 100,  # Convertir a decimal
                "valor_retencion": valor_retencion_concepto,
                "base_minima": base_minima,
                "codigo_concepto": codigo_concepto
            }
        }
    
    def _obtener_conceptos_retefuente(self) -> Dict:
        """
        Obtiene el diccionario de conceptos de retefuente desde config global.
        
        Returns:
            Dict: CONCEPTOS_RETEFUENTE con tarifas y bases mínimas
        """
        try:
            # Intentar importar desde main o config
            import sys
            import os
            
            # Agregar directorio padre al path
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, parent_dir)
            
            # Importar conceptos desde config
            from config import CONCEPTOS_RETEFUENTE
            logger.info(f"Conceptos cargados desde main: {len(CONCEPTOS_RETEFUENTE)}")
            return CONCEPTOS_RETEFUENTE
            
        except ImportError as e:
            logger.error(f"No se pudo importar CONCEPTOS_RETEFUENTE desde main: {e}")
            # Usar conceptos hardcodeados como fallback
            return self._conceptos_fallback()
        except Exception as e:
            logger.error(f"Error obteniendo conceptos: {e}")
            return self._conceptos_fallback()
    
    def _conceptos_fallback(self) -> Dict:
        """
        Conceptos de emergencia si no se puede acceder al diccionario global.
        
        Returns:
            Dict: Conceptos básicos hardcodeados
        """
        logger.warning("Usando conceptos de fallback - limitados")
        
        return {
            "Servicios generales (declarantes)": {
                "base_pesos": 100000,
                "tarifa_retencion": 0.04
            },
            "Servicios generales (no declarantes)": {
                "base_pesos": 100000,
                "tarifa_retencion": 0.06
            },
            "Honorarios y comisiones por servicios (declarantes)": {
                "base_pesos": 0,
                "tarifa_retencion": 0.11
            },
            "Honorarios y comisiones por servicios (no declarantes)": {
                "base_pesos": 0,
                "tarifa_retencion": 0.10
            },
            "Arrendamiento de bienes inmuebles": {
                "base_pesos": 498000,
                "tarifa_retencion": 0.035
            }
        }
    
    def _crear_resultado_no_liquidable(self, mensajes_error: List[str], estado: str = None, valor_factura_sin_iva: float = 0) -> ResultadoLiquidacion:
        """
        Crea un resultado cuando no se puede liquidar retención.

        Args:
            mensajes_error: Lista de mensajes explicando por qué no se puede liquidar
            estado: Estado específico a asignar (si no se proporciona, se determina automáticamente)
            valor_factura_sin_iva: Valor total de la factura sin IVA (de Gemini)

        Returns:
            ResultadoLiquidacion: Resultado con valores en cero y explicación
        """
        # 🔧 FIX: Generar concepto descriptivo en lugar de "N/A"
        concepto_descriptivo = "No aplica retención"

        # NUEVO: Determinar estado si no se proporciona
        if estado is None:
            estado = "preliquidacion_sin_finalizar"  # Default
        else :
            estado = estado

        # Determinar concepto específico y estado basado en el mensaje de error
        if mensajes_error:
            primer_mensaje = mensajes_error[0].lower()

            if "autorretenedor" in primer_mensaje:
                concepto_descriptivo = "No aplica - tercero es autorretenedor"
                estado = "no_aplica_impuesto"
            elif "simple" in primer_mensaje:
                concepto_descriptivo = "No aplica - régimen simple de tributación y persona jurídica"
                estado = "no_aplica_impuesto"
            elif "extranjera" in primer_mensaje or "exterior" in primer_mensaje:
                concepto_descriptivo = "No aplica - facturación extranjera"
            elif "base" in primer_mensaje and "mínimo" in primer_mensaje:
                concepto_descriptivo = "No aplica - base inferior al mínimo"
                estado = "no_aplica_impuesto"
            elif "383" in primer_mensaje:
                concepto_descriptivo = "No aplica - Artículo 383 no cumple condiciones"
                estado = "no_aplica_impuesto"
            elif "concepto" in primer_mensaje and "identificado" in primer_mensaje:
                concepto_descriptivo = "No aplica - conceptos no identificados"
                estado = "preliquidacion_sin_finalizar"
            elif "faltantes" in primer_mensaje and "datos" in primer_mensaje:
                concepto_descriptivo = "No aplica - datos del tercero incompletos"
                estado = "preliquidacion_sin_finalizar"

        #  NUEVA ESTRUCTURA: Crear resultado con nueva estructura
        return ResultadoLiquidacion(
            valor_base_retencion=0,
            valor_retencion=0,
            valor_factura_sin_iva=valor_factura_sin_iva,  # NUEVO: Valor total de la factura
            conceptos_aplicados=[],  #  NUEVO: Lista vacía para casos sin retención
            resumen_conceptos=concepto_descriptivo,  #  NUEVO: Descripción clara del motivo
            fecha_calculo=datetime.now().isoformat(),
            puede_liquidar=False,
            mensajes_error=mensajes_error,
            estado=estado  # NUEVO
        )
    
    # ===============================
    # VALIDACIONES MANUALES PARA FACTURACIÓN EXTRANJERA
    # ===============================

    def _validar_pais_proveedor_extranjera(self, analisis_extranjera: Dict[str, Any]) -> Dict[str, Any]:
        """
        SRP: SOLO valida que el pais_proveedor no sea vacío.

        Args:
            analisis_extranjera: Resultado del análisis de Gemini para factura extranjera

        Returns:
            Dict con puede_continuar, pais_proveedor, mensajes
        """
        pais_proveedor = analisis_extranjera.get("pais_proveedor", "").strip()

        if not pais_proveedor:
            logger.error("Validación pais_proveedor: No se pudo identificar el país del proveedor")
            return {
                "puede_continuar": False,
                "pais_proveedor": "",
                "mensajes": ["No se pudo identificar el país del proveedor"]
            }

        logger.info(f"Validación pais_proveedor: {pais_proveedor}")
        return {
            "puede_continuar": True,
            "pais_proveedor": pais_proveedor,
            "mensajes": []
        }

    def _validar_concepto_facturado_extranjera(self, analisis_extranjera: Dict[str, Any]) -> Dict[str, Any]:
        """
        SRP: SOLO valida que se haya extraído al menos un concepto_facturado.

        Args:
            analisis_extranjera: Resultado del análisis de Gemini

        Returns:
            Dict con puede_continuar, conceptos_identificados, mensajes
        """
        conceptos_identificados = analisis_extranjera.get("conceptos_identificados", [])

        if not conceptos_identificados:
            logger.error("Validación concepto_facturado: No se extrajo ningún concepto facturado")
            return {
                "puede_continuar": False,
                "conceptos_identificados": [],
                "mensajes": ["No se pudo extraer un concepto facturado"]
            }

        # Verificar que al menos un concepto tenga concepto_facturado válido
        conceptos_validos = [
            c for c in conceptos_identificados
            if c.get("concepto_facturado", "").strip() != ""
        ]

        if not conceptos_validos:
            logger.error("Validación concepto_facturado: Ningún concepto tiene concepto_facturado válido")
            return {
                "puede_continuar": False,
                "conceptos_identificados": [],
                "mensajes": ["No se pudo extraer un concepto facturado"]
            }

        logger.info(f"Validación concepto_facturado: {len(conceptos_validos)} concepto(s) válido(s)")
        return {
            "puede_continuar": True,
            "conceptos_identificados": conceptos_validos,
            "mensajes": []
        }

    def _validar_concepto_mapeado_extranjera(self, conceptos_identificados: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        SRP: SOLO valida que al menos un concepto esté mapeado a la base de datos.

        Args:
            conceptos_identificados: Lista de conceptos extraídos por Gemini

        Returns:
            Dict con puede_continuar, conceptos_mapeados, mensajes
        """
        # Verificar que al menos un concepto tenga "concepto" válido (mapeado al diccionario)
        conceptos_mapeados = [
            c for c in conceptos_identificados
            if c.get("concepto", "").strip() != "" and c.get("concepto_index") is not None
        ]

        if not conceptos_mapeados:
            logger.error("Validación concepto_mapeado: Los conceptos facturados no aplican para retención en la fuente extranjera")
            return {
                "puede_continuar": False,
                "conceptos_mapeados": [],
                "mensajes": ["Los conceptos facturados no aplican para retención en la fuente extranjera"]
            }

        logger.info(f"Validación concepto_mapeado: {len(conceptos_mapeados)} concepto(s) mapeado(s)")
        return {
            "puede_continuar": True,
            "conceptos_mapeados": conceptos_mapeados,
            "mensajes": []
        }

    def _validar_base_gravable_extranjera(self, conceptos_mapeados: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        SRP: SOLO valida que los conceptos tengan base_gravable > 0.

        Args:
            conceptos_mapeados: Lista de conceptos mapeados

        Returns:
            Dict con puede_continuar, conceptos_con_base, mensajes
        """
        conceptos_con_base = [
            c for c in conceptos_mapeados
            if c.get("base_gravable", 0) > 0
        ]

        if not conceptos_con_base:
            logger.error("Validación base_gravable: No se pudo extraer la base gravable del concepto")
            return {
                "puede_continuar": False,
                "conceptos_con_base": [],
                "mensajes": ["No se pudo extraer la base gravable del concepto"]
            }

        logger.info(f"Validación base_gravable: {len(conceptos_con_base)} concepto(s) con base válida")
        return {
            "puede_continuar": True,
            "conceptos_con_base": conceptos_con_base,
            "mensajes": []
        }

    def _validar_valor_total_extranjera(self, analisis_extranjera: Dict[str, Any]) -> Dict[str, Any]:
        """
        SRP: SOLO valida que el valor_total > 0.

        Args:
            analisis_extranjera: Resultado del análisis de Gemini

        Returns:
            Dict con puede_continuar, valor_total, mensajes
        """
        valor_total = analisis_extranjera.get("valor_total", 0.0)

        if valor_total <= 0:
            logger.error("Validación valor_total: No se pudo extraer el valor total de la factura")
            return {
                "puede_continuar": False,
                "valor_total": 0.0,
                "mensajes": ["No se pudo extraer el valor total de la factura"]
            }

        logger.info(f"Validación valor_total: ${valor_total:,.2f}")
        return {
            "puede_continuar": True,
            "valor_total": valor_total,
            "mensajes": []
        }

    def _obtener_tarifa_aplicable_extranjera(self, concepto_index: int, pais_proveedor: str) -> Dict[str, Any]:
        """
        SRP: SOLO obtiene la tarifa aplicable (convenio o normal) consultando la BD.

        Args:
            concepto_index: Index del concepto en la tabla conceptos_extranjeros
            pais_proveedor: País del proveedor extranjero

        Returns:
            Dict con puede_continuar, tarifa_aplicable, tiene_convenio, datos_concepto, mensajes
        """
        if not self.db_manager:
            logger.error("DatabaseManager no inicializado")
            return {
                "puede_continuar": False,
                "tarifa_aplicable": 0.0,
                "tiene_convenio": False,
                "datos_concepto": None,
                "mensajes": ["Error: DatabaseManager no inicializado"]
            }

        try:
            # PASO 1: Obtener datos del concepto desde conceptos_extranjeros
            logger.info(f"Consultando concepto_index={concepto_index} en conceptos_extranjeros")
            resultado_conceptos = self.db_manager.obtener_conceptos_extranjeros()

            if not resultado_conceptos.get("success", False):
                logger.error(f"Error consultando conceptos_extranjeros: {resultado_conceptos.get('error')}")
                return {
                    "puede_continuar": False,
                    "tarifa_aplicable": 0.0,
                    "tiene_convenio": False,
                    "datos_concepto": None,
                    "mensajes": ["Error consultando conceptos extranjeros en la base de datos"]
                }

            # Buscar el concepto específico por index
            conceptos = resultado_conceptos.get("data", [])
            concepto_encontrado = None

            for concepto_bd in conceptos:
                if concepto_bd.get("index") == concepto_index:
                    concepto_encontrado = concepto_bd
                    break

            if not concepto_encontrado:
                logger.error(f"Concepto con index={concepto_index} no encontrado en la BD")
                return {
                    "puede_continuar": False,
                    "tarifa_aplicable": 0.0,
                    "tiene_convenio": False,
                    "datos_concepto": None,
                    "mensajes": ["El concepto no se encontró en la base de datos de conceptos extranjeros"]
                }

            logger.info(f"Concepto encontrado: {concepto_encontrado.get('nombre_concepto')}")

            # PASO 2: Verificar si el país tiene convenio de doble tributación
            logger.info(f"Verificando convenio para país: {pais_proveedor}")
            resultado_paises = self.db_manager.obtener_paises_con_convenio()

            if not resultado_paises.get("success", False):
                logger.warning(f"Error consultando países con convenio: {resultado_paises.get('error')}")
                # Continuar sin convenio
                tiene_convenio = False
            else:
                paises_convenio = resultado_paises.get("data", [])
                # Normalizar nombres para comparación
                paises_convenio_lower = [p.lower() for p in paises_convenio]
                tiene_convenio = pais_proveedor.lower() in paises_convenio_lower

            # PASO 3: Seleccionar tarifa según convenio
            if tiene_convenio:
                tarifa = concepto_encontrado.get("tarifa_convenio", 0.0)
                logger.info(f"País con convenio - Aplicando tarifa_convenio: {tarifa}%")
            else:
                tarifa = concepto_encontrado.get("tarifa_normal", 0.0)
                logger.info(f"País sin convenio - Aplicando tarifa_normal: {tarifa}%")

            return {
                "puede_continuar": True,
                "tarifa_aplicable": tarifa,
                "tiene_convenio": tiene_convenio,
                "datos_concepto": concepto_encontrado,
                "mensajes": []
            }

        except Exception as e:
            logger.error(f"Error obteniendo tarifa aplicable: {e}")
            return {
                "puede_continuar": False,
                "tarifa_aplicable": 0.0,
                "tiene_convenio": False,
                "datos_concepto": None,
                "mensajes": [f"Error consultando tarifas: {str(e)}"]
            }

    def _validar_base_minima_extranjera(self, base_gravable: float, datos_concepto: Dict[str, Any]) -> Dict[str, Any]:
        """
        SRP: SOLO valida que la base_gravable supere la base_minima del concepto.

        Args:
            base_gravable: Base gravable del concepto
            datos_concepto: Datos del concepto desde BD

        Returns:
            Dict con puede_continuar, mensajes
        """
        base_minima = datos_concepto.get("base_pesos", 0.0)

        if base_gravable < base_minima:
            logger.warning(f"Base gravable ${base_gravable:,.2f} no supera base mínima ${base_minima:,.2f}")
            return {
                "puede_continuar": False,
                "mensajes": [f"La base gravable (${base_gravable:,.0f}) no supera la base mínima de ${base_minima:,.0f}"]
            }

        logger.info(f"Base gravable ${base_gravable:,.2f} supera base mínima ${base_minima:,.2f}")
        return {
            "puede_continuar": True,
            "mensajes": []
        }

    def _calcular_retencion_extranjera(self, base_gravable: float, tarifa_aplicable: float) -> Dict[str, Any]:
        """
        SRP: SOLO calcula la retención = base_gravable * tarifa.

        Args:
            base_gravable: Base gravable del concepto
            tarifa_aplicable: Tarifa a aplicar (porcentaje, ej: 15.0 para 15%)

        Returns:
            Dict con valor_retencion
        """
        # Tarifa viene como porcentaje directo (ej: 15.0 = 15%)
        valor_retencion = base_gravable * (tarifa_aplicable / 100)

        logger.info(f"Cálculo retención: ${base_gravable:,.2f} x {tarifa_aplicable}% = ${valor_retencion:,.2f}")

        return {
            "valor_retencion": valor_retencion
        }

    def _crear_resultado_extranjera_error(self, mensajes: List[str], valor_total: float = 0.0,
                                          pais_proveedor: str = "") -> ResultadoLiquidacion:
        """
        SRP: SOLO crea ResultadoLiquidacion para errores de validación en facturación extranjera.

        SIEMPRE agrega "Facturación extranjera" al final de las observaciones.

        Args:
            mensajes: Lista de mensajes de error
            valor_total: Valor total de la factura (si está disponible)
            pais_proveedor: País del proveedor (si está disponible)

        Returns:
            ResultadoLiquidacion con estado de error y valores en cero
        """
        observaciones_finales = mensajes.copy() if mensajes else []

        if pais_proveedor:
            observaciones_finales.insert(0, f"País proveedor: {pais_proveedor}")

        # OBLIGATORIO: Siempre al final
        observaciones_finales.append("Facturación extranjera")

        logger.warning(f"Resultado extranjera con error: {mensajes[0] if mensajes else 'Error desconocido'}")

        return ResultadoLiquidacion(
            valor_base_retencion=0.0,
            valor_retencion=0.0,
            valor_factura_sin_iva=valor_total,
            conceptos_aplicados=[],
            resumen_conceptos="No aplica retención - Error en validación",
            fecha_calculo=datetime.now().isoformat(),
            puede_liquidar=False,
            mensajes_error=observaciones_finales,
            estado="preliquidacion_sin_finalizar"
        )

    def _crear_resultado_extranjera(self, conceptos_procesados: List[Dict[str, Any]],
                                    valor_total: float, pais_proveedor: str,
                                    tiene_convenio: bool, mensajes: List[str]) -> ResultadoLiquidacion:
        """
        SRP: SOLO crea el objeto ResultadoLiquidacion para factura extranjera con múltiples conceptos.

        SIEMPRE agrega "Facturación extranjera" a las observaciones.

        Args:
            conceptos_procesados: Lista de conceptos procesados, cada uno con:
                - datos_concepto: Datos del concepto desde BD
                - base_gravable: Base gravable
                - tarifa_aplicable: Tarifa aplicada
                - valor_retencion: Valor retención individual
            valor_total: Valor total de la factura
            pais_proveedor: País del proveedor
            tiene_convenio: Si el país tiene convenio de doble tributación
            mensajes: Mensajes adicionales

        Returns:
            ResultadoLiquidacion con estructura completa
        """
        # Crear detalles de todos los conceptos
        detalles_conceptos = []
        resumenes = []
        valor_retencion_total = 0.0
        base_gravable_total = 0.0

        for concepto_proc in conceptos_procesados:
            datos = concepto_proc["datos_concepto"]
            base = concepto_proc["base_gravable"]
            tarifa = concepto_proc["tarifa_aplicable"]
            valor_ret = concepto_proc["valor_retencion"]

            # Acumular totales
            valor_retencion_total += valor_ret
            base_gravable_total += base

            # Crear detalle individual
            detalle = DetalleConcepto(
                concepto=datos.get("nombre_concepto", "Concepto extranjero"),
                concepto_facturado=datos.get("concepto_facturado", None),
                tarifa_retencion=tarifa,
                base_gravable=base,
                valor_retencion=valor_ret,
                codigo_concepto=None  # Conceptos extranjeros no tienen código interno
            )
            detalles_conceptos.append(detalle)

            # Crear resumen individual
            tipo_tarifa = "convenio" if tiene_convenio else "normal"
            resumenes.append(f"{datos.get('nombre_concepto', 'Concepto extranjero')} ({tarifa:.1f}% - {tipo_tarifa})")

        # Generar resumen descriptivo completo
        resumen_completo = " + ".join(resumenes) if resumenes else "No aplica retención"

        # Preparar observaciones
        observaciones_finales = mensajes.copy() if mensajes else []
        observaciones_finales.extend([
            f"País proveedor: {pais_proveedor}",
            f"Convenio de doble tributación: {'Sí' if tiene_convenio else 'No'}",
            f"Total conceptos procesados: {len(conceptos_procesados)}",
            "Facturación extranjera"  # OBLIGATORIO: Siempre al final
        ])

        logger.info(f"Resultado extranjera creado: {len(conceptos_procesados)} concepto(s), retención total: ${valor_retencion_total:,.2f}")

        return ResultadoLiquidacion(
            valor_base_retencion=base_gravable_total,
            valor_retencion=valor_retencion_total,
            valor_factura_sin_iva=valor_total,
            conceptos_aplicados=detalles_conceptos,
            resumen_conceptos=resumen_completo,
            fecha_calculo=datetime.now().isoformat(),
            puede_liquidar=True,
            mensajes_error=observaciones_finales,
            estado="preliquidado"
        )

    def _convertir_resultado_usd_a_cop(self, resultado: 'ResultadoLiquidacion', trm_valor: float) -> 'ResultadoLiquidacion':
        """
        Convierte todos los valores monetarios de un ResultadoLiquidacion de USD a COP.

        SRP: Solo responsable de convertir valores monetarios usando la TRM

        Args:
            resultado: ResultadoLiquidacion con valores en USD
            trm_valor: Valor de la TRM para conversión

        Returns:
            ResultadoLiquidacion con todos los valores convertidos a COP
        """
        from copy import deepcopy

        logger.info(f"Convirtiendo resultado de USD a COP usando TRM: {trm_valor}")

        # Convertir valores principales
        resultado.valor_factura_sin_iva = resultado.valor_factura_sin_iva * trm_valor
        resultado.valor_retencion = resultado.valor_retencion * trm_valor
        resultado.valor_base_retencion = resultado.valor_base_retencion * trm_valor

        # Convertir valores en cada concepto aplicado
        for concepto in resultado.conceptos_aplicados:
            concepto.base_gravable = concepto.base_gravable * trm_valor
            concepto.valor_retencion = concepto.valor_retencion * trm_valor

            # Si el concepto tiene detalles (base_minima_exenta, etc.)
            if hasattr(concepto, 'base_minima_exenta') and concepto.base_minima_exenta is not None:
                concepto.base_minima_exenta = concepto.base_minima_exenta * trm_valor

        # Agregar observación sobre la conversión
        mensaje_conversion = f"Valores convertidos de USD a COP usando TRM: ${trm_valor:,.2f}"
        if mensaje_conversion not in resultado.mensajes_error:
            resultado.mensajes_error.append(mensaje_conversion)

        logger.info(f"Conversión completada. Retención total en COP: ${resultado.valor_retencion:,.2f}")
        return resultado

    def liquidar_factura_extranjera_con_validaciones(self, analisis_extranjera: Dict[str, Any], tipoMoneda: str = "COP") -> ResultadoLiquidacion:
        """
        FUNCIÓN PRINCIPAL: Liquida factura extranjera con validaciones secuenciales para TODOS los conceptos.

        Arquitectura v3.0: Gemini SOLO identifica datos, Python valida y calcula.

        Flujo de validaciones (se detiene en el primer error crítico):
        1. Validar país proveedor no vacío
        2. Validar concepto facturado extraído
        3. Validar concepto mapeado a BD
        4. Validar base gravable > 0
        5. Validar valor total > 0
        6. Para cada concepto:
           - Obtener tarifa aplicable (convenio o normal)
           - Validar base mínima
           - Calcular retención
        7. Crear resultado final con todos los conceptos
        8. Si tipoMoneda es USD, convertir todos los valores a COP usando TRM

        Args:
            analisis_extranjera: Análisis de Gemini con estructura:
                {
                    "pais_proveedor": "...",
                    "conceptos_identificados": [...],
                    "valor_total": 0.0,
                    "observaciones": [...]
                }
            tipoMoneda: Tipo de moneda ("COP" o "USD"), por defecto "COP"

        Returns:
            ResultadoLiquidacion con estructura completa (valores en COP)
        """
        logger.info("Iniciando liquidación factura extranjera con validaciones manuales para TODOS los conceptos")

        # VALIDACIÓN 1: País proveedor
        logger.info("Validación 1/5: País proveedor...")
        resultado_pais = self._validar_pais_proveedor_extranjera(analisis_extranjera)
        if not resultado_pais["puede_continuar"]:
            return self._crear_resultado_extranjera_error(
                resultado_pais["mensajes"],
                valor_total=analisis_extranjera.get("valor_total", 0.0)
            )
        pais_proveedor = resultado_pais["pais_proveedor"]

        # VALIDACIÓN 2: Concepto facturado
        logger.info("Validación 2/5: Concepto facturado...")
        resultado_concepto_fact = self._validar_concepto_facturado_extranjera(analisis_extranjera)
        if not resultado_concepto_fact["puede_continuar"]:
            return self._crear_resultado_extranjera_error(
                resultado_concepto_fact["mensajes"],
                valor_total=analisis_extranjera.get("valor_total", 0.0),
                pais_proveedor=pais_proveedor
            )
        conceptos_identificados = resultado_concepto_fact["conceptos_identificados"]

        # VALIDACIÓN 3: Concepto mapeado a BD
        logger.info("Validación 3/5: Concepto mapeado a BD...")
        resultado_mapeado = self._validar_concepto_mapeado_extranjera(conceptos_identificados)
        if not resultado_mapeado["puede_continuar"]:
            return self._crear_resultado_extranjera_error(
                resultado_mapeado["mensajes"],
                valor_total=analisis_extranjera.get("valor_total", 0.0),
                pais_proveedor=pais_proveedor
            )
        conceptos_mapeados = resultado_mapeado["conceptos_mapeados"]

        # VALIDACIÓN 4: Base gravable > 0
        logger.info("Validación 4/5: Base gravable...")
        resultado_base = self._validar_base_gravable_extranjera(conceptos_mapeados)
        if not resultado_base["puede_continuar"]:
            return self._crear_resultado_extranjera_error(
                resultado_base["mensajes"],
                valor_total=analisis_extranjera.get("valor_total", 0.0),
                pais_proveedor=pais_proveedor
            )
        conceptos_con_base = resultado_base["conceptos_con_base"]

        # VALIDACIÓN 5: Valor total > 0
        logger.info("Validación 5/5: Valor total...")
        resultado_total = self._validar_valor_total_extranjera(analisis_extranjera)
        if not resultado_total["puede_continuar"]:
            return self._crear_resultado_extranjera_error(
                resultado_total["mensajes"],
                valor_total=0.0,
                pais_proveedor=pais_proveedor
            )
        valor_total = resultado_total["valor_total"]

        # PROCESAMIENTO: Iterar sobre TODOS los conceptos
        logger.info(f"Procesando {len(conceptos_con_base)} concepto(s) extranjero(s)...")

        conceptos_procesados = []
        advertencias = []
        tiene_convenio = None  # Se determinará en el primer concepto

        for idx, concepto_item in enumerate(conceptos_con_base, 1):
            concepto_index = concepto_item.get("concepto_index")
            base_gravable = concepto_item.get("base_gravable")
            concepto_facturado = concepto_item.get("concepto_facturado", "")

            logger.info(f"Procesando concepto {idx}/{len(conceptos_con_base)}: {concepto_facturado}")

            # PASO 6.1: Obtener tarifa aplicable (convenio o normal)
            resultado_tarifa = self._obtener_tarifa_aplicable_extranjera(concepto_index, pais_proveedor)
            if not resultado_tarifa["puede_continuar"]:
                advertencias.append(f"Concepto '{concepto_facturado}': {resultado_tarifa['mensajes'][0]}")
                logger.warning(f"Concepto {idx} falló obtención de tarifa, saltando...")
                continue

            tarifa_aplicable = resultado_tarifa["tarifa_aplicable"]
            tiene_convenio_concepto = resultado_tarifa["tiene_convenio"]
            datos_concepto = resultado_tarifa["datos_concepto"]

            # Establecer tiene_convenio del país (mismo para todos los conceptos)
            if tiene_convenio is None:
                tiene_convenio = tiene_convenio_concepto

            # PASO 6.2: Validar base mínima
            resultado_base_min = self._validar_base_minima_extranjera(base_gravable, datos_concepto)
            if not resultado_base_min["puede_continuar"]:
                advertencias.append(f"Concepto '{concepto_facturado}': {resultado_base_min['mensajes'][0]}")
                logger.warning(f"Concepto {idx} no supera base mínima, saltando...")
                continue

            # PASO 6.3: Calcular retención
            resultado_calculo = self._calcular_retencion_extranjera(base_gravable, tarifa_aplicable)
            valor_retencion = resultado_calculo["valor_retencion"]

            # Agregar concepto_facturado a datos_concepto
            datos_concepto_completo = datos_concepto.copy()
            datos_concepto_completo["concepto_facturado"] = concepto_facturado

            # Agregar a lista de procesados
            conceptos_procesados.append({
                "datos_concepto": datos_concepto_completo,
                "base_gravable": base_gravable,
                "tarifa_aplicable": tarifa_aplicable/100,  # Convertir a decimal
                "valor_retencion": valor_retencion
            })

            logger.info(f"Concepto {idx} procesado exitosamente: ${valor_retencion:,.2f}")

        # Verificar si se procesó al menos un concepto
        if not conceptos_procesados:
            mensajes_error = ["No se pudo procesar ningún concepto para retención extranjera"]
            if advertencias:
                mensajes_error.extend(advertencias)
            return self._crear_resultado_extranjera_error(
                mensajes_error,
                valor_total=valor_total,
                pais_proveedor=pais_proveedor
            )

        # PASO 7: Crear resultado final con todos los conceptos procesados
        logger.info(f"Creando resultado final con {len(conceptos_procesados)} concepto(s) procesado(s)...")

        # Recopilar observaciones de Gemini si existen
        observaciones_gemini = analisis_extranjera.get("observaciones", [])

        # Agregar advertencias si las hay
        if advertencias:
            observaciones_gemini.extend(advertencias)

        resultado_final = self._crear_resultado_extranjera(
            conceptos_procesados=conceptos_procesados,
            valor_total=valor_total,
            pais_proveedor=pais_proveedor,
            tiene_convenio=tiene_convenio if tiene_convenio is not None else False,
            mensajes=observaciones_gemini
        )

        # PASO 8: Convertir de USD a COP si es necesario
        if tipoMoneda and tipoMoneda.upper() == "USD":
            logger.info("Moneda detectada: USD - Iniciando conversión a COP usando TRM...")
            try:
                with ConversorTRM(timeout=30) as conversor:
                    trm_valor = conversor.obtener_trm_valor()
                    logger.info(f"TRM obtenida exitosamente: ${trm_valor:,.2f} COP/USD")
                    resultado_final = self._convertir_resultado_usd_a_cop(resultado_final, trm_valor)
            except (TRMServiceError, TRMValidationError) as e:
                logger.error(f"Error al obtener TRM para conversión: {e}")
                resultado_final.mensajes_error.append(
                    f"ADVERTENCIA: No se pudo convertir de USD a COP (Error TRM: {str(e)}). Valores mostrados en USD."
                )
            except Exception as e:
                logger.error(f"Error inesperado en conversión USD a COP: {e}")
                resultado_final.mensajes_error.append(
                    f"ADVERTENCIA: Error inesperado en conversión de moneda. Valores mostrados en USD."
                )
        else:
            logger.info(f"Moneda: {tipoMoneda or 'COP'} - No se requiere conversión")

        logger.info(f"Factura extranjera liquidada exitosamente: {len(conceptos_procesados)} concepto(s), retención total: ${resultado_final.valor_retencion:,.2f}")
        return resultado_final

    # ===============================
    # FUNCIONES PÚBLICAS PARA MAIN.PY
    # ===============================

    def liquidar_factura(self, analisis_factura: AnalisisFactura, nit_administrativo: str) -> ResultadoLiquidacion:
        """
        Función pública para liquidar facturas nacionales.
        
        Args:
            analisis_factura: Análisis de la factura de Gemini
            nit_administrativo: NIT de la entidad administrativa
            
        Returns:
            ResultadoLiquidacion: Resultado del cálculo de retención
        """
        logger.info(f"Liquidando factura nacional para NIT: {nit_administrativo}")
        return self.calcular_retencion(analisis_factura)
    


    def liquidar_retefuente_seguro(self, analisis_retefuente: Dict[str, Any], nit_administrativo: str, tipoMoneda: str = "COP") -> Dict[str, Any]:
        """
        Liquida retefuente con manejo seguro de estructura de datos.

        SOLUCIONA EL ERROR: 'dict' object has no attribute 'es_facturacion_exterior'

        FUNCIONALIDAD:
        Maneja estructura JSON de análisis de Gemini
        Extrae correctamente la sección "analisis"
        Convierte dict a objeto AnalisisFactura
        Verifica campos requeridos antes de liquidar
        Manejo robusto de errores con logging detallado
        Fallback seguro en caso de errores
        Conversión de moneda USD a COP si es necesario

        Args:
            analisis_retefuente: Resultado del análisis de Gemini (estructura JSON)
            nit_administrativo: NIT administrativo
            tipoMoneda: Tipo de moneda de la factura ("COP" o "USD"), por defecto "COP"

        Returns:
            Dict con resultado de liquidación o información de error
        """
        try:
            logger.info(f"Iniciando liquidación segura de retefuente para NIT: {nit_administrativo}")

            # VERIFICAR ESTRUCTURA Y EXTRAER ANÁLISIS
            es_facturacion_exterior = False  # Default
            if isinstance(analisis_retefuente, dict):
                if "analisis" in analisis_retefuente:
                    # Estructura: {"analisis": {...}, "timestamp": ..., "es_facturacion_exterior": ...}
                    datos_analisis = analisis_retefuente["analisis"]
                    es_facturacion_exterior = analisis_retefuente.get("es_facturacion_exterior", False)
                    logger.info(f"Extrayendo análisis desde estructura JSON con clave 'analisis', es_facturacion_exterior={es_facturacion_exterior}")
                else:
                    # Estructura directa: {"conceptos_identificados": ..., etc}
                    datos_analisis = analisis_retefuente
                    # En estructura directa, es_facturacion_exterior vendría en datos_analisis si existiera
                    es_facturacion_exterior = datos_analisis.get("es_facturacion_exterior", False)
                    logger.info(f"Usando estructura directa de análisis, es_facturacion_exterior={es_facturacion_exterior}")
            else:
                # Ya es un objeto, usar directamente
                datos_analisis = analisis_retefuente
                logger.info("Usando objeto AnalisisFactura directamente")

            # VERIFICAR CAMPOS REQUERIDOS (ya no incluye es_facturacion_exterior)
            campos_requeridos = ["conceptos_identificados", "naturaleza_tercero"]
            campos_faltantes = []

            for campo in campos_requeridos:
                if campo not in datos_analisis:
                    campos_faltantes.append(campo)

            if campos_faltantes:
                error_msg = f"Campos requeridos faltantes: {', '.join(campos_faltantes)}"
                logger.error(f"{error_msg}")
                logger.error(f"Claves disponibles: {list(datos_analisis.keys()) if isinstance(datos_analisis, dict) else 'No es dict'}")

                return {
                    "aplica": False,
                    "error": error_msg,
                    "valor_retencion": 0.0,
                    "observaciones": [
                        "Error en estructura de datos del análisis",
                        f"Faltan campos: {', '.join(campos_faltantes)}",
                        " La IA no pudo identificar los campos faltantes en la documentacion"
                    ],
                    "estado": "preliquidacion_sin_finalizar"  # NUEVO: Error en estructura
                }

            # CREAR OBJETO ANALYSISFACTURA MANUALMENTE
            # Modelos ya importados desde modelos/ al inicio del archivo

            # Convertir conceptos identificados
            conceptos = []
            conceptos_data = datos_analisis.get("conceptos_identificados", [])

            if not isinstance(conceptos_data, list):
                logger.warning(f"conceptos_identificados no es lista: {type(conceptos_data)}")
                conceptos_data = []

            for concepto_data in conceptos_data:
                if isinstance(concepto_data, dict):
                    concepto_obj = ConceptoIdentificado(
                        concepto=concepto_data.get("concepto", ""),
                        concepto_facturado=concepto_data.get("concepto_facturado", None),
                        base_gravable=concepto_data.get("base_gravable", None),
                        concepto_index=concepto_data.get("concepto_index", None)
                    )
                    conceptos.append(concepto_obj)
                    logger.info(f"Concepto convertido: {concepto_obj.concepto} (index: {concepto_obj.concepto_index})")

            # Convertir naturaleza del tercero
            naturaleza_data = datos_analisis.get("naturaleza_tercero", {})
            if not isinstance(naturaleza_data, dict):
                logger.warning(f"naturaleza_tercero no es dict: {type(naturaleza_data)}")
                naturaleza_data = {}

            naturaleza_obj = NaturalezaTercero(
                es_persona_natural=naturaleza_data.get("es_persona_natural", None),
                regimen_tributario=naturaleza_data.get("regimen_tributario", None),
                es_autorretenedor=naturaleza_data.get("es_autorretenedor", None),
                es_responsable_iva=naturaleza_data.get("es_responsable_iva", None)
            )

            # Crear objeto completo
            analisis_obj = AnalisisFactura(
                conceptos_identificados=conceptos,
                naturaleza_tercero=naturaleza_obj,
                articulo_383=datos_analisis.get("articulo_383", None),
                es_facturacion_exterior=es_facturacion_exterior,  # Usar valor extraído del nivel superior
                valor_total=datos_analisis.get("valor_total", None),
                observaciones=datos_analisis.get("observaciones", [])
            )

            logger.info(f"Objeto AnalisisFactura creado: {len(conceptos)} conceptos, facturación_exterior={analisis_obj.es_facturacion_exterior}")

            # DECIDIR FLUJO: Extranjera (v3.0 validaciones) o Nacional (flujo normal)
            if es_facturacion_exterior:
                logger.info("Detectada facturación extranjera - Usando liquidar_factura_extranjera_con_validaciones (v3.0)")
                # Para facturación extranjera, usar datos_analisis (dict) con validaciones manuales
                resultado = self.liquidar_factura_extranjera_con_validaciones(datos_analisis, tipoMoneda=tipoMoneda)
            else:
                logger.info("Detectada facturación nacional - Usando liquidar_factura (flujo normal)")
                # Para facturación nacional, usar objeto AnalisisFactura
                resultado = self.liquidar_factura(analisis_obj, nit_administrativo)

            # CONVERTIR RESULTADO CON NUEVA ESTRUCTURA
            resultado_dict = {
                "aplica": resultado.puede_liquidar,
                "estado": resultado.estado,
                "valor_factura_sin_iva": resultado.valor_factura_sin_iva,
                "valor_retencion": resultado.valor_retencion,
                "base_gravable": resultado.valor_base_retencion,
                "fecha_calculo": resultado.fecha_calculo,
                "observaciones": resultado.mensajes_error,
                "calculo_exitoso": resultado.puede_liquidar,
                # NUEVOS CAMPOS CON ESTRUCTURA MEJORADA:
                "conceptos_aplicados": [concepto.dict() for concepto in resultado.conceptos_aplicados] if resultado.conceptos_aplicados else [],
                "resumen_conceptos": resultado.resumen_conceptos,
            }

            # AGREGAR pais_proveedor si es facturación extranjera
            if es_facturacion_exterior:
                pais_proveedor = datos_analisis.get("pais_proveedor", "")
                resultado_dict["pais_proveedor"] = pais_proveedor
                logger.info(f"Agregado pais_proveedor al resultado: {pais_proveedor}")

            if resultado.puede_liquidar:
                logger.info(f"Retefuente liquidada exitosamente: ${resultado.valor_retencion:,.2f}")
            else:
                logger.warning(f"Retefuente no se pudo liquidar: {resultado.mensajes_error}")

            return resultado_dict

        except ImportError as e:
            error_msg = f"Error importando clases necesarias: {str(e)}"
            logger.error(f"{error_msg}")
            return {
                "aplica": False,
                "error": error_msg,
                "valor_retencion": 0.0,
                "observaciones": ["Error importando módulos de análisis", "Revise la configuración del sistema"],
                "estado": "preliquidacion_sin_finalizar"  # NUEVO: Error de importación
            }

        except Exception as e:
            error_msg = f"Error liquidando retefuente: {str(e)}"
            logger.error(f"{error_msg}")
            logger.error(f"Tipo de estructura recibida: {type(analisis_retefuente)}")

            # Log adicional para debugging
            if isinstance(analisis_retefuente, dict):
                logger.error(f"Claves disponibles en análisis: {list(analisis_retefuente.keys())}")
                if "analisis" in analisis_retefuente and isinstance(analisis_retefuente["analisis"], dict):
                    logger.error(f"Claves en 'analisis': {list(analisis_retefuente['analisis'].keys())}")

            # Log del traceback completo para debugging
            import traceback
            logger.error(f"Traceback completo: {traceback.format_exc()}")

            return {
                "aplica": False,
                "error": error_msg,
                "valor_retencion": 0.0,
                "observaciones": [
                    "Error en liquidación de retefuente",
                    "Revise estructura de datos",
                    f"Error técnico: {str(e)}"
                ],
                "estado": "preliquidacion_sin_finalizar"  # NUEVO: Error general
            }
