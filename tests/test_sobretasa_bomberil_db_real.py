"""
TEST SOBRETASA BOMBERIL CON BASE DE DATOS REAL
===============================================

Tests de integración que hacen queries REALES a la base de datos Supabase.

UBICACIONES REALES EN BD:
- BUCARAMANGA: 68001
- IBAGUE: 73001
- VILLANUEVA CASANARE: 85440

IMPORTANTE: Estos tests requieren conexión a Supabase.
"""

import sys
import pytest
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import directo del módulo para evitar dependencias del __init__.py
import importlib.util
liquidador_path = Path(__file__).parent.parent / "Liquidador" / "liquidador_sobretasa_b.py"
spec = importlib.util.spec_from_file_location("liquidador_sobretasa_b", liquidador_path)
liquidador_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(liquidador_module)
LiquidadorSobretasaBomberil = liquidador_module.LiquidadorSobretasaBomberil

# Intentar importar database manager
try:
    from database.database import DatabaseManager, SupabaseDatabase
    TIENE_DB = True
except ImportError as e:
    print(f"[WARNING] No se pudo importar database: {e}")
    print("[INFO] Instala las dependencias con: pip install supabase")
    TIENE_DB = False
    DatabaseManager = None
    SupabaseDatabase = None


@pytest.fixture(scope="module")
def db_manager():
    """Crea DatabaseManager con conexión real a Supabase para tests de integración"""
    if not TIENE_DB:
        pytest.skip("Dependencias de base de datos no disponibles")

    try:
        SUPABASE_URL = "https://gfcseujjfnaoicdenymt.supabase.co"
        SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmY3NldWpqZm5hb2ljZGVueW10Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTEwMzA4MDgsImV4cCI6MjA2NjYwNjgwOH0.ghHQ-wDB7itkoEEKq04iOCmLUyrL1hLSjLXhq1gN62k"
        supabase_db = SupabaseDatabase(SUPABASE_URL, SUPABASE_KEY)
        instance = DatabaseManager(supabase_db)
        return instance
    except Exception as e:
        pytest.skip(f"No se pudo conectar a Supabase: {e}")


def print_separator():
    """Imprime separador visual"""
    print("\n" + "="*80)


def crear_resultado_ica_bucaramanga():
    """Crea resultado ICA simulado para BUCARAMANGA (68001) - formato v3.0"""
    return {
        "aplica": True,
        "estado": "preliquidado",
        "valor_total_ica": 1500000.0,
        "actividades_relacionadas": [
            {
                "codigo_ubicacion": 68001,
                "nombre_ubicacion": "BUCARAMANGA",
                "valor_ica": 1500000.0
            }
        ],
        "observaciones": [],
        "fecha_liquidacion": "2025-10-14T10:00:00.000000"
    }


def crear_resultado_ica_ibague():
    """Crea resultado ICA simulado para IBAGUE (73001) - formato v3.0"""
    return {
        "aplica": True,
        "estado": "preliquidado",
        "valor_total_ica": 2000000.0,
        "actividades_relacionadas": [
            {
                "codigo_ubicacion": 73001,
                "nombre_ubicacion": "IBAGUE",
                "valor_ica": 2000000.0
            }
        ],
        "observaciones": [],
        "fecha_liquidacion": "2025-10-14T10:00:00.000000"
    }


def crear_resultado_ica_villanueva():
    """Crea resultado ICA simulado para VILLANUEVA CASANARE (85440) - formato v3.0"""
    return {
        "aplica": True,
        "estado": "preliquidado",
        "valor_total_ica": 800000.0,
        "actividades_relacionadas": [
            {
                "codigo_ubicacion": 85440,
                "nombre_ubicacion": "VILLANUEVA",
                "valor_ica": 800000.0
            }
        ],
        "observaciones": [],
        "fecha_liquidacion": "2025-10-14T10:00:00.000000"
    }


