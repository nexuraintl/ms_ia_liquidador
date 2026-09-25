"""
CLASIFICACIÓN IVA Y RETEIVA
===========================

Módulo especializado para análisis de IVA y ReteIVA usando Google Gemini AI.
Funciona en paralelo con otros impuestos del sistema integrado.

Funcionalidades:
- Identificación y extracción de IVA de facturas
- Validación de responsabilidad de IVA en RUT
- Determinación de fuente de ingreso (nacional/extranjera)
- Cálculo de ReteIVA según normativa colombiana
- Validación de bienes exentos/excluidos de IVA

Autor: Miguel Angel Jaramillo Durango
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# Importar el ProcesadorGemini base
from .procesador_gemini import ProcesadorGemini
from .prompt_clasificador import PROMPT_ANALISIS_IVA

# Configuración de IVA
from config import (
    obtener_configuracion_iva,
    es_fuente_ingreso_nacional,
    calcular_reteiva,
    obtener_tarifa_reteiva,
    nit_aplica_iva_reteiva
)

logger = logging.getLogger(__name__)

@dataclass
class ResultadoAnalisisIVA:
    """Resultado estructurado del análisis de IVA y ReteIVA"""
    # IVA identificado
    tiene_iva: bool
    valor_iva_total: float
    porcentaje_iva: float
    detalle_conceptos_iva: List[Dict[str, Any]]
    
    # Responsabilidad IVA
    rut_disponible: bool
    es_responsable_iva: Optional[bool]
    codigo_encontrado: str
    
    # Concepto facturado
    concepto_descripcion: str
    concepto_aplica_iva: bool
    categoria_concepto: str
    
    # Fuente de ingreso
    es_fuente_nacional: bool
    validaciones_fuente: Dict[str, bool]
    
    # ReteIVA
    aplica_reteiva: bool
    porcentaje_reteiva: str
    valor_reteiva_calculado: float
    metodo_calculo: str
    
    # Estado final
    estado_liquidacion: str
    observaciones: List[str]

class ClasificadorIVA:
    """
    Clasificador especializado para análisis de IVA y ReteIVA.
    
    Utiliza Google Gemini AI para identificar:
    - IVA en facturas (totalidad, por conceptos, o ausencia)
    - Responsabilidad de IVA según RUT
    - Validación de conceptos exentos/excluidos
    - Fuente de ingreso (nacional/extranjera)
    - Cálculo de ReteIVA según normativa
    """
    
    def __init__(self, procesador_gemini: ProcesadorGemini):
        """
        Inicializa el clasificador de IVA.
        
        Args:
            procesador_gemini: Instancia del procesador Gemini configurado
        """
        self.procesador = procesador_gemini
        self.config_iva = obtener_configuracion_iva()
        logger.info("✅ ClasificadorIVA inicializado correctamente")
    
    async def analizar_iva_completo(self, documentos_clasificados: Dict[str, str], 
                                   nit_administrativo: str) -> ResultadoAnalisisIVA:
        """
        Realiza análisis completo de IVA y ReteIVA de los documentos.
        
        Args:
            documentos_clasificados: Diccionario con documentos clasificados por tipo
            nit_administrativo: NIT de la entidad administrativa
            
        Returns:
            ResultadoAnalisisIVA: Resultado estructurado del análisis
            
        Raises:
            ValueError: Si el NIT no aplica para IVA/ReteIVA
            Exception: Errores de procesamiento con Gemini
        """
        logger.info(f"🔍 Iniciando análisis completo de IVA para NIT: {nit_administrativo}")
        
        # Validar NIT
        if not nit_aplica_iva_reteiva(nit_administrativo):
            raise ValueError(f"NIT {nit_administrativo} no está configurado para análisis de IVA/ReteIVA")
        
        try:
            # 1. Extraer textos por tipo de documento
            textos = self._extraer_textos_por_tipo(documentos_clasificados)
            
            # 2. Generar prompt especializado de IVA
            prompt_iva = PROMPT_ANALISIS_IVA(
                factura_texto=textos["factura"],
                rut_texto=textos["rut"],
                anexos_texto=textos["anexos"],
                cotizaciones_texto=textos["cotizaciones"],
                anexo_contrato=textos["anexo_contrato"]
            )
            
            # 3. Enviar a Gemini para análisis
            logger.info("🧠 Enviando análisis de IVA a Gemini...")
            respuesta_gemini = await self.procesador.enviar_prompt(prompt_iva)
            
            # 4. Procesar respuesta de Gemini
            analisis_json = self._procesar_respuesta_gemini(respuesta_gemini)
            
            # 5. Validar y completar cálculos
            resultado = self._construir_resultado_final(analisis_json, nit_administrativo)
            
            logger.info(f"✅ Análisis de IVA completado. Estado: {resultado.estado_liquidacion}")
            return resultado
            
        except Exception as e:
            error_msg = f"❌ Error en análisis de IVA: {str(e)}"
            logger.error(error_msg)
            
            # Retornar resultado de error estructurado
            return self._crear_resultado_error(error_msg)
    
    def _extraer_textos_por_tipo(self, documentos_clasificados: Dict[str, str]) -> Dict[str, str]:
        """
        Extrae y organiza textos por tipo de documento.
        
        Args:
            documentos_clasificados: Documentos clasificados por nombre de archivo
            
        Returns:
            Dict con textos organizados por tipo
        """
        textos = {
            "factura": "",
            "rut": "",
            "anexos": "",
            "cotizaciones": "",
            "anexo_contrato": ""
        }
        
        for nombre_archivo, contenido in documentos_clasificados.items():
            # Obtener clasificación del archivo (asumiendo que está en el nombre o metadatos)
            nombre_lower = nombre_archivo.lower()
            
            if "factura" in nombre_lower or "invoice" in nombre_lower:
                textos["factura"] += f"\n--- {nombre_archivo} ---\n{contenido}"
            elif "rut" in nombre_lower:
                textos["rut"] += f"\n--- {nombre_archivo} ---\n{contenido}"
            elif "anexo" in nombre_lower and ("contrato" in nombre_lower or "concepto" in nombre_lower):
                textos["anexo_contrato"] += f"\n--- {nombre_archivo} ---\n{contenido}"
            elif "cotizacion" in nombre_lower or "propuesta" in nombre_lower:
                textos["cotizaciones"] += f"\n--- {nombre_archivo} ---\n{contenido}"
            else:
                textos["anexos"] += f"\n--- {nombre_archivo} ---\n{contenido}"
        
        # Limpiar textos vacíos
        for key in textos:
            textos[key] = textos[key].strip()
        
        logger.info(f"📄 Textos extraídos: Factura={len(textos['factura'])}, RUT={len(textos['rut'])}, Anexos={len(textos['anexos'])}")
        return textos
    
    def _procesar_respuesta_gemini(self, respuesta_gemini: str) -> Dict[str, Any]:
        """
        Procesa y valida la respuesta JSON de Gemini.
        
        Args:
            respuesta_gemini: Respuesta cruda de Gemini
            
        Returns:
            Dict con análisis estructurado
            
        Raises:
            ValueError: Si la respuesta no es JSON válido
        """
        try:
            # Limpiar respuesta de posibles caracteres extra
            respuesta_limpia = respuesta_gemini.strip()
            
            # Si viene entre ```json y ```, extraer solo el JSON
            if respuesta_limpia.startswith("```json"):
                inicio = respuesta_limpia.find("{")
                fin = respuesta_limpia.rfind("}") + 1
                respuesta_limpia = respuesta_limpia[inicio:fin]
            
            # Parsear JSON
            analisis_json = json.loads(respuesta_limpia)
            
            # Validar estructura mínima requerida
            campos_requeridos = ["analisis_iva", "analisis_fuente_ingreso", "calculo_reteiva", "estado_liquidacion"]
            for campo in campos_requeridos:
                if campo not in analisis_json:
                    raise ValueError(f"Campo requerido '{campo}' no encontrado en respuesta de Gemini")
            
            logger.info("✅ Respuesta de Gemini procesada correctamente")
            return analisis_json
            
        except json.JSONDecodeError as e:
            error_msg = f"Error parseando JSON de Gemini: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"Respuesta cruda: {respuesta_gemini[:500]}...")
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Error procesando respuesta de Gemini: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise
    
    def _construir_resultado_final(self, analisis_json: Dict[str, Any], 
                                  nit_administrativo: str) -> ResultadoAnalisisIVA:
        """
        Construye el resultado final estructurado a partir del análisis de Gemini.
        
        Args:
            analisis_json: Análisis procesado de Gemini
            nit_administrativo: NIT administrativo
            
        Returns:
            ResultadoAnalisisIVA: Resultado estructurado y validado
        """
        try:
            # Extraer datos del análisis de Gemini
            iva_data = analisis_json["analisis_iva"]
            fuente_data = analisis_json["analisis_fuente_ingreso"]
            reteiva_data = analisis_json["calculo_reteiva"]
            estado_data = analisis_json["estado_liquidacion"]
            
            # Construir resultado estructurado
            resultado = ResultadoAnalisisIVA(
                # IVA identificado
                tiene_iva=iva_data["iva_identificado"]["tiene_iva"],
                valor_iva_total=float(iva_data["iva_identificado"]["valor_iva_total"]),
                porcentaje_iva=float(iva_data["iva_identificado"]["porcentaje_iva"]),
                detalle_conceptos_iva=iva_data["iva_identificado"]["detalle_conceptos_iva"],
                
                # Responsabilidad IVA
                rut_disponible=iva_data["responsabilidad_iva_rut"]["rut_disponible"],
                es_responsable_iva=iva_data["responsabilidad_iva_rut"]["es_responsable_iva"],
                codigo_encontrado=iva_data["responsabilidad_iva_rut"]["codigo_encontrado"],
                
                # Concepto facturado
                concepto_descripcion=iva_data["concepto_facturado"]["descripcion"],
                concepto_aplica_iva=iva_data["concepto_facturado"]["aplica_iva"],
                categoria_concepto=iva_data["concepto_facturado"]["categoria"],
                
                # Fuente de ingreso
                es_fuente_nacional=fuente_data["es_fuente_nacional"],
                validaciones_fuente=fuente_data["validaciones_fuente"],
                
                # ReteIVA
                aplica_reteiva=reteiva_data["aplica_reteiva"],
                porcentaje_reteiva=reteiva_data["porcentaje_reteiva"],
                valor_reteiva_calculado=float(reteiva_data["valor_reteiva_calculado"]),
                metodo_calculo=reteiva_data["metodo_calculo"],
                
                # Estado final
                estado_liquidacion=estado_data["estado"],
                observaciones=estado_data["observaciones"]
            )
            
            # Validar y recalcular ReteIVA si es necesario
            if resultado.aplica_reteiva and resultado.tiene_iva:
                valor_reteiva_validado = calcular_reteiva(
                    valor_iva=resultado.valor_iva_total,
                    es_fuente_nacional=resultado.es_fuente_nacional
                )
                
                # Actualizar si hay diferencia significativa
                if abs(resultado.valor_reteiva_calculado - valor_reteiva_validado) > 0.01:
                    logger.warning(f"⚠️ Recalculando ReteIVA: Gemini={resultado.valor_reteiva_calculado}, Validado={valor_reteiva_validado}")
                    resultado.valor_reteiva_calculado = valor_reteiva_validado
            
            logger.info(f"✅ Resultado final construido: IVA=${resultado.valor_iva_total:,.2f}, ReteIVA=${resultado.valor_reteiva_calculado:,.2f}")
            return resultado
            
        except Exception as e:
            error_msg = f"Error construyendo resultado final: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
    
    def _crear_resultado_error(self, mensaje_error: str) -> ResultadoAnalisisIVA:
        """
        Crea un resultado de error estructurado.
        
        Args:
            mensaje_error: Descripción del error ocurrido
            
        Returns:
            ResultadoAnalisisIVA: Resultado con estado de error
        """
        return ResultadoAnalisisIVA(
            # IVA identificado (valores por defecto)
            tiene_iva=False,
            valor_iva_total=0.0,
            porcentaje_iva=0.0,
            detalle_conceptos_iva=[],
            
            # Responsabilidad IVA
            rut_disponible=False,
            es_responsable_iva=None,
            codigo_encontrado="error",
            
            # Concepto facturado
            concepto_descripcion="Error en procesamiento",
            concepto_aplica_iva=False,
            categoria_concepto="error",
            
            # Fuente de ingreso
            es_fuente_nacional=True,
            validaciones_fuente={},
            
            # ReteIVA
            aplica_reteiva=False,
            porcentaje_reteiva="0%",
            valor_reteiva_calculado=0.0,
            metodo_calculo="error",
            
            # Estado final
            estado_liquidacion="Error en procesamiento",
            observaciones=[mensaje_error]
        )
    
    def obtener_resumen_configuracion(self) -> Dict[str, Any]:
        """
        Obtiene resumen de la configuración actual de IVA.
        
        Returns:
            Dict con configuración actual
        """
        return {
            "nits_configurados": list(self.config_iva["nits_validos"].keys()),
            "total_bienes_no_causan_iva": len(self.config_iva["bienes_no_causan_iva"]),
            "total_bienes_exentos_iva": len(self.config_iva["bienes_exentos_iva"]),
            "total_servicios_excluidos_iva": len(self.config_iva["servicios_excluidos_iva"]),
            "tarifas_reteiva": self.config_iva["config_reteiva"]
        }

# ===============================
# FUNCIONES DE UTILIDAD
# ===============================

def validar_nit_iva(nit: str) -> bool:
    """
    Valida si un NIT está configurado para análisis de IVA.
    
    Args:
        nit: NIT a validar
        
    Returns:
        bool: True si el NIT aplica para IVA/ReteIVA
    """
    return nit_aplica_iva_reteiva(nit)

def obtener_nits_iva_configurados() -> List[str]:
    """
    Obtiene la lista de NITs configurados para IVA.
    
    Returns:
        List[str]: Lista de NITs configurados
    """
    config = obtener_configuracion_iva()
    return list(config["nits_validos"].keys())

def convertir_resultado_a_dict(resultado: ResultadoAnalisisIVA) -> Dict[str, Any]:
    """
    Convierte el resultado estructurado a diccionario para serialización.
    
    Args:
        resultado: Resultado estructurado
        
    Returns:
        Dict con el resultado serializable
    """
    return {
        "iva_identificado": {
            "tiene_iva": resultado.tiene_iva,
            "valor_iva_total": resultado.valor_iva_total,
            "porcentaje_iva": resultado.porcentaje_iva,
            "detalle_conceptos_iva": resultado.detalle_conceptos_iva
        },
        "responsabilidad_iva": {
            "rut_disponible": resultado.rut_disponible,
            "es_responsable_iva": resultado.es_responsable_iva,
            "codigo_encontrado": resultado.codigo_encontrado
        },
        "concepto_facturado": {
            "descripcion": resultado.concepto_descripcion,
            "aplica_iva": resultado.concepto_aplica_iva,
            "categoria": resultado.categoria_concepto
        },
        "fuente_ingreso": {
            "es_fuente_nacional": resultado.es_fuente_nacional,
            "validaciones_fuente": resultado.validaciones_fuente
        },
        "reteiva": {
            "aplica_reteiva": resultado.aplica_reteiva,
            "porcentaje_reteiva": resultado.porcentaje_reteiva,
            "valor_reteiva_calculado": resultado.valor_reteiva_calculado,
            "metodo_calculo": resultado.metodo_calculo
        },
        "estado_liquidacion": {
            "estado": resultado.estado_liquidacion,
            "observaciones": resultado.observaciones
        }
    }

# ===============================
# EJEMPLO DE USO
# ===============================

if __name__ == "__main__":
    """
    Ejemplo de uso del ClasificadorIVA.
    """
    async def ejemplo_uso():
        # Simular documentos clasificados
        documentos_ejemplo = {
            "factura_servicios.pdf": "Factura por servicios de consultoría...",
            "rut_proveedor.pdf": "RUT del proveedor con responsabilidades...",
            "anexo_detalle.pdf": "Detalle de servicios prestados..."
        }
        
        # Crear clasificador (requiere procesador Gemini configurado)
        # procesador = ProcesadorGemini()  # Configurado previamente
        # clasificador = ClasificadorIVA(procesador)
        
        # Analizar IVA
        # resultado = await clasificador.analizar_iva_completo(
        #     documentos_clasificados=documentos_ejemplo,
        #     nit_administrativo="800.178.148-8"
        # )
        
        # print(f"Estado: {resultado.estado_liquidacion}")
        # print(f"IVA Total: ${resultado.valor_iva_total:,.2f}")
        # print(f"ReteIVA: ${resultado.valor_reteiva_calculado:,.2f}")
        
        print("✅ Ejemplo de uso de ClasificadorIVA (comentado para evitar ejecución)")
    
    # Ejecutar ejemplo
    # asyncio.run(ejemplo_uso())
    print("📋 Módulo ClasificadorIVA cargado correctamente")
