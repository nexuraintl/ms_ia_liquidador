"""
CLASIFICACIÓN DE DOCUMENTOS - MÓDULO DE NEGOCIO
===============================================

Módulo responsable de la clasificación híbrida multimodal de documentos
utilizando Google Gemini AI.

Autor: Miguel Angel Jaramillo Durango
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple, Any, Dict
from fastapi import HTTPException, UploadFile
from Clasificador.clasificador import ProcesadorGemini
from config import guardar_archivo_json
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ResultadoDocumentosClasificados:
    """
    Dataclass para encapsular el resultado completo de la clasificación de documentos.

    Contiene toda la información generada en el proceso de clasificación híbrida
    multimodal, incluyendo documentos estructurados, clasificación simple, y
    detección de casos especiales (consorcio, recurso extranjero, facturación
    extranjera).

    Attributes:
        documentos_clasificados: Diccionario con documentos clasificados y estructurados.
                                 Formato: {
                                     nombre_archivo: {
                                         "categoria": str,
                                         "texto": str,
                                         "procesamiento": str (opcional)
                                     }
                                 }
        es_consorcio: Indicador booleano de si se detectó un consorcio.
        es_recurso_extranjero: Indicador booleano de si es recurso de fuente extranjera.
        es_facturacion_extranjera: Indicador booleano de si es facturación extranjera.
        clasificacion: Diccionario simple de clasificación.
                      Formato: {nombre_archivo: categoria}

    Methods:
        __iter__: Permite desempaquetar el resultado para compatibilidad con código legacy.
                  Retorna: (documentos_clasificados, es_consorcio,
                           es_recurso_extranjero, es_facturacion_extranjera)

    Example:
        >>> resultado = ResultadoDocumentosClasificados(
        ...     documentos_clasificados={"factura.pdf": {"categoria": "FACTURA", "texto": "..."}},
        ...     es_consorcio=True,
        ...     es_recurso_extranjero=False,
        ...     es_facturacion_extranjera=False,
        ...     clasificacion={"factura.pdf": "FACTURA"}
        ... )
        >>> print(resultado.es_consorcio)
        True
        >>> docs, consorcio, extranjero, extranjera = resultado
        >>> print(docs["factura.pdf"]["categoria"])
        FACTURA

    Notes:
        - Soporta acceso por atributo: resultado.documentos_clasificados
        - Soporta desempaquetado: docs, consorcio, extranjero, extranjera = resultado
        - Todas las variables necesarias para el flujo de main.py están disponibles
    """
    documentos_clasificados: Dict[str, Any]
    es_consorcio: bool
    es_recurso_extranjero: bool
    es_facturacion_extranjera: bool
    clasificacion: Dict[str, str]

    def __iter__(self):
        """
        Permite desempaquetar el dataclass para compatibilidad con código legacy.

        Returns:
            Iterator con tupla de (documentos_clasificados, es_consorcio,
                                  es_recurso_extranjero, es_facturacion_extranjera, clasificacion)

        Example:
            >>> resultado = await clasificar_archivos(...)
            >>> docs, consorcio, extranjero, extranjera = resultado
        """
        return iter((
            self.documentos_clasificados,
            self.es_consorcio,
            self.es_recurso_extranjero,
            self.es_facturacion_extranjera,
            self.clasificacion
        ))
    
class ClasificadorDocumentos:
    """
    Clasificador de documentos con soporte multimodal híbrido.

    Implementa el patrón Strategy para la clasificación de documentos
    utilizando Google Gemini AI. Soporta procesamiento híbrido de archivos
    directos (PDFs/imágenes) y textos preprocesados (Excel/Email/Word).

    Attributes:
        clasificador: Instancia de ProcesadorGemini para análisis con IA.

    Example:
        >>> clasificador_gemini = ProcesadorGemini()
        >>> clasificador_docs = ClasificadorDocumentos(clasificador_gemini)
        >>> resultado = await clasificador_docs.clasificar(
        ...     archivos_directos=[pdf_file],
        ...     textos_preprocesados={"archivo.xlsx": "texto..."},
        ...     provedor="CONSORCIO ABC",
        ...     nit_administrativo="900123456",
        ...     nombre_entidad="Universidad Nacional",
        ...     impuestos_a_procesar=["retefuente", "iva"]
        ... )
    """

    def __init__(self, clasificador: Any) -> None:
        """
        Inicializa el clasificador de documentos.

        Args:
            clasificador: Instancia de ProcesadorGemini para análisis con IA.
        """
        self.clasificador = clasificador

    async def clasificar(
        self,
        archivos_directos: List[UploadFile],
        textos_preprocesados: Dict[str, str],
        provedor: str,
        nit_administrativo: str,
        nombre_entidad: str,
        impuestos_a_procesar: List[str]
    ) -> ResultadoDocumentosClasificados:
        """
        Clasifica documentos usando enfoque híbrido multimodal con Gemini AI.

        Coordina la clasificación de documentos combinando archivos directos
        (PDFs/imágenes procesadas nativamente por Gemini) y textos preprocesados
        (Excel/Email/Word convertidos a texto). Detecta automáticamente consorcios
        y facturación extranjera.

        Args:
            archivos_directos: Lista de archivos UploadFile para procesamiento
                              directo multimodal (PDFs, imágenes).
            textos_preprocesados: Diccionario con textos extraídos de archivos
                                 preprocesados {nombre_archivo: texto}.
            provedor: Nombre del proveedor/consorcio para mejor identificación.
            nit_administrativo: NIT de la entidad administrativa que procesa.
            nombre_entidad: Nombre de la entidad administrativa.
            impuestos_a_procesar: Lista de códigos de impuestos a procesar
                                 (ej: ["retefuente", "iva", "estampilla"]).

        Returns:
            ResultadoDocumentosClasificados con:
                - documentos_clasificados: Dict con documentos estructurados
                  {nombre_archivo: {categoria, texto, procesamiento}}
                - clasificacion: Dict simple {nombre_archivo: categoria}
                - es_consorcio: bool indicando si se detectó consorcio
                - es_recurso_extranjero: bool indicando recurso extranjero
                - es_facturacion_extranjera: bool indicando facturación extranjera

        Raises:
            HTTPException: Si hay error en la clasificación con Gemini.
                          - 504: Timeout comunicándose con servicio de IA
                          - 429: Límite de uso del servicio excedido
                          - 502: Error de autenticación o comunicación

        Example:
            >>> resultado = await clasificador.clasificar(
            ...     archivos_directos=[factura_pdf, rut_pdf],
            ...     textos_preprocesados={"anexo.xlsx": "contenido..."},
            ...     provedor="CONSORCIO XYZ",
            ...     nit_administrativo="900123456",
            ...     nombre_entidad="Universidad Nacional",
            ...     impuestos_a_procesar=["retefuente", "iva"]
            ... )
            >>> print(resultado.documentos_clasificados["factura.pdf"]["categoria"])
            FACTURA
            >>> print(resultado.es_consorcio)
            True
            >>> clasificacion, es_consorcio, es_recurso_extranjero, es_facturacion_extranjera = resultado
            >>> print(clasificacion["factura.pdf"])
            FACTURA

        Notes:
            - Guarda automáticamente clasificación en Results/clasificacion_documentos.json
            - Detecta consorcios y facturación extranjera automáticamente
            - Soporta archivos ilimitados: clasificación en lotes de 10 (batching)
            - Combina procesamiento híbrido para máxima precisión
            - Resultado soporta desempaquetado con __iter__() para compatibilidad
        """
        logger.info("Iniciando clasificación híbrida multimodal:")
        logger.info(f"Archivos directos (PDFs/imágenes): {len(archivos_directos)}")
        logger.info(f"Textos preprocesados (Excel/Email/Word): {len(textos_preprocesados)}")

        clasificacion_info, es_consorcio, es_recurso_extranjero, es_facturacion_extranjera = await self.clasificador.clasificar_documentos(
            archivos_directos=archivos_directos,
            textos_preprocesados=textos_preprocesados,
            proveedor=provedor
        )
        
        # Hard stop: si tras la clasificación total no hay ninguna FACTURA, retornar estado preliquidacion_sin_finalizar
        tiene_factura = False
        for k, v in clasificacion_info.items():
            cat = v.get("tipo") if isinstance(v, dict) else v
            if cat == "FACTURA":
                tiene_factura = True
                break
        
        if not tiene_factura:
            logger.error("Hard stop: No se identificó ninguna FACTURA en los soportes adjuntos.")
            raise ValueError("No se identificó ninguna factura en los soportes adjuntos.")

        # Recorte por prioridad fiscal si el conjunto relevante excede 20
        archivos_relevantes = []
        for k, v in clasificacion_info.items():
            relev = v.get("relevante", True) if isinstance(v, dict) else True
            if relev:
                archivos_relevantes.append(k)

        observaciones_recorte = []
        if len(archivos_relevantes) > 20:
            logger.warning(f"Se excede el techo de 20 documentos relevantes (total relevantes: {len(archivos_relevantes)}). Aplicando recorte por prioridad fiscal...")
            
            def obtener_prioridad(nombre: str) -> int:
                info = clasificacion_info[nombre]
                cat = info.get("tipo", "") if isinstance(info, dict) else info
                nombre_lower = nombre.lower()
                cat_upper = cat.upper() if cat else ""
                
                if "FACTURA" in cat_upper:
                    return 1
                if "RUT" in cat_upper:
                    return 2
                if "CONTRATO" in cat_upper or "CONTRATO" in nombre_lower:
                    return 3
                if any(kw in nombre_lower for kw in ["pila", "seguridad", "383", "certificado", "deduccion"]):
                    return 4
                return 5

            archivos_relevantes_ordenados = sorted(archivos_relevantes, key=lambda x: (obtener_prioridad(x), x))
            relevantes_finales = set(archivos_relevantes_ordenados[:20])
            recortados = archivos_relevantes_ordenados[20:]
            
            for k in clasificacion_info.keys():
                if k in relevantes_finales:
                    if isinstance(clasificacion_info[k], dict):
                        clasificacion_info[k]["relevante"] = True
                else:
                    if isinstance(clasificacion_info[k], dict):
                        clasificacion_info[k]["relevante"] = False
                    else:
                        clasificacion_info[k] = {"tipo": clasificacion_info[k], "relevante": False}
            
            msg_recorte = f"Límite de 20 relevantes excedido. Se recortaron los siguientes archivos: {', '.join(recortados)}"
            logger.info(msg_recorte)
            observaciones_recorte.append(msg_recorte)

        logger.info(f" Documentos clasificados: {len(clasificacion_info)}")
        logger.info(f" Es consorcio: {es_consorcio}")
        logger.info(f" Facturación extranjera: {es_facturacion_extranjera}")
        
        clasificacion_data, documentos_clasificados = self.estructurar_respuesta_clasificacion(
            clasificacion = clasificacion_info,
            textos_preprocesados = textos_preprocesados,
            es_consorcio = es_consorcio,
            es_recurso_extranjero = es_recurso_extranjero,
            es_facturacion_extranjera = es_facturacion_extranjera,
            nit_administrativo = nit_administrativo,
            nombre_entidad = nombre_entidad,
            impuestos_a_procesar = impuestos_a_procesar,
            archivos_directos=archivos_directos,
            observaciones=observaciones_recorte
        )
        
        guardar_archivo_json(clasificacion_data, "clasificacion_documentos")
        
        logger.info(f" Clasificación completada: {len(clasificacion_info)} documentos")
        logger.info(f" Consorcio detectado: {es_consorcio}")
        logger.info(f" Facturación extranjera: {es_facturacion_extranjera}")
        
        # Devolver clasificacion simple Dict[str, str] para compatibilidad downstream
        clasificacion_simple = {k: (v.get("tipo", "ANEXO") if isinstance(v, dict) else v) for k, v in clasificacion_info.items()}

        return ResultadoDocumentosClasificados(
            documentos_clasificados=documentos_clasificados,
            es_consorcio=es_consorcio,
            es_recurso_extranjero=es_recurso_extranjero,
            es_facturacion_extranjera=es_facturacion_extranjera,
            clasificacion=clasificacion_simple
        )

    def estructurar_respuesta_clasificacion(
        self,
        clasificacion: Dict[str, Any],
        textos_preprocesados: Dict[str, str],
        es_consorcio: bool,
        es_recurso_extranjero: bool,
        es_facturacion_extranjera: bool,
        nit_administrativo: str,
        nombre_entidad: str,
        impuestos_a_procesar: List[str],
        archivos_directos: List[UploadFile],
        observaciones: List[str] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Estructura la respuesta de clasificación para persistencia y uso posterior.

        Combina la clasificación de Gemini con información contextual del procesamiento
        (NIT, entidad, impuestos, modo híbrido) y genera dos salidas:
        1. Datos completos para guardar en JSON (con metadatos)
        2. Documentos clasificados para procesamiento posterior

        Args:
            clasificacion: Diccionario {nombre_archivo: info_dict_o_str} resultante
                          de la clasificación de Gemini.
            textos_preprocesados: Textos extraídos de archivos preprocesados.
            es_consorcio: Indicador si se detectó consorcio.
            es_recurso_extranjero: Indicador si se detectó recurso extranjero.
            es_facturacion_extranjera: Indicador si se detectó facturación extranjera.
            nit_administrativo: NIT de la entidad administrativa.
            nombre_entidad: Nombre de la entidad administrativa.
            impuestos_a_procesar: Lista de códigos de impuestos a procesar.
            archivos_directos: Lista de archivos procesados directamente.
            observaciones: Observaciones/recortes registrados durante el proceso.

        Returns:
            Tupla con dos diccionarios:
            - clasificacion_data: Datos completos con metadatos para persistencia
            - documentos_clasificados: Documentos estructurados para procesamiento
        """
        documentos_clasificados = {}
        # Mapear el tipo nuevo "CONTRATO" al string canonico que esperan los clasificadores
        # downstream para enrutar el OBJETO DEL CONTRATO a su seccion dedicada.
        # 5 de 6 clasificadores comparan contra "ANEXO CONCEPTO DE CONTRATO"; tasa_prodeporte
        # tambien lo acepta. Asi el texto del contrato llega a todas las llamadas downstream.
        equivalencias_categoria = {"CONTRATO": "ANEXO CONCEPTO DE CONTRATO"}
        for nombre_archivo, info in clasificacion.items():
            categoria = info.get("tipo", "ANEXO") if isinstance(info, dict) else info
            categoria = equivalencias_categoria.get(categoria, categoria)
            relevante = info.get("relevante", True) if isinstance(info, dict) else True

            if nombre_archivo in textos_preprocesados:
                # Si el documento no es relevante, su texto no debe llegar a las llamadas
                # downstream (coherente con el filtrado del cache de archivos directos).
                texto = textos_preprocesados[nombre_archivo] if relevante else ""
                documentos_clasificados[nombre_archivo] = {
                    "categoria": categoria,
                    "texto": texto,
                    "relevante": relevante
                }
            else:
                documentos_clasificados[nombre_archivo] = {
                    "categoria": categoria,
                    "texto": "[ARCHIVO_DIRECTO_MULTIMODAL]",
                    "procesamiento": "directo_gemini",
                    "relevante": relevante
                }
        
        # Guardar clasificación con información híbrida
        clasificacion_simple = {k: (v.get("tipo", "ANEXO") if isinstance(v, dict) else v) for k, v in clasificacion.items()}
        clasificacion_data = {
            "timestamp": datetime.now().isoformat(),
            "nit_administrativo": nit_administrativo,
            "nombre_entidad": nombre_entidad,
            "clasificacion": clasificacion_simple,
            "es_consorcio": es_consorcio,
            "es_facturacion_extranjera": es_facturacion_extranjera,
            "es_recurso_extranjero": es_recurso_extranjero,
            "impuestos_aplicables": impuestos_a_procesar,
            "observaciones": observaciones or [],
            "procesamiento_hibrido": {
                "multimodalidad_activa": True,
                "archivos_directos": len(archivos_directos),
                "archivos_preprocesados": len(textos_preprocesados),
                "total_archivos": len(archivos_directos) + len(textos_preprocesados),
                "nombres_archivos_directos": [archivo.filename for archivo in archivos_directos],
                "nombres_archivos_preprocesados": list(textos_preprocesados.keys()),
                "version_multimodal": "3.0.0"
            }
        }
        return clasificacion_data, documentos_clasificados


