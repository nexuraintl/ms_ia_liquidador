"""
Tests de Clasificación, Filtrado y Hard Stop de Documentos.
Cubre los requisitos de división en dos fases, batching, recorte por prioridad fiscal,
hard stop y filtrado de cache.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from fastapi import UploadFile, HTTPException
from app.clasificacion_documentos import ClasificadorDocumentos, ResultadoDocumentosClasificados
from app.preparacion_tareas_analisis import PreparadorCacheArchivos
from Clasificador.clasificador import ProcesadorGemini


import re
import json

def llamar_gemini_side_effect_helper(contents, nombres_archivos=None):
    # nombres_archivos: nuevo kwarg que vincula nombre<->contenido en el envio
    # multimodal; el helper solo necesita el prompt (contents[0]) para simular.
    # If it is the global analysis prompt, return a global analysis response
    prompt = contents[0]
    if "analisis_fuente_ingreso" in prompt:
        return json.dumps({
            "es_consorcio": False,
            "ubicacion_proveedor": "Bogota, Colombia",
            "es_fuera_colombia": False,
            "analisis_fuente_ingreso": {
                "servicio_uso_colombia": True,
                "evidencias_uso_encontradas": [],
                "ejecutado_en_colombia": True,
                "evidencias_ejecucion_encontradas": [],
                "asistencia_tecnica_colombia": False,
                "evidencias_asistencia_encontradas": [],
                "bien_ubicado_colombia": False,
                "evidencias_bien_encontradas": []
            }
        })
    
    # Otherwise, it's a batch classification prompt.
    # Extract file names ONLY from the documents section, not from the
    # instructions (the prompt may include example asset names like
    # "image00X.png" as calibration anchors that must not be counted).
    seccion_docs = prompt.lower()
    marcador = "documentos a analizar"
    if marcador in seccion_docs:
        seccion_docs = seccion_docs.split(marcador, 1)[1]
    files = re.findall(r"(\w+\.(?:pdf|png|txt|xml|xlsx|msg))", seccion_docs)
    
    clasif = {}
    for f in files:
        if "dup_1" in f:
            tipo = "RUT"
        else:
            tipo = "FACTURA" if ("file" in f or "dup" in f) else "ANEXO"
        clasif[f] = {"tipo": tipo, "relevante": True}
        
    return json.dumps({
        "clasificacion": clasif,
        "factura_identificada": any(v["tipo"] == "FACTURA" for v in clasif.values()),
        "rut_identificado": any(v["tipo"] == "RUT" for v in clasif.values())
    })


@pytest.mark.asyncio
async def test_4_1_mas_de_20_archivos_sin_error_batching():
    """Test 4.1: >20 archivos no se rechazan y se procesan en lotes de 10."""
    mock_gemini = AsyncMock(spec=ProcesadorGemini)
    mock_gemini.files_manager = MagicMock()
    mock_gemini.files_manager.upload_file = AsyncMock(return_value=Mock(name="file_ref", display_name="doc.pdf"))
    mock_gemini._files_get_con_retry = AsyncMock(return_value=Mock(name="file_obj", mime_type="application/pdf", uri="uri://doc"))
    
    # Mock calls to return valid batch JSON dynamically using side_effect
    mock_gemini._llamar_gemini_hibrido = AsyncMock(side_effect=llamar_gemini_side_effect_helper)
    mock_gemini._limpiar_respuesta_json = lambda x: x
    mock_gemini._guardar_respuesta = AsyncMock()
    mock_gemini._evaluar_tipo_recurso = MagicMock(return_value=False)
    mock_gemini._determinar_facturacion_extranjera = MagicMock(return_value=False)
    
    # 25 dummy files
    archivos = []
    for i in range(1, 26):
        a = Mock(spec=UploadFile)
        a.filename = f"file{i}.pdf"
        a.read = AsyncMock(return_value=b"%PDF-1.4")
        archivos.append(a)
        
    # Bind real method to mock
    mock_gemini.clasificar_documentos = ProcesadorGemini.clasificar_documentos.__get__(mock_gemini, ProcesadorGemini)
    
    res = await mock_gemini.clasificar_documentos(archivos_directos=archivos)
    
    # Should call _llamar_gemini_hibrido 4 times (3 batches + 1 global analysis)
    assert mock_gemini._llamar_gemini_hibrido.call_count == 4
    assert len(res[0]) == 25


@pytest.mark.asyncio
async def test_4_2_merge_lotes_or_factura_and_collisions():
    """Test 4.2: Merge de lotes consolida la clasificación, factura_identificada es OR y maneja colisiones."""
    mock_gemini = AsyncMock(spec=ProcesadorGemini)
    mock_gemini.files_manager = MagicMock()
    mock_gemini.files_manager.upload_file = AsyncMock(return_value=Mock(name="file_ref", display_name="dup.pdf"))
    mock_gemini._files_get_con_retry = AsyncMock(return_value=Mock(name="file_obj", mime_type="application/pdf", uri="uri://dup"))
    
    # Mock calls using dynamic side_effect
    mock_gemini._llamar_gemini_hibrido = AsyncMock(side_effect=llamar_gemini_side_effect_helper)
    mock_gemini._limpiar_respuesta_json = lambda x: x
    mock_gemini._guardar_respuesta = AsyncMock()
    mock_gemini._evaluar_tipo_recurso = MagicMock(return_value=False)
    mock_gemini._determinar_facturacion_extranjera = MagicMock(return_value=False)
    
    file1 = Mock(spec=UploadFile, filename="dup.pdf")
    file2 = Mock(spec=UploadFile, filename="dup.pdf")
    for f in [file1, file2]:
        f.read = AsyncMock(return_value=b"%PDF-1.4")
        
    mock_gemini.clasificar_documentos = ProcesadorGemini.clasificar_documentos.__get__(mock_gemini, ProcesadorGemini)
    
    clasif, es_consorcio, es_recurso_extranjero, es_facturacion_extranjera = await mock_gemini.clasificar_documentos(archivos_directos=[file1, file2])
    
    # Collision resolved: dup.pdf and dup_1.pdf
    assert "dup.pdf" in clasif
    assert "dup_1.pdf" in clasif
    assert clasif["dup.pdf"]["tipo"] == "FACTURA"
    assert clasif["dup_1.pdf"]["tipo"] == "RUT"


@pytest.mark.asyncio
async def test_4_3_filtro_conservador_descarte():
    """Test 4.3: Filtro conservador descarta basura y conserva PILA/383."""
    mock_clasificador = AsyncMock()
    # Mocking that Gemini returns relevance: False for trash files, and True for important ones
    mock_clasificador.clasificar_documentos.return_value = (
        {
            "factura.pdf": {"tipo": "FACTURA", "relevante": True},
            "pila.pdf": {"tipo": "ANEXO", "relevante": True},
            "deducciones_383.pdf": {"tipo": "ANEXO", "relevante": True},
            "pantallazo.png": {"tipo": "DESCARTABLE", "relevante": False},
            "correo_vacio.txt": {"tipo": "DESCARTABLE", "relevante": False}
        },
        False, False, False
    )
    
    clasificador_docs = ClasificadorDocumentos(mock_clasificador)
    
    factura = Mock(spec=UploadFile, filename="factura.pdf")
    pila = Mock(spec=UploadFile, filename="pila.pdf")
    deducciones = Mock(spec=UploadFile, filename="deducciones_383.pdf")
    pantallazo = Mock(spec=UploadFile, filename="pantallazo.png")
    correo = Mock(spec=UploadFile, filename="correo_vacio.txt")
    
    with patch('app.clasificacion_documentos.guardar_archivo_json'):
        resultado = await clasificador_docs.clasificar(
            archivos_directos=[factura, pila, deducciones, pantallazo, correo],
            textos_preprocesados={},
            provedor="Proveedor SAS",
            nit_administrativo="123",
            nombre_entidad="Entidad",
            impuestos_a_procesar=["retefuente"]
        )
        
    docs = resultado.documentos_clasificados
    assert docs["factura.pdf"]["relevante"] is True
    assert docs["pila.pdf"]["relevante"] is True
    assert docs["deducciones_383.pdf"]["relevante"] is True
    assert docs["pantallazo.png"]["relevante"] is False
    assert docs["correo_vacio.txt"]["relevante"] is False


@pytest.mark.asyncio
async def test_4_4_recorte_prioridad_fiscal():
    """Test 4.4: Recorte por prioridad fiscal cuando hay >20 relevantes."""
    mock_clasificador = AsyncMock()
    
    # 25 files all marked relevant by Gemini initially
    # We will have:
    # 2 facturas
    # 2 RUTs
    # 2 contratos
    # 2 PILA/383
    # 17 ANEXOs
    mock_clasif_return = {}
    for i in range(1, 3):
        mock_clasif_return[f"factura{i}.pdf"] = {"tipo": "FACTURA", "relevante": True}
    for i in range(1, 3):
        mock_clasif_return[f"rut{i}.pdf"] = {"tipo": "RUT", "relevante": True}
    for i in range(1, 3):
        mock_clasif_return[f"contrato{i}.pdf"] = {"tipo": "CONTRATO", "relevante": True}
    for i in range(1, 3):
        mock_clasif_return[f"pila{i}.pdf"] = {"tipo": "ANEXO", "relevante": True}
    for i in range(1, 18):
        mock_clasif_return[f"anexo{i}.pdf"] = {"tipo": "ANEXO", "relevante": True}
        
    mock_clasificador.clasificar_documentos.return_value = (mock_clasif_return, False, False, False)
    
    clasificador_docs = ClasificadorDocumentos(mock_clasificador)
    
    archivos = [Mock(spec=UploadFile, filename=name) for name in mock_clasif_return.keys()]
    
    with patch('app.clasificacion_documentos.guardar_archivo_json'):
        resultado = await clasificador_docs.clasificar(
            archivos_directos=archivos,
            textos_preprocesados={},
            provedor="Proveedor SAS",
            nit_administrativo="123",
            nombre_entidad="Entidad",
            impuestos_a_procesar=["retefuente"]
        )
        
    docs = resultado.documentos_clasificados
    relevantes = [k for k, v in docs.items() if v["relevante"]]
    
    # Should keep exactly 20 relevant files
    assert len(relevantes) == 20
    
    # The 2 facturas, 2 RUTs, 2 contratos, and 2 planillas PILA must be relevant due to higher priority
    for name in ["factura1.pdf", "factura2.pdf", "rut1.pdf", "rut2.pdf", "contrato1.pdf", "contrato2.pdf", "pila1.pdf", "pila2.pdf"]:
        assert docs[name]["relevante"] is True


@pytest.mark.asyncio
async def test_4_5_hard_stop_sin_factura():
    """Test 4.5: Hard stop por ausencia de FACTURA lanza ValueError y aborta."""
    mock_clasificador = AsyncMock()
    # Gemini classifies only RUT and ANEXO, no FACTURA
    mock_clasificador.clasificar_documentos.return_value = (
        {
            "rut.pdf": {"tipo": "RUT", "relevante": True},
            "anexo.pdf": {"tipo": "ANEXO", "relevante": True}
        },
        False, False, False
    )
    
    clasificador_docs = ClasificadorDocumentos(mock_clasificador)
    rut = Mock(spec=UploadFile, filename="rut.pdf")
    anexo = Mock(spec=UploadFile, filename="anexo.pdf")
    
    with pytest.raises(ValueError, match="No se identificó ninguna factura"):
        await clasificador_docs.clasificar(
            archivos_directos=[rut, anexo],
            textos_preprocesados={},
            provedor="Proveedor SAS",
            nit_administrativo="123",
            nombre_entidad="Entidad",
            impuestos_a_procesar=["retefuente"]
        )


@pytest.mark.asyncio
async def test_4_6_multi_factura_relevantes():
    """Test 4.6: Multi-factura (PDF + XML) deja ambas como relevantes."""
    mock_clasificador = AsyncMock()
    mock_clasificador.clasificar_documentos.return_value = (
        {
            "factura.pdf": {"tipo": "FACTURA", "relevante": True},
            "factura.xml": {"tipo": "FACTURA", "relevante": True},
            "rut.pdf": {"tipo": "RUT", "relevante": True}
        },
        False, False, False
    )
    
    clasificador_docs = ClasificadorDocumentos(mock_clasificador)
    f_pdf = Mock(spec=UploadFile, filename="factura.pdf")
    f_xml = Mock(spec=UploadFile, filename="factura.xml")
    rut = Mock(spec=UploadFile, filename="rut.pdf")
    
    with patch('app.clasificacion_documentos.guardar_archivo_json'):
        resultado = await clasificador_docs.clasificar(
            archivos_directos=[f_pdf, f_xml, rut],
            textos_preprocesados={},
            provedor="Proveedor SAS",
            nit_administrativo="123",
            nombre_entidad="Entidad",
            impuestos_a_procesar=["retefuente"]
        )
        
    docs = resultado.documentos_clasificados
    assert docs["factura.pdf"]["relevante"] is True
    assert docs["factura.xml"]["relevante"] is True


@pytest.mark.asyncio
async def test_4_8_descartable_fuerza_relevante_false():
    """Test 4.8: Si Gemini devuelve DESCARTABLE con relevante=true, el merge lo fuerza a false."""

    def side_effect(contents, nombres_archivos=None):
        prompt = contents[0]
        if "analisis_fuente_ingreso" in prompt:
            return json.dumps({
                "es_consorcio": False,
                "ubicacion_proveedor": "Bogota, Colombia",
                "es_fuera_colombia": False,
                "analisis_fuente_ingreso": {
                    "servicio_uso_colombia": True,
                    "evidencias_uso_encontradas": [],
                    "ejecutado_en_colombia": True,
                    "evidencias_ejecucion_encontradas": [],
                    "asistencia_tecnica_colombia": False,
                    "evidencias_asistencia_encontradas": [],
                    "bien_ubicado_colombia": False,
                    "evidencias_bien_encontradas": []
                }
            })
        # Lote: factura valida + un DESCARTABLE que (incorrectamente) viene relevante=true
        return json.dumps({
            "clasificacion": {
                "factura.pdf": {"tipo": "FACTURA", "relevante": True},
                "correo_notificacion.pdf": {"tipo": "DESCARTABLE", "relevante": True}
            },
            "factura_identificada": True,
            "rut_identificado": False
        })

    mock_gemini = AsyncMock(spec=ProcesadorGemini)
    mock_gemini.files_manager = MagicMock()
    mock_gemini.files_manager.upload_file = AsyncMock(return_value=Mock(name="file_ref", display_name="factura.pdf"))
    mock_gemini._files_get_con_retry = AsyncMock(return_value=Mock(name="file_obj", mime_type="application/pdf", uri="uri://doc"))
    mock_gemini._llamar_gemini_hibrido = AsyncMock(side_effect=side_effect)
    mock_gemini._limpiar_respuesta_json = lambda x: x
    mock_gemini._guardar_respuesta = AsyncMock()
    mock_gemini._evaluar_tipo_recurso = MagicMock(return_value=False)
    mock_gemini._determinar_facturacion_extranjera = MagicMock(return_value=False)

    factura = Mock(spec=UploadFile, filename="factura.pdf")
    factura.read = AsyncMock(return_value=b"%PDF-1.4")
    correo = Mock(spec=UploadFile, filename="correo_notificacion.pdf")
    correo.read = AsyncMock(return_value=b"%PDF-1.4")

    mock_gemini.clasificar_documentos = ProcesadorGemini.clasificar_documentos.__get__(mock_gemini, ProcesadorGemini)

    clasif, _, _, _ = await mock_gemini.clasificar_documentos(archivos_directos=[factura, correo])

    assert clasif["factura.pdf"]["relevante"] is True
    # El invariante: DESCARTABLE nunca queda relevante=true
    assert clasif["correo_notificacion.pdf"]["tipo"] == "DESCARTABLE"
    assert clasif["correo_notificacion.pdf"]["relevante"] is False


@pytest.mark.asyncio
async def test_4_7_cache_archivos_filtrado():
    """Test 4.7: El cache_archivos queda filtrado al conjunto relevante."""
    mock_gemini = AsyncMock(spec=ProcesadorGemini)
    mock_gemini.preparar_archivos_para_workers_paralelos = AsyncMock(return_value={
        "factura.pdf": "ref1",
        "rut.pdf": "ref2"
    })
    
    preparador_cache = PreparadorCacheArchivos(mock_gemini)
    
    f_pdf = Mock(spec=UploadFile, filename="factura.pdf")
    rut = Mock(spec=UploadFile, filename="rut.pdf")
    basura = Mock(spec=UploadFile, filename="basura.png")
    
    documentos_clasificados = {
        "factura.pdf": {"categoria": "FACTURA", "relevante": True},
        "rut.pdf": {"categoria": "RUT", "relevante": True},
        "basura.png": {"categoria": "DESCARTABLE", "relevante": False}
    }
    
    # We patch obtener_nombre_archivo to return matching filename mock values
    with patch('app.preparacion_tareas_analisis.PreparadorCacheArchivos.preparar_cache', 
               wraps=preparador_cache.preparar_cache) as wrap_cache:
        
        cache = await preparador_cache.preparar_cache(
            archivos_directos=[f_pdf, rut, basura],
            documentos_clasificados=documentos_clasificados
        )
        
    # The actual call to preparar_archivos_para_workers_paralelos should only get the two relevant files
    mock_gemini.preparar_archivos_para_workers_paralelos.assert_called_once()
    passed_args = mock_gemini.preparar_archivos_para_workers_paralelos.call_args[0][0]
    assert len(passed_args) == 2
    assert passed_args[0].filename == "factura.pdf"
    assert passed_args[1].filename == "rut.pdf"
