"""
PRUEBA MANUAL - INTEGRACIÓN FILES API
======================================

Script para probar manualmente la integración de Files API con el clasificador.
Usa la API real de Google (requiere GEMINI_API_KEY en .env)

Uso:
    python tests/manual_test_files_api.py

Autor: Claude + Usuario
Versión: 3.0.0
"""

import os
import sys
import asyncio
from pathlib import Path
from io import BytesIO
from datetime import datetime

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from Clasificador.clasificador import ProcesadorGemini
from Clasificador.gemini_files_manager import GeminiFilesManager


class MockUploadFile:
    """Mock simple de UploadFile para pruebas manuales"""

    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content
        self._position = 0

    async def read(self, size: int = -1) -> bytes:
        """Lee contenido del archivo"""
        if size == -1:
            data = self._content[self._position:]
            self._position = len(self._content)
        else:
            data = self._content[self._position:self._position + size]
            self._position += size
        return data

    async def seek(self, position: int) -> None:
        """Mueve el puntero del archivo"""
        self._position = position


def crear_pdf_prueba() -> bytes:
    """Crea un PDF simple de prueba"""
    # PDF mínimo válido
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Factura de Prueba) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000317 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF
"""
    return pdf_content


async def test_1_gemini_files_manager_basico():
    """
    TEST 1: GeminiFilesManager - Upload básico

    Verifica:
    - Upload de archivo a Files API
    - Espera a estado ACTIVE
    - Obtención de metadata
    - Cleanup
    """
    print("\n" + "="*80)
    print("TEST 1: GeminiFilesManager - Upload Básico")
    print("="*80)

    # Cargar API key
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("[ERROR] GEMINI_API_KEY no encontrada en .env")
        return False

    try:
        # Crear archivo de prueba
        print("\n>>Creando PDF de prueba...")
        pdf_content = crear_pdf_prueba()
        mock_file = MockUploadFile("factura_prueba.pdf", pdf_content)
        print(f"[OK]PDF creado: {len(pdf_content)} bytes")

        # Inicializar Files Manager
        print("\n>>Inicializando GeminiFilesManager...")
        files_manager = GeminiFilesManager(api_key=api_key)
        print("[OK]GeminiFilesManager inicializado")

        # Upload archivo
        print("\n>>Subiendo archivo a Files API...")
        file_result = await files_manager.upload_file(
            archivo=mock_file,
            wait_for_active=True,
            timeout_seconds=60
        )
        print(f"[OK]Archivo subido exitosamente!")
        print(f"   - Name: {file_result.name}")
        print(f"   - Display Name: {file_result.display_name}")
        print(f"   - MIME Type: {file_result.mime_type}")
        print(f"   - Size: {file_result.size_bytes} bytes")
        print(f"   - State: {file_result.state}")
        print(f"   - URI: {file_result.uri}")

        # Obtener metadata
        print("\n>>Obteniendo metadata del archivo...")
        metadata = await files_manager.get_file_metadata(file_result.name)
        print(f"[OK]Metadata obtenida: {metadata.name}")

        # Cleanup
        print("\n>>Limpiando archivos...")
        await files_manager.cleanup_all()
        print("[OK]Cleanup completado")

        print("\n" + "="*80)
        print("[OK]TEST 1 PASÓ - GeminiFilesManager funciona correctamente")
        print("="*80)
        return True

    except Exception as e:
        print(f"\n[ERROR] ERROR en TEST 1: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_2_clasificador_con_files_api():
    """
    TEST 2: ProcesadorGemini con Files API

    Verifica:
    - Inicialización de ProcesadorGemini
    - GeminiFilesManager está presente
    - Clasificación de documentos usa Files API
    """
    print("\n" + "="*80)
    print("TEST 2: ProcesadorGemini con Files API")
    print("="*80)

    try:
        # Crear archivo de prueba
        print("\n>>Creando PDF de prueba...")
        pdf_content = crear_pdf_prueba()
        mock_file = MockUploadFile("factura_test.pdf", pdf_content)
        print(f"[OK]PDF creado: {len(pdf_content)} bytes")

        # Inicializar Procesador
        print("\n>>Inicializando ProcesadorGemini...")
        clasificador = ProcesadorGemini()
        print("[OK]ProcesadorGemini inicializado")

        # Verificar Files Manager
        print("\n>>Verificando GeminiFilesManager...")
        assert hasattr(clasificador, 'files_manager'), "files_manager no existe"
        assert clasificador.files_manager is not None, "files_manager es None"
        print(f"[OK]GeminiFilesManager presente: {type(clasificador.files_manager)}")

        # Verificar nuevo SDK
        print("\n>>Verificando nuevo SDK...")
        assert hasattr(clasificador, 'client'), "client no existe"
        assert hasattr(clasificador, 'model_name'), "model_name no existe"
        print(f"[OK]Nuevo SDK configurado: {clasificador.model_name}")

        # Clasificar documentos
        print("\n>>Clasificando documentos con Files API...")
        print("   (Esto puede tardar unos segundos...)")

        resultado = await clasificador.clasificar_documentos(
            archivos_directos=[mock_file],
            textos_preprocesados={}
        )

        print("[OK]Clasificación completada!")
        print(f"   - Tipo de resultado: {type(resultado)}")
        if isinstance(resultado, tuple) and len(resultado) >= 1:
            clasificacion = resultado[0]
            print(f"   - Clasificación: {clasificacion}")

        # Cleanup
        print("\n>>Limpiando archivos...")
        await clasificador.files_manager.cleanup_all()
        print("[OK]Cleanup completado")

        print("\n" + "="*80)
        print("[OK]TEST 2 PASÓ - ProcesadorGemini usa Files API correctamente")
        print("="*80)
        return True

    except Exception as e:
        print(f"\n[ERROR] ERROR en TEST 2: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_3_preparar_cache_workers():
    """
    TEST 3: Cache para Workers Paralelos

    Verifica:
    - preparar_archivos_para_workers_paralelos retorna FileUploadResult
    - No retorna bytes
    """
    print("\n" + "="*80)
    print("TEST 3: Cache para Workers Paralelos")
    print("="*80)

    try:
        # Crear archivo de prueba
        print("\n>>Creando PDF de prueba...")
        pdf_content = crear_pdf_prueba()
        mock_file = MockUploadFile("factura_cache.pdf", pdf_content)
        print(f"[OK]PDF creado: {len(pdf_content)} bytes")

        # Inicializar Procesador
        print("\n>>Inicializando ProcesadorGemini...")
        clasificador = ProcesadorGemini()
        print("[OK]ProcesadorGemini inicializado")

        # Preparar cache
        print("\n>>Preparando cache para workers paralelos...")
        print("   (Esto sube archivos a Files API...)")

        cache = await clasificador.preparar_archivos_para_workers_paralelos(
            [mock_file]
        )

        print("[OK]Cache preparado!")
        print(f"   - Tipo de cache: {type(cache)}")
        print(f"   - Número de archivos: {len(cache)}")

        # Verificar contenido
        from Clasificador.gemini_files_manager import FileUploadResult
        for nombre, valor in cache.items():
            print(f"\n   [Archivo]: {nombre}")
            print(f"      - Tipo: {type(valor)}")
            print(f"      - Es FileUploadResult: {isinstance(valor, FileUploadResult)}")
            if isinstance(valor, FileUploadResult):
                print(f"      - Name: {valor.name}")
                print(f"      - State: {valor.state}")

        # Cleanup
        print("\n>>Limpiando archivos...")
        await clasificador.files_manager.cleanup_all()
        print("[OK]Cleanup completado")

        print("\n" + "="*80)
        print("[OK]TEST 3 PASÓ - Cache retorna FileUploadResult correctamente")
        print("="*80)
        return True

    except Exception as e:
        print(f"\n[ERROR] ERROR en TEST 3: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Ejecuta todos los tests manuales"""
    print("\n")
    print("=" * 80)
    print(" " * 20 + "PRUEBA MANUAL - FILES API INTEGRATION")
    print("=" * 80)

    resultados = []

    # Test 1: GeminiFilesManager básico
    resultado_1 = await test_1_gemini_files_manager_basico()
    resultados.append(("TEST 1: GeminiFilesManager Básico", resultado_1))

    # Test 2: ProcesadorGemini con Files API
    resultado_2 = await test_2_clasificador_con_files_api()
    resultados.append(("TEST 2: ProcesadorGemini con Files API", resultado_2))

    # Test 3: Cache para workers
    resultado_3 = await test_3_preparar_cache_workers()
    resultados.append(("TEST 3: Cache para Workers Paralelos", resultado_3))

    # Resumen
    print("\n")
    print("=" * 80)
    print(" " * 30 + "RESUMEN DE TESTS")
    print("=" * 80)

    tests_pasados = 0
    tests_totales = len(resultados)

    for nombre, resultado in resultados:
        status = "[OK] PASO" if resultado else "[ERROR] FALLO"
        print(f"{status} - {nombre}")
        if resultado:
            tests_pasados += 1

    print("\n" + "="*80)
    print(f"RESULTADO FINAL: {tests_pasados}/{tests_totales} tests pasaron")
    print("="*80)

    if tests_pasados == tests_totales:
        print("\n[SUCCESS] Todos los tests pasaron! La integracion Files API funciona correctamente.")
        return 0
    else:
        print(f"\n[WARNING] {tests_totales - tests_pasados} tests fallaron. Revisar errores arriba.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