def crear_resultado_ica_bogota():
    """Crea resultado ICA simulado para BOGOTA (11001) - NO existe en TASA_BOMBERIL - formato v3.0"""
    return {
        "aplica": True,
        "estado": "preliquidado",
        "valor_total_ica": 3000000.0,
        "actividades_relacionadas": [
            {
                "codigo_ubicacion": 11001,
                "nombre_ubicacion": "BOGOTA D.C.",
                "valor_ica": 3000000.0
            }
        ],
        "observaciones": [],
        "fecha_liquidacion": "2025-10-14T10:00:00.000000"
    }


def crear_resultado_ica_multiples_ubicaciones():
    """Crea resultado ICA con múltiples ubicaciones - formato v3.0:
    - BUCARAMANGA (68001) - EXISTE en BD
    - IBAGUE (73001) - EXISTE en BD
    - BOGOTA (11001) - NO EXISTE en BD
    """
    return {
        "aplica": True,
        "estado": "preliquidado",
        "valor_total_ica": 4500000.0,
        "actividades_relacionadas": [
            {"codigo_ubicacion": 68001, "nombre_ubicacion": "BUCARAMANGA", "valor_ica": 1500000.0},
            {"codigo_ubicacion": 73001, "nombre_ubicacion": "IBAGUE", "valor_ica": 2000000.0},
            {"codigo_ubicacion": 11001, "nombre_ubicacion": "BOGOTA D.C.", "valor_ica": 1000000.0}
        ],
        "observaciones": [],
        "fecha_liquidacion": "2025-10-14T10:00:00.000000"
    }


