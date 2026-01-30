"""
Test de conexion manual al servicio TRM
Ejecutar desde la raiz del proyecto: python -m Conversor.test_conexion
O desde esta carpeta: python test_conexion.py

NOTA: Requiere conexion a internet
"""

import sys
import os

# Agregar el directorio padre al path para imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from Conversor.conversor_trm import ConversorTRM
    from Conversor.exceptions import TRMServiceError, TRMValidationError
except ImportError:
    # Si falla, intentar import relativo (cuando se ejecuta desde la carpeta Conversor)
    from conversor_trm import ConversorTRM
    from exceptions import TRMServiceError, TRMValidationError


def test_conexion_real():
    """Test de conexion con el servicio real"""
    print("\n" + "=" * 60)
    print("TEST DE CONEXION AL SERVICIO TRM")
    print("=" * 60 + "\n")

    print("Conectando al servicio de la Superfinanciera...")

    try:
        with ConversorTRM(timeout=30) as conversor:
            # Test 1: Obtener TRM actual
            print("\n1. Obteniendo TRM actual...")
            resultado = conversor.obtener_trm()

            print(f"   Estado: OK")
            print(f"   TRM: {resultado['value']} COP/USD")
            print(f"   Vigencia desde: {resultado['validityFrom']}")
            print(f"   Vigencia hasta: {resultado['validityTo']}")

            # Test 2: Conversion USD a COP
            print("\n2. Probando conversion USD a COP...")
            monto_usd = 100
            monto_cop = conversor.convertir_usd_a_cop(monto_usd)
            print(f"   {monto_usd} USD = {monto_cop:,.2f} COP")

            # Test 3: Conversion COP a USD
            print("\n3. Probando conversion COP a USD...")
            monto_cop_test = 3500000
            monto_usd_result = conversor.convertir_cop_a_usd(monto_cop_test)
            print(f"   {monto_cop_test:,} COP = {monto_usd_result:.2f} USD")

            # Test 4: TRM historica
            print("\n4. Obteniendo TRM historica (2020-03-06)...")
            resultado_hist = conversor.obtener_trm("2020-03-06")
            print(f"   TRM 2020-03-06: {resultado_hist['value']} COP/USD")

            print("\n" + "=" * 60)
            print("TODOS LOS TESTS EXITOSOS")
            print("=" * 60 + "\n")

            return True

    except TRMValidationError as e:
        print(f"\nError de validacion: {e}")
        return False

    except TRMServiceError as e:
        print(f"\nError del servicio TRM: {e}")
        print("\nPosibles causas:")
        print("- Sin conexion a internet")
        print("- Servicio temporalmente no disponible")
        print("- Problemas con certificado SSL")
        return False

    except Exception as e:
        print(f"\nError inesperado: {e}")
        return False


if __name__ == "__main__":
    import sys

    print("\n")
    print("*" * 60)
    print("*  TEST DE CONEXION - MODULO CONVERSOR TRM".ljust(59) + "*")
    print("*" * 60)

    exito = test_conexion_real()

    if exito:
        print("\nEl modulo Conversor TRM esta funcionando correctamente!")
        sys.exit(0)
    else:
        print("\nHubo problemas al conectar con el servicio.")
        print("Verifica tu conexion a internet y vuelve a intentar.")
        sys.exit(1)
