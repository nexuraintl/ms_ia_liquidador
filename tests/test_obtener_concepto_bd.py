"""
Test para verificar la función obtener_concepto_por_index de la base de datos

Prueba específica para:
- estructura_contable = 18
- index = 135
"""

import sys
import os
from dotenv import load_dotenv

# Agregar directorio padre al path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from database import DatabaseManager, SupabaseDatabase

def test_obtener_concepto_por_index():
    """
    Test específico para obtener_concepto_por_index
    estructura_contable=18, index=135
    """
    print("=" * 80)
    print("TEST: obtener_concepto_por_index")
    print("=" * 80)

    # Cargar variables de entorno
    load_dotenv()

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Variables de entorno SUPABASE_URL y SUPABASE_KEY no configuradas")
        return

    print(f"URL: {SUPABASE_URL}")
    print(f"Key: {SUPABASE_KEY[:20]}...")

    # Crear conexión
    try:
        supabase_db = SupabaseDatabase(SUPABASE_URL, SUPABASE_KEY)
        db_manager = DatabaseManager(supabase_db)
        print("[OK] Conexion establecida correctamente\n")
    except Exception as e:
        print(f"[ERROR] Error estableciendo conexion: {e}")
        return

    # Parámetros del test
    estructura_contable = 18
    index = 135

    print(f"Parámetros de prueba:")
    print(f"  - estructura_contable: {estructura_contable}")
    print(f"  - index: {index}")
    print()

    # Ejecutar consulta
    print("Ejecutando consulta...")
    try:
        resultado = db_manager.obtener_concepto_por_index(index, estructura_contable)

        print("\n" + "=" * 80)
        print("RESULTADO DE LA CONSULTA")
        print("=" * 80)

        if resultado['success']:
            print("[OK] Consulta EXITOSA")
            print()

            data = resultado['data']
            print("DATOS OBTENIDOS:")
            print(f"  - descripcion_concepto: {data.get('descripcion_concepto')}")
            print(f"  - base: {data.get('base')}")
            print(f"  - porcentaje: {data.get('porcentaje')}")
            print(f"  - index: {data.get('index')}")
            print(f"  - estructura_contable: {data.get('estructura_contable')}")
            print()

            # Validar datos
            print("VALIDACIONES:")
            porcentaje = data.get('porcentaje')
            base = data.get('base')

            if porcentaje is not None:
                try:
                    porcentaje_float = float(porcentaje)
                    tarifa_calculada = porcentaje_float / 100
                    print(f"  [OK] Porcentaje valido: {porcentaje}%")
                    print(f"  [OK] Tarifa calculada: {tarifa_calculada} ({porcentaje}% / 100)")
                except (ValueError, TypeError) as e:
                    print(f"  [ERROR] Error convirtiendo porcentaje: {e}")
            else:
                print("  [WARNING] Porcentaje es None")

            if base is not None:
                try:
                    base_float = float(base)
                    print(f"  [OK] Base valida: ${base_float:,.2f}")
                except (ValueError, TypeError) as e:
                    print(f"  [ERROR] Error convirtiendo base: {e}")
            else:
                print("  [WARNING] Base es None")

            print()
            print("DATOS RAW:")
            print(f"  {resultado.get('raw_data')}")

        else:
            print("[ERROR] Consulta FALLIDA")
            print(f"Mensaje: {resultado['message']}")
            if 'error' in resultado:
                print(f"Error: {resultado['error']}")

    except Exception as e:
        print(f"\n[ERROR] EXCEPCION durante la consulta: {e}")
        import traceback
        print("\nTraceback completo:")
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("FIN DEL TEST")
    print("=" * 80)


def test_listar_conceptos_estructura_18():
    """
    Test adicional: Listar todos los conceptos de estructura_contable=18
    """
    print("\n\n")
    print("=" * 80)
    print("TEST ADICIONAL: Listar conceptos de estructura_contable=18")
    print("=" * 80)

    # Cargar variables de entorno
    load_dotenv()

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    # Crear conexión
    try:
        supabase_db = SupabaseDatabase(SUPABASE_URL, SUPABASE_KEY)
        db_manager = DatabaseManager(supabase_db)
    except Exception as e:
        print(f"Error estableciendo conexión: {e}")
        return

    estructura_contable = 18

    print(f"Buscando todos los conceptos para estructura_contable={estructura_contable}...")

    try:
        resultado = db_manager.obtener_conceptos_retefuente(estructura_contable)

        if resultado['success']:
            print(f"\n[OK] Se encontraron {resultado['total']} conceptos")
            print("\nPrimeros 10 conceptos:")

            for i, concepto in enumerate(resultado['data'][:10], 1):
                print(f"  {i}. [{concepto['index']}] {concepto['descripcion_concepto']}")

            # Verificar si existe el index 135
            indices = [c['index'] for c in resultado['data']]
            if 135 in indices:
                print(f"\n[OK] El index 135 SI existe en la estructura_contable 18")
                concepto_135 = next(c for c in resultado['data'] if c['index'] == 135)
                print(f"   Descripcion: {concepto_135['descripcion_concepto']}")
            else:
                print(f"\n[ERROR] El index 135 NO existe en la estructura_contable 18")
                print(f"   Indices disponibles: {sorted(indices)[:20]}...")
        else:
            print(f"[ERROR] Error: {resultado['message']}")

    except Exception as e:
        print(f"[ERROR] Excepcion: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Ejecutar test principal
    test_obtener_concepto_por_index()

    # Ejecutar test adicional
    test_listar_conceptos_estructura_18()
