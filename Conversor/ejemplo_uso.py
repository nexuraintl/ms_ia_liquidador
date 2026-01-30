"""
Ejemplo de uso del modulo Conversor TRM
Ejecutar desde la raiz: python -m Conversor.ejemplo_uso
O desde esta carpeta: python ejemplo_uso.py
"""

import sys
import os

# Agregar el directorio padre al path para imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from Conversor.conversor_trm import ConversorTRM
    from Conversor.exceptions import TRMServiceError, TRMValidationError
except ImportError:
    from conversor_trm import ConversorTRM
    from exceptions import TRMServiceError, TRMValidationError


def ejemplo_basico():
    """Ejemplo basico de obtencion de TRM"""
    print("=" * 60)
    print("EJEMPLO 1: Obtener TRM actual")
    print("=" * 60)

    with ConversorTRM(timeout=30) as conversor:
        try:
            resultado = conversor.obtener_trm()
            print(f"TRM actual: {resultado['value']} COP/USD")
            print(f"Vigencia desde: {resultado['validityFrom']}")
            print(f"Vigencia hasta: {resultado['validityTo']}")
            print(f"Unidad: {resultado['unit']}")
        except TRMServiceError as e:
            print(f"Error: {e}")


def ejemplo_trm_historica():
    """Ejemplo de obtencion de TRM historica"""
    print("\n" + "=" * 60)
    print("EJEMPLO 2: Obtener TRM historica")
    print("=" * 60)

    with ConversorTRM() as conversor:
        try:
            fecha = "2020-03-06"
            resultado = conversor.obtener_trm(fecha)
            print(f"TRM del {fecha}: {resultado['value']} COP/USD")
        except TRMValidationError as e:
            print(f"Error de validacion: {e}")
        except TRMServiceError as e:
            print(f"Error del servicio: {e}")


def ejemplo_conversion_usd_cop():
    """Ejemplo de conversion USD a COP"""
    print("\n" + "=" * 60)
    print("EJEMPLO 3: Convertir USD a COP")
    print("=" * 60)

    with ConversorTRM() as conversor:
        try:
            montos_usd = [100, 500, 1000, 5000]

            for monto_usd in montos_usd:
                monto_cop = conversor.convertir_usd_a_cop(monto_usd)
                print(f"{monto_usd:>6} USD = {monto_cop:>12,.2f} COP")

        except Exception as e:
            print(f"Error: {e}")


def ejemplo_conversion_cop_usd():
    """Ejemplo de conversion COP a USD"""
    print("\n" + "=" * 60)
    print("EJEMPLO 4: Convertir COP a USD")
    print("=" * 60)

    with ConversorTRM() as conversor:
        try:
            montos_cop = [100000, 500000, 1000000, 5000000]

            for monto_cop in montos_cop:
                monto_usd = conversor.convertir_cop_a_usd(monto_cop)
                print(f"{monto_cop:>12,} COP = {monto_usd:>8,.2f} USD")

        except Exception as e:
            print(f"Error: {e}")


def ejemplo_conversion_fecha_especifica():
    """Ejemplo de conversion con fecha especifica"""
    print("\n" + "=" * 60)
    print("EJEMPLO 5: Conversion con fecha especifica")
    print("=" * 60)

    with ConversorTRM() as conversor:
        try:
            fecha = "2020-03-06"
            monto_usd = 1000

            monto_cop = conversor.convertir_usd_a_cop(monto_usd, fecha)
            print(f"{monto_usd} USD = {monto_cop:,.2f} COP (TRM del {fecha})")

        except Exception as e:
            print(f"Error: {e}")


def ejemplo_manejo_errores():
    """Ejemplo de manejo de errores"""
    print("\n" + "=" * 60)
    print("EJEMPLO 6: Manejo de errores")
    print("=" * 60)

    with ConversorTRM() as conversor:
        # Error de formato de fecha
        print("\nPrueba 1: Formato de fecha invalido")
        try:
            conversor.obtener_trm("06-03-2020")  # Formato incorrecto
        except TRMValidationError as e:
            print(f"  Capturado TRMValidationError: {e}")

        # Error de monto negativo
        print("\nPrueba 2: Monto negativo")
        try:
            conversor.convertir_usd_a_cop(-100)
        except TRMValidationError as e:
            print(f"  Capturado TRMValidationError: {e}")


def ejemplo_comparacion_fechas():
    """Ejemplo comparando TRM de diferentes fechas"""
    print("\n" + "=" * 60)
    print("EJEMPLO 7: Comparacion de TRM en diferentes fechas")
    print("=" * 60)

    with ConversorTRM() as conversor:
        try:
            fechas = ["2020-01-15", "2020-06-15", "2020-12-15"]
            monto_usd = 1000

            print(f"\nConversion de {monto_usd} USD en diferentes fechas:\n")
            print(f"{'Fecha':<15} {'TRM':>10} {'Conversion (COP)':>20}")
            print("-" * 50)

            for fecha in fechas:
                trm_valor = conversor.obtener_trm_valor(fecha)
                monto_cop = monto_usd * trm_valor
                print(f"{fecha:<15} {trm_valor:>10.2f} {monto_cop:>20,.2f}")

        except Exception as e:
            print(f"Error: {e}")


def main():
    """Ejecuta todos los ejemplos"""
    print("\n")
    print("*" * 60)
    print("*" + " " * 58 + "*")
    print("*" + "  EJEMPLOS DE USO DEL MODULO CONVERSOR TRM".center(58) + "*")
    print("*" + " " * 58 + "*")
    print("*" * 60)
    print("\n")

    try:
        ejemplo_basico()
        ejemplo_trm_historica()
        ejemplo_conversion_usd_cop()
        ejemplo_conversion_cop_usd()
        ejemplo_conversion_fecha_especifica()
        ejemplo_manejo_errores()
        ejemplo_comparacion_fechas()

        print("\n" + "=" * 60)
        print("Todos los ejemplos ejecutados exitosamente!")
        print("=" * 60 + "\n")

    except KeyboardInterrupt:
        print("\n\nEjecucion interrumpida por el usuario.")
    except Exception as e:
        print(f"\n\nError inesperado: {e}")


if __name__ == "__main__":
    main()