async def clasificar_archivos(
    clasificador: Any,
    archivos_directos: List[UploadFile],
    textos_preprocesados: Dict[str, str],
    provedor: str,
    nit_administrativo: str,
    nombre_entidad: str,
    impuestos_a_procesar: List[str]
) -> ResultadoDocumentosClasificados:
    """
    Función fachada para clasificar archivos con enfoque híbrido multimodal.

    Simplifica la invocación de la clasificación de documentos creando
    automáticamente la instancia de ClasificadorDocumentos y delegando
    la operación. Útil para mantener retrocompatibilidad y simplicidad
    en el código cliente.

    Args:
        clasificador: Instancia de ProcesadorGemini para análisis con IA.
        archivos_directos: Lista de archivos UploadFile para procesamiento
                          directo multimodal (PDFs, imágenes).
        textos_preprocesados: Diccionario con textos extraídos de archivos
                             preprocesados {nombre_archivo: texto}.
        provedor: Nombre del proveedor/consorcio para mejor identificación.
        nit_administrativo: NIT de la entidad administrativa que procesa.
        nombre_entidad: Nombre de la entidad administrativa.
        impuestos_a_procesar: Lista de códigos de impuestos a procesar
                             (ej: ["retefuente", "iva", "estampilla"]).

    Returns:
        ResultadoDocumentosClasificados con:
            - documentos_clasificados: Dict con documentos estructurados
              {nombre_archivo: {categoria, texto, procesamiento}}
            - clasificacion: Dict simple {nombre_archivo: categoria}
            - es_consorcio: bool indicando si se detectó consorcio
            - es_recurso_extranjero: bool indicando recurso extranjero
            - es_facturacion_extranjera: bool indicando facturación extranjera

    Raises:
        HTTPException: Si hay error en la clasificación con Gemini.
                      - 504: Timeout comunicándose con servicio de IA
                      - 429: Límite de uso del servicio excedido
                      - 502: Error de autenticación o comunicación

    Example:
        >>> from Clasificador.clasificador import ProcesadorGemini
        >>> clasificador_gemini = ProcesadorGemini()
        >>> resultado = await clasificar_archivos(
        ...     clasificador=clasificador_gemini,
        ...     archivos_directos=[factura_pdf],
        ...     textos_preprocesados={"anexo.xlsx": "texto..."},
        ...     provedor="CONSORCIO ABC",
        ...     nit_administrativo="900123456",
        ...     nombre_entidad="Universidad Nacional",
        ...     impuestos_a_procesar=["retefuente", "iva"]
        ... )
        >>> print(resultado.documentos_clasificados["factura.pdf"]["categoria"])
        FACTURA
        >>> print(resultado.es_consorcio)
        False
        >>> clasificacion, es_consorcio, es_recurso_extranjero, es_facturacion_extranjera = resultado
        >>> print(clasificacion["factura.pdf"])
        FACTURA

    Notes:
        - Función de conveniencia para simplificar llamadas
        - Crea instancia de ClasificadorDocumentos internamente
        - Guarda automáticamente clasificación en Results/
        - Soporta archivos ilimitados: clasificación en lotes de 10 (batching)
        - Resultado soporta desempaquetado para compatibilidad con código legacy
    """
    instancia_clasificador = ClasificadorDocumentos(clasificador)
    return await instancia_clasificador.clasificar(
        archivos_directos=archivos_directos,
        textos_preprocesados=textos_preprocesados,
        provedor=provedor,
        nit_administrativo=nit_administrativo,
        nombre_entidad=nombre_entidad,
        impuestos_a_procesar=impuestos_a_procesar
    )
    