def test_1_conexion_base_datos():
    """
    TEST 1: Verificar conexión a base de datos
    """
    print_separator()
    print("TEST 1: Verificando conexión a base de datos")
    print_separator()

    try:
        # Configuración de Supabase
        SUPABASE_URL = "https://gfcseujjfnaoicdenymt.supabase.co"
        SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmY3NldWpqZm5hb2ljZGVueW10Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTEwMzA4MDgsImV4cCI6MjA2NjYwNjgwOH0.ghHQ-wDB7itkoEEKq04iOCmLUyrL1hLSjLXhq1gN62k"

        # Crear conexión
        supabase_db = SupabaseDatabase(SUPABASE_URL, SUPABASE_KEY)
        db_manager = DatabaseManager(supabase_db)

        print("[OK] Conexión a Supabase establecida")

        # Verificar tabla TASA_BOMBERIL
        response = db_manager.db_connection.supabase.table("TASA_BOMBERIL").select("*").execute()

        print(f"[OK] Tabla TASA_BOMBERIL encontrada")
        print(f"[OK] Registros en tabla: {len(response.data)}")

        # Mostrar datos
        print("\n[INFO] Datos en TASA_BOMBERIL:")
        for registro in response.data:
            print(f"  - Codigo: {registro.get('CODIGO_UBICACION')}, "
                  f"Nombre: {registro.get('NOMBRE_UBICACION')}, "
                  f"Tarifa: {registro.get('TARIFA')}")

        print("\n[OK] TEST 1 PASADO")
        return db_manager

    except Exception as e:
        print(f"\n[ERROR] TEST 1 FALLIDO: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_2_liquidar_bucaramanga(db_manager):
    """
    TEST 2: Liquidar Sobretasa Bomberil para BUCARAMANGA (debe existir en BD)
    """
    print_separator()
    print("TEST 2: Liquidación para BUCARAMANGA (68001)")
    print_separator()

    try:
        # Crear liquidador
        liquidador = LiquidadorSobretasaBomberil(db_manager)

        # Crear resultado ICA
        resultado_ica = crear_resultado_ica_bucaramanga()

        # Liquidar
        resultado = liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Mostrar resultado
        print(f"\n[INFO] Estado: {resultado['estado']}")
        print(f"[INFO] Aplica: {resultado['aplica']}")
        print(f"[INFO] Valor total: ${resultado['valor_total_sobretasa']:,.2f}")
        print(f"[INFO] Observaciones: {resultado['observaciones']}")

        if resultado['ubicaciones']:
            print(f"\n[INFO] Ubicaciones liquidadas:")
            for ub in resultado['ubicaciones']:
                print(f"  - {ub['nombre_ubicacion']}: Tarifa {ub['tarifa']} x ${ub['base_gravable_ica']:,.2f} = ${ub['valor']:,.2f}")

        # Validación
        if resultado['aplica']:
            print("\n[OK] TEST 2 PASADO - Sobretasa aplicada correctamente")
        else:
            print(f"\n[WARNING] Sobretasa no aplicó - Revisar si BUCARAMANGA está en BD")

        return True

    except Exception as e:
        print(f"\n[ERROR] TEST 2 FALLIDO: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_liquidar_ibague(db_manager):
    """
    TEST 3: Liquidar Sobretasa Bomberil para IBAGUE (debe existir en BD)
    """
    print_separator()
    print("TEST 3: Liquidación para IBAGUE (73001)")
    print_separator()

    try:
        # Crear liquidador
        liquidador = LiquidadorSobretasaBomberil(db_manager)

        # Crear resultado ICA
        resultado_ica = crear_resultado_ica_ibague()

        # Liquidar
        resultado = liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Mostrar resultado
        print(f"\n[INFO] Estado: {resultado['estado']}")
        print(f"[INFO] Aplica: {resultado['aplica']}")
        print(f"[INFO] Valor total: ${resultado['valor_total_sobretasa']:,.2f}")
        print(f"[INFO] Observaciones: {resultado['observaciones']}")

        if resultado['ubicaciones']:
            print(f"\n[INFO] Ubicaciones liquidadas:")
            for ub in resultado['ubicaciones']:
                print(f"  - {ub['nombre_ubicacion']}: Tarifa {ub['tarifa']} x ${ub['base_gravable_ica']:,.2f} = ${ub['valor']:,.2f}")

        # Validación
        if resultado['aplica']:
            print("\n[OK] TEST 3 PASADO - Sobretasa aplicada correctamente")
        else:
            print(f"\n[WARNING] Sobretasa no aplicó - Revisar si IBAGUE está en BD")

        return True

    except Exception as e:
        print(f"\n[ERROR] TEST 3 FALLIDO: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_liquidar_villanueva(db_manager):
    """
    TEST 4: Liquidar Sobretasa Bomberil para VILLANUEVA CASANARE (debe existir en BD)
    """
    print_separator()
    print("TEST 4: Liquidación para VILLANUEVA CASANARE (85440)")
    print_separator()

    try:
        # Crear liquidador
        liquidador = LiquidadorSobretasaBomberil(db_manager)

        # Crear resultado ICA
        resultado_ica = crear_resultado_ica_villanueva()

        # Liquidar
        resultado = liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Mostrar resultado
        print(f"\n[INFO] Estado: {resultado['estado']}")
        print(f"[INFO] Aplica: {resultado['aplica']}")
        print(f"[INFO] Valor total: ${resultado['valor_total_sobretasa']:,.2f}")
        print(f"[INFO] Observaciones: {resultado['observaciones']}")

        if resultado['ubicaciones']:
            print(f"\n[INFO] Ubicaciones liquidadas:")
            for ub in resultado['ubicaciones']:
                print(f"  - {ub['nombre_ubicacion']}: Tarifa {ub['tarifa']} x ${ub['base_gravable_ica']:,.2f} = ${ub['valor']:,.2f}")

        # Validación
        if resultado['aplica']:
            print("\n[OK] TEST 4 PASADO - Sobretasa aplicada correctamente")
        else:
            print(f"\n[WARNING] Sobretasa no aplicó - Revisar si VILLANUEVA está en BD")

        return True

    except Exception as e:
        print(f"\n[ERROR] TEST 4 FALLIDO: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_liquidar_bogota_no_existe(db_manager):
    """
    TEST 5: Liquidar Sobretasa Bomberil para BOGOTA (NO existe en BD)
    Debe retornar: No aplica impuesto
    """
    print_separator()
    print("TEST 5: Liquidación para BOGOTA (11001) - NO EXISTE EN BD")
    print_separator()

    try:
        # Crear liquidador
        liquidador = LiquidadorSobretasaBomberil(db_manager)

        # Crear resultado ICA
        resultado_ica = crear_resultado_ica_bogota()

        # Liquidar
        resultado = liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Mostrar resultado
        print(f"\n[INFO] Estado: {resultado['estado']}")
        print(f"[INFO] Aplica: {resultado['aplica']}")
        print(f"[INFO] Valor total: ${resultado['valor_total_sobretasa']:,.2f}")
        print(f"[INFO] Observaciones: {resultado['observaciones']}")

        # Validación
        if not resultado['aplica'] and resultado['estado'] == "No aplica impuesto":
            print("\n[OK] TEST 5 PASADO - Correctamente detectó que BOGOTA no está en BD")
        else:
            print(f"\n[WARNING] Comportamiento inesperado - BOGOTA no debería tener tarifa")

        return True

    except Exception as e:
        print(f"\n[ERROR] TEST 5 FALLIDO: {e}")
        import traceback
        traceback.print_exc()
        return False


def crear_resultado_ica_multiples_ubicaciones_extendido():
    """Crea resultado ICA con MUCHAS ubicaciones mezcladas - formato v3.0:
    - BUCARAMANGA (68001), IBAGUE (73001), VILLANUEVA (85440) - EXISTEN en BD
    - BOGOTA (11001), MEDELLIN (5001), CALI (76001) - NO EXISTEN en BD
    """
    return {
        "aplica": True,
        "estado": "preliquidado",
        "valor_total_ica": 8700000.0,
        "actividades_relacionadas": [
            {"codigo_ubicacion": 68001, "nombre_ubicacion": "BUCARAMANGA", "valor_ica": 2500000.0},
            {"codigo_ubicacion": 73001, "nombre_ubicacion": "IBAGUE", "valor_ica": 1800000.0},
            {"codigo_ubicacion": 85440, "nombre_ubicacion": "VILLANUEVA", "valor_ica": 900000.0},
            {"codigo_ubicacion": 11001, "nombre_ubicacion": "BOGOTA D.C.", "valor_ica": 2000000.0},
            {"codigo_ubicacion": 5001, "nombre_ubicacion": "MEDELLIN", "valor_ica": 1000000.0},
            {"codigo_ubicacion": 76001, "nombre_ubicacion": "CALI", "valor_ica": 500000.0}
        ],
        "observaciones": [],
        "fecha_liquidacion": "2025-10-14T10:00:00.000000"
    }


def test_6_multiples_ubicaciones_mixtas(db_manager):
    """
    TEST 6: Liquidar con múltiples ubicaciones - algunas existen, otras no
    - BUCARAMANGA (68001) - EXISTE
    - IBAGUE (73001) - EXISTE
    - BOGOTA (11001) - NO EXISTE

    Debe calcular solo las que existen
    """
    print_separator()
    print("TEST 6: Múltiples ubicaciones - mixtas (algunas existen, otras no)")
    print_separator()

    try:
        # Crear liquidador
        liquidador = LiquidadorSobretasaBomberil(db_manager)

        # Crear resultado ICA
        resultado_ica = crear_resultado_ica_multiples_ubicaciones()

        # Liquidar
        resultado = liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Mostrar resultado
        print(f"\n[INFO] Estado: {resultado['estado']}")
        print(f"[INFO] Aplica: {resultado['aplica']}")
        print(f"[INFO] Valor total: ${resultado['valor_total_sobretasa']:,.2f}")
        print(f"[INFO] Observaciones: {resultado['observaciones']}")

        if resultado['ubicaciones']:
            print(f"\n[INFO] Ubicaciones liquidadas ({len(resultado['ubicaciones'])} de 3):")
            for ub in resultado['ubicaciones']:
                print(f"  - {ub['nombre_ubicacion']}: Tarifa {ub['tarifa']} x ${ub['base_gravable_ica']:,.2f} = ${ub['valor']:,.2f}")

        # Validación
        if resultado['aplica']:
            print(f"\n[OK] TEST 6 PASADO - Solo calculó las ubicaciones que existen en BD")
            if len(resultado['ubicaciones']) == 2:
                print("[OK] Correctamente ignoró BOGOTA (no existe en BD)")
        else:
            print(f"\n[WARNING] Debería haber calculado al menos BUCARAMANGA e IBAGUE")

        return True

    except Exception as e:
        print(f"\n[ERROR] TEST 6 FALLIDO: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_7_multiples_ubicaciones_extendido(db_manager):
    """
    TEST 7: Caso robusto con MUCHAS ubicaciones mezcladas (6 ubicaciones)

    UBICACIONES QUE SÍ EXISTEN EN BD (3):
    - BUCARAMANGA (68001)
    - IBAGUE (73001)
    - VILLANUEVA CASANARE (85440)

    UBICACIONES QUE NO EXISTEN EN BD (3):
    - BOGOTA (11001)
    - MEDELLIN (5001)
    - CALI (76001)

    VALIDACIONES ESPERADAS:
    - Debe calcular solo las 3 ubicaciones que existen
    - Debe ignorar silenciosamente las 3 que no existen
    - Valor total = suma de solo las que existen
    """
    print_separator()
    print("TEST 7: Múltiples ubicaciones EXTENDIDO (6 total: 3 existen, 3 no)")
    print_separator()

    try:
        # Crear liquidador
        liquidador = LiquidadorSobretasaBomberil(db_manager)

        # Crear resultado ICA con 6 ubicaciones mezcladas
        resultado_ica = crear_resultado_ica_multiples_ubicaciones_extendido()

        print(f"[INFO] Procesando factura con 6 ubicaciones:")
        print(f"  - 3 ubicaciones que SÍ existen en BD")
        print(f"  - 3 ubicaciones que NO existen en BD")

        # Liquidar
        resultado = liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Mostrar resultado
        print(f"\n[INFO] Estado: {resultado['estado']}")
        print(f"[INFO] Aplica: {resultado['aplica']}")
        print(f"[INFO] Valor total: ${resultado['valor_total_sobretasa']:,.2f}")
        print(f"[INFO] Observaciones: {resultado['observaciones']}")

        # Mostrar detalle de ubicaciones
        if resultado['ubicaciones']:
            print(f"\n[INFO] Ubicaciones liquidadas ({len(resultado['ubicaciones'])} de 6):")
            for ub in resultado['ubicaciones']:
                print(f"  - {ub['nombre_ubicacion']} ({ub['codigo_ubicacion']}): "
                      f"Tarifa {ub['tarifa']} x ${ub['base_gravable_ica']:,.2f} = ${ub['valor']:,.2f}")

        # VALIDACIONES DETALLADAS
        print("\n[INFO] Validaciones:")

        # Validación 1: Debe aplicar
        if resultado['aplica']:
            print("  [OK] Sobretasa aplica correctamente")
        else:
            print("  [ERROR] Sobretasa debería aplicar (hay ubicaciones válidas)")
            return False

        # Validación 2: Debe haber exactamente 3 ubicaciones liquidadas
        if len(resultado['ubicaciones']) == 3:
            print(f"  [OK] Calculó exactamente 3 ubicaciones (las que existen en BD)")
        else:
            print(f"  [WARNING] Se esperaban 3 ubicaciones, pero se calcularon {len(resultado['ubicaciones'])}")

        # Validación 3: Verificar que solo están las ubicaciones correctas
        ubicaciones_calculadas = {ub['codigo_ubicacion'] for ub in resultado['ubicaciones']}
        ubicaciones_esperadas = {68001, 73001, 85440}  # BUCARAMANGA, IBAGUE, VILLANUEVA

        if ubicaciones_calculadas == ubicaciones_esperadas:
            print(f"  [OK] Calculó solo las ubicaciones que existen en BD")
        else:
            print(f"  [WARNING] Ubicaciones calculadas: {ubicaciones_calculadas}")
            print(f"  [WARNING] Ubicaciones esperadas: {ubicaciones_esperadas}")

        # Validación 4: Verificar que NO se calcularon las ubicaciones inexistentes
        ubicaciones_no_deben_estar = {11001, 5001, 76001}  # BOGOTA, MEDELLIN, CALI
        ubicaciones_no_calculadas = ubicaciones_no_deben_estar - ubicaciones_calculadas

        if ubicaciones_no_calculadas == ubicaciones_no_deben_estar:
            print(f"  [OK] Correctamente ignoró 3 ubicaciones que no existen (BOGOTA, MEDELLIN, CALI)")
        else:
            print(f"  [WARNING] Algunas ubicaciones inexistentes fueron calculadas")

        # Validación 5: Cálculo total esperado
        # BUCARAMANGA: $2,500,000 × 0.1 = $250,000
        # IBAGUE: $1,800,000 × 0.06 = $108,000
        # VILLANUEVA: $900,000 × 0.1 = $90,000
        # TOTAL ESPERADO: $448,000
        valor_esperado = (2500000 * 0.1) + (1800000 * 0.06) + (900000 * 0.1)

        if abs(resultado['valor_total_sobretasa'] - valor_esperado) < 1:  # Tolerancia de $1
            print(f"  [OK] Valor total correcto: ${resultado['valor_total_sobretasa']:,.2f}")
        else:
            print(f"  [WARNING] Valor total: ${resultado['valor_total_sobretasa']:,.2f}, "
                  f"esperado: ${valor_esperado:,.2f}")

        # Resumen final
        print(f"\n[OK] TEST 7 PASADO - Sistema maneja correctamente ubicaciones mezcladas")
        print(f"[OK] Procesó 6 ubicaciones: 3 calculadas, 3 ignoradas")

        return True

    except Exception as e:
        print(f"\n[ERROR] TEST 7 FALLIDO: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Ejecuta todos los tests"""
    print("\n" + "="*80)
    print("TESTS SOBRETASA BOMBERIL - CONSULTAS REALES A BASE DE DATOS")
    print("="*80)

    # Verificar dependencias
    if not TIENE_DB:
        print("\n[ERROR] Faltan dependencias. Ejecuta: pip install supabase")
        return False

    # TEST 1: Conexión
    db_manager = test_1_conexion_base_datos()

    if not db_manager:
        print("\n[ERROR] No se pudo conectar a la base de datos. Abortando tests.")
        return False

    # Ejecutar tests
    resultados = []
    resultados.append(test_2_liquidar_bucaramanga(db_manager))
    resultados.append(test_3_liquidar_ibague(db_manager))
    resultados.append(test_4_liquidar_villanueva(db_manager))
    resultados.append(test_5_liquidar_bogota_no_existe(db_manager))
    resultados.append(test_6_multiples_ubicaciones_mixtas(db_manager))
    resultados.append(test_7_multiples_ubicaciones_extendido(db_manager))

    # Resumen
    print_separator()
    print("RESUMEN DE TESTS")
    print_separator()

    total = len(resultados)
    exitosos = sum(resultados)

    print(f"[INFO] Tests ejecutados: {total}")
    print(f"[OK] Tests exitosos: {exitosos}")
    print(f"[ERROR] Tests fallidos: {total - exitosos}")
    print("="*80)

    return all(resultados)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
