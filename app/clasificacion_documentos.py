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
            - Soporta hasta 20 archivos directos simultáneos
            - Combina procesamiento híbrido para máxima precisión
            - Resultado soporta desempaquetado con __iter__() para compatibilidad
        """
        logger.info("Iniciando clasificación híbrida multimodal:")
        logger.info(f"Archivos directos (PDFs/imágenes): {len(archivos_directos)}")
        logger.info(f"Textos preprocesados (Excel/Email/Word): {len(textos_preprocesados)}")

        clasificacion, es_consorcio, es_recurso_extranjero, es_facturacion_extranjera = await self.clasificador.clasificar_documentos(
            archivos_directos=archivos_directos,
            textos_preprocesados=textos_preprocesados,
            proveedor=provedor
        )
        
        logger.info(f" Documentos clasificados: {len(clasificacion)}")
        logger.info(f" Es consorcio: {es_consorcio}")
        logger.info(f" Facturación extranjera: {es_facturacion_extranjera}")
        
        clasificacion_data, documentos_clasificados = self.estructurar_respuesta_clasificacion(
            clasificacion = clasificacion,
            textos_preprocesados = textos_preprocesados,
            es_consorcio = es_consorcio,
            es_recurso_extranjero = es_recurso_extranjero,
            es_facturacion_extranjera = es_facturacion_extranjera,
            nit_administrativo = nit_administrativo,
            nombre_entidad = nombre_entidad,
            impuestos_a_procesar = impuestos_a_procesar,
            archivos_directos=archivos_directos)
        
        guardar_archivo_json(clasificacion_data, "clasificacion_documentos")
        
        logger.info(f" Clasificación completada: {len(clasificacion)} documentos")
        logger.info(f" Consorcio detectado: {es_consorcio}")
        logger.info(f" Facturación extranjera: {es_facturacion_extranjera}")
        
        return ResultadoDocumentosClasificados(
            documentos_clasificados=documentos_clasificados,
            es_consorcio=es_consorcio,
            es_recurso_extranjero=es_recurso_extranjero,
            es_facturacion_extranjera=es_facturacion_extranjera,
            clasificacion=clasificacion)

    def estructurar_respuesta_clasificacion(
        self,
        clasificacion: Dict[str, str],
        textos_preprocesados: Dict[str, str],
        es_consorcio: bool,
        es_recurso_extranjero: bool,
        es_facturacion_extranjera: bool,
        nit_administrativo: str,
        nombre_entidad: str,
        impuestos_a_procesar: List[str],
        archivos_directos: List[UploadFile]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Estructura la respuesta de clasificación para persistencia y uso posterior.

        Combina la clasificación de Gemini con información contextual del procesamiento
        (NIT, entidad, impuestos, modo híbrido) y genera dos salidas:
        1. Datos completos para guardar en JSON (con metadatos)
        2. Documentos clasificados para procesamiento posterior

        Args:
            clasificacion: Diccionario {nombre_archivo: categoria} resultante
                          de la clasificación de Gemini.
            textos_preprocesados: Textos extraídos de archivos preprocesados.
            es_consorcio: Indicador si se detectó consorcio.
            es_recurso_extranjero: Indicador si se detectó recurso extranjero.
            es_facturacion_extranjera: Indicador si se detectó facturación extranjera.
            nit_administrativo: NIT de la entidad administrativa.
            nombre_entidad: Nombre de la entidad administrativa.
            impuestos_a_procesar: Lista de códigos de impuestos a procesar.
            archivos_directos: Lista de archivos procesados directamente.

        Returns:
            Tupla con dos diccionarios:
            - clasificacion_data: Datos completos con metadatos para persistencia
            - documentos_clasificados: Documentos estructurados para procesamiento

        Example:
            >>> clasificacion = {"factura.pdf": "FACTURA", "rut.pdf": "RUT"}
            >>> data, docs = estructurar_respuesta_clasificacion(
            ...     clasificacion=clasificacion,
            ...     textos_preprocesados={"anexo.xlsx": "texto..."},
            ...     es_consorcio=True,
            ...     es_recurso_extranjero=False,
            ...     es_facturacion_extranjera=False,
            ...     nit_administrativo="900123456",
            ...     nombre_entidad="Universidad Nacional",
            ...     impuestos_a_procesar=["retefuente"],
            ...     archivos_directos=[factura_upload, rut_upload]
            ... )
            >>> print(docs["factura.pdf"]["categoria"])
            FACTURA
            >>> print(data["procesamiento_hibrido"]["total_archivos"])
            3

        Notes:
            - Archivos directos se marcan con procesamiento: "directo_gemini"
            - Archivos preprocesados incluyen el texto extraído
            - Genera metadatos de procesamiento híbrido automáticamente
        """
        documentos_clasificados = {}
        for nombre_archivo, categoria in clasificacion.items():
            # Para archivos directos, el texto no está disponible (se procesó directamente por Gemini)
            if nombre_archivo in textos_preprocesados:
                documentos_clasificados[nombre_archivo] = {
                    "categoria": categoria,
                    "texto": textos_preprocesados[nombre_archivo]
                }
            else:
                # Archivo directo (PDF/imagen) - procesado nativamente por Gemini
                documentos_clasificados[nombre_archivo] = {
                    "categoria": categoria,
                    "texto": "[ARCHIVO_DIRECTO_MULTIMODAL]",
                    "procesamiento": "directo_gemini"
                }
        
        # Guardar clasificación con información híbrida
        clasificacion_data = {
            "timestamp": datetime.now().isoformat(),
            "nit_administrativo": nit_administrativo,
            "nombre_entidad": nombre_entidad,
            "clasificacion": clasificacion,
            "es_consorcio": es_consorcio,
            "es_facturacion_extranjera": es_facturacion_extranjera,
            "es_recurso_extranjero": es_recurso_extranjero,
            "impuestos_aplicables": impuestos_a_procesar,
            "procesamiento_hibrido": {
                "multimodalidad_activa": True,
                "archivos_directos": len(archivos_directos),
                "archivos_preprocesados": len(textos_preprocesados),
                "total_archivos": len(archivos_directos) + len(textos_preprocesados),
                "nombres_archivos_directos": [archivo.filename for archivo in archivos_directos],
                "nombres_archivos_preprocesados": list(textos_preprocesados.keys()),
                "version_multimodal": "2.8.0"
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
        - Soporta hasta 20 archivos directos simultáneos
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
    