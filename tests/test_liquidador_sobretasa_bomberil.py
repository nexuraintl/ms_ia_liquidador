"""
TEST LIQUIDADOR SOBRETASA BOMBERIL
===================================

Tests unitarios para el liquidador de Sobretasa Bomberil.
Simula diferentes respuestas de ICA y de la base de datos.

CASOS DE PRUEBA:
1. ICA con valor > 0 y ubicación con tarifa (exitoso)
2. ICA con valor > 0 pero ubicación sin tarifa (no aplica)
3. ICA con valor = 0 (preliquidación sin finalizar)
4. Múltiples ubicaciones con diferentes tarifas
5. Error de conexión a base de datos
6. ICA no procesado/sin actividades
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import sys
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


class TestLiquidadorSobretasaBomberil(unittest.TestCase):
    """Tests para el liquidador de Sobretasa Bomberil"""

    def setUp(self):
        """Configuración inicial para cada test"""
        # Mock del database_manager
        self.mock_db_manager = Mock()
        self.mock_db_manager.db_connection = Mock()
        self.mock_db_manager.db_connection.supabase = Mock()

        # Crear instancia del liquidador con mock
        self.liquidador = LiquidadorSobretasaBomberil(self.mock_db_manager)

    # ========================================
    # FIXTURES: RESPUESTAS DE ICA SIMULADAS
    # ========================================

    def get_resultado_ica_exitoso_una_ubicacion(self):
        """Resultado ICA exitoso con una sola ubicación (formato v3.0)"""
        return {
            "aplica": True,
            "estado": "preliquidado",
            "valor_total_ica": 2000000.0,
            "actividades_relacionadas": [
                {
                    "codigo_ubicacion": 11001,
                    "nombre_ubicacion": "BOGOTÁ D.C.",
                    "valor_ica": 2000000.0
                }
            ],
            "observaciones": [],
            "fecha_liquidacion": "2025-10-14T10:00:00.000000"
        }

    def get_resultado_ica_exitoso_multiples_ubicaciones(self):
        """Resultado ICA exitoso con múltiples ubicaciones (formato v3.0)"""
        return {
            "aplica": True,
            "estado": "preliquidado",
            "valor_total_ica": 3250000.0,
            "actividades_relacionadas": [
                {
                    "codigo_ubicacion": 11001,
                    "nombre_ubicacion": "BOGOTÁ D.C.",
                    "valor_ica": 2000000.0
                },
                {
                    "codigo_ubicacion": 5001,
                    "nombre_ubicacion": "MEDELLÍN",
                    "valor_ica": 1250000.0
                }
            ],
            "observaciones": [],
            "fecha_liquidacion": "2025-10-14T10:00:00.000000"
        }

    def get_resultado_ica_sin_valor(self):
        """Resultado ICA cuando no aplica (valor = 0)"""
        return {
            "aplica": False,
            "estado": "no_aplica_impuesto",
            "valor_total_ica": 0.0,
            "actividades_relacionadas": [],
            "observaciones": [],
            "fecha_liquidacion": "2025-10-14T10:00:00.000000"
        }

    def get_resultado_ica_preliquidacion_sin_finalizar(self):
        """Resultado ICA cuando la preliquidación no finalizó"""
        return {
            "aplica": True,
            "estado": "preliquidacion_sin_finalizar",
            "valor_total_ica": 0.0,
            "actividades_relacionadas": [],
            "observaciones": [],
            "fecha_liquidacion": "2025-10-14T10:00:00.000000"
        }

    def get_resultado_ica_sin_actividades(self):
        """Resultado ICA sin actividades relacionadas"""
        return {
            "aplica": True,
            "estado": "preliquidado",
            "valor_total_ica": 0.0,
            "actividades_relacionadas": [],
            "observaciones": [],
            "fecha_liquidacion": "2025-10-14T10:00:00.000000"
        }

    # ========================================
    # TESTS: CASOS EXITOSOS
    # ========================================

    def test_liquidar_sobretasa_una_ubicacion_con_tarifa(self):
        """
        TEST 1: ICA con valor > 0 y ubicación con tarifa
        Resultado esperado: Preliquidado exitoso
        """
        print("\n" + "="*80)
        print("TEST 1: Una ubicación con tarifa")
        print("="*80)

        # Configurar respuesta de ICA
        resultado_ica = self.get_resultado_ica_exitoso_una_ubicacion()

        # Mock de la respuesta de la BD usando DatabaseManager
        self.mock_db_manager.obtener_tarifa_bomberil.return_value = {
            "success": True,
            "data": {"tarifa": 0.05, "nombre_ubicacion": "BOGOTÁ D.C."},
            "message": "OK"
        }

        # Ejecutar liquidación
        resultado = self.liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Validaciones
        print(f"\n[OK] Estado: {resultado['estado']}")
        print(f"[OK] Aplica: {resultado['aplica']}")
        print(f"[OK] Valor total: ${resultado['valor_total_sobretasa']:,.2f}")
        print(f"[OK] Ubicaciones procesadas: {len(resultado['ubicaciones'])}")

        self.assertTrue(resultado["aplica"])
        self.assertEqual(resultado["estado"], "preliquidado")
        self.assertEqual(len(resultado["ubicaciones"]), 1)

        # Validar cálculo: 2,000,000 * 0.05 = 100,000
        self.assertEqual(resultado["valor_total_sobretasa"], 100000.0)

        # Validar estructura de ubicación
        ubicacion = resultado["ubicaciones"][0]
        self.assertEqual(ubicacion["codigo_ubicacion"], 11001)
        self.assertEqual(ubicacion["nombre_ubicacion"], "BOGOTÁ D.C.")
        self.assertEqual(ubicacion["tarifa"], 0.05)
        self.assertEqual(ubicacion["base_gravable_ica"], 2000000.0)
        self.assertEqual(ubicacion["valor"], 100000.0)

        print("\n[OK] TEST 1 PASADO")

    def test_liquidar_sobretasa_multiples_ubicaciones(self):
        """
        TEST 2: ICA con múltiples ubicaciones, algunas con tarifa
        Resultado esperado: Preliquidado solo para ubicaciones con tarifa
        """
        print("\n" + "="*80)
        print("TEST 2: Múltiples ubicaciones - algunas con tarifa")
        print("="*80)

        # Configurar respuesta de ICA
        resultado_ica = self.get_resultado_ica_exitoso_multiples_ubicaciones()

        # Mock de respuestas de BD - simular dos llamadas
        # Primera llamada: BOGOTÁ (código 11001) - SÍ tiene tarifa
        # Segunda llamada: MEDELLÍN (código 5001) - NO tiene tarifa
        self.mock_db_manager.obtener_tarifa_bomberil.side_effect = [
            {"success": True, "data": {"tarifa": 0.05, "nombre_ubicacion": "BOGOTÁ D.C."}, "message": "OK"},
            {"success": True, "data": None, "message": "No aplica para esta ubicación"}
        ]

        # Ejecutar liquidación
        resultado = self.liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Validaciones
        print(f"\n[OK] Estado: {resultado['estado']}")
        print(f"[OK] Aplica: {resultado['aplica']}")
        print(f"[OK] Valor total: ${resultado['valor_total_sobretasa']:,.2f}")
        print(f"[OK] Ubicaciones con tarifa: {len(resultado['ubicaciones'])} de 2")

        self.assertTrue(resultado["aplica"])
        self.assertEqual(resultado["estado"], "preliquidado")
        self.assertEqual(len(resultado["ubicaciones"]), 1)  # Solo Bogotá

        # Validar cálculo: 2,000,000 * 0.05 = 100,000 (solo Bogotá)
        self.assertEqual(resultado["valor_total_sobretasa"], 100000.0)

        # Validar que solo está Bogotá
        ubicacion = resultado["ubicaciones"][0]
        self.assertEqual(ubicacion["codigo_ubicacion"], 11001)
        self.assertEqual(ubicacion["nombre_ubicacion"], "BOGOTÁ D.C.")

        print("\n[OK] TEST 2 PASADO")

    def test_liquidar_sobretasa_todas_ubicaciones_con_tarifa(self):
        """
        TEST 3: Múltiples ubicaciones y todas tienen tarifa
        Resultado esperado: Suma de todas las sobretasas
        """
        print("\n" + "="*80)
        print("TEST 3: Todas las ubicaciones con tarifa")
        print("="*80)

        # Configurar respuesta de ICA
        resultado_ica = self.get_resultado_ica_exitoso_multiples_ubicaciones()

        # Mock de respuestas - ambas ubicaciones tienen tarifa
        self.mock_db_manager.obtener_tarifa_bomberil.side_effect = [
            {"success": True, "data": {"tarifa": 0.05, "nombre_ubicacion": "BOGOTÁ D.C."}, "message": "OK"},
            {"success": True, "data": {"tarifa": 0.04, "nombre_ubicacion": "MEDELLÍN"}, "message": "OK"}
        ]

        # Ejecutar liquidación
        resultado = self.liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Validaciones
        print(f"\n[OK] Estado: {resultado['estado']}")
        print(f"[OK] Ubicaciones con tarifa: {len(resultado['ubicaciones'])}")

        self.assertEqual(len(resultado["ubicaciones"]), 2)

        # Validar cálculos:
        # Bogotá: 2,000,000 * 0.05 = 100,000
        # Medellín: 1,250,000 * 0.04 = 50,000
        # Total: 150,000
        self.assertEqual(resultado["valor_total_sobretasa"], 150000.0)

        print(f"[OK] Valor Bogotá: ${resultado['ubicaciones'][0]['valor']:,.2f}")
        print(f"[OK] Valor Medellín: ${resultado['ubicaciones'][1]['valor']:,.2f}")
        print(f"[OK] Valor total: ${resultado['valor_total_sobretasa']:,.2f}")

        print("\n[OK] TEST 3 PASADO")

    # ========================================
    # TESTS: CASOS DE NO APLICACIÓN
    # ========================================

    def test_liquidar_sobretasa_ica_sin_valor(self):
        """
        TEST 4: ICA con valor = 0 (no aplica)
        Resultado esperado: Preliquidacion sin finalizar
        """
        print("\n" + "="*80)
        print("TEST 4: ICA sin valor (no aplica)")
        print("="*80)

        # Configurar respuesta de ICA
        resultado_ica = self.get_resultado_ica_sin_valor()

        # Ejecutar liquidación (no debe llamar a la BD)
        resultado = self.liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Validaciones
        print(f"\n[OK] Estado: {resultado['estado']}")
        print(f"[OK] Aplica: {resultado['aplica']}")
        print(f"[OK] Observaciones: {resultado['observaciones']}")

        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "no_aplica_impuesto")
        self.assertEqual(resultado["valor_total_sobretasa"], 0.0)
        self.assertIn("ICA no aplica", resultado["observaciones"])

        # Verificar que NO se llamó a la BD
        self.mock_db_manager.obtener_tarifa_bomberil.assert_not_called()

        print("\n[OK] TEST 4 PASADO")

    def test_liquidar_sobretasa_ubicacion_sin_tarifa(self):
        """
        TEST 5: ICA válido pero ubicación sin tarifa en BD
        Resultado esperado: No aplica impuesto
        """
        print("\n" + "="*80)
        print("TEST 5: Ubicación sin tarifa en BD")
        print("="*80)

        # Configurar respuesta de ICA
        resultado_ica = self.get_resultado_ica_exitoso_una_ubicacion()

        # Mock de respuesta BD sin tarifa para esta ubicación
        self.mock_db_manager.obtener_tarifa_bomberil.return_value = {
            "success": True,
            "data": None,
            "message": "No aplica para esta ubicación"
        }

        # Ejecutar liquidación
        resultado = self.liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Validaciones
        print(f"\n[OK] Estado: {resultado['estado']}")
        print(f"[OK] Aplica: {resultado['aplica']}")
        print(f"[OK] Observaciones: {resultado['observaciones']}")

        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "no_aplica_impuesto")
        self.assertEqual(len(resultado["ubicaciones"]), 0)
        self.assertIn("aplica Sobretasa Bomberil", resultado["observaciones"])

        print("\n[OK] TEST 5 PASADO")

    def test_liquidar_sobretasa_sin_actividades(self):
        """
        TEST 6: ICA sin actividades facturadas
        Resultado esperado: Preliquidacion sin finalizar
        """
        print("\n" + "="*80)
        print("TEST 6: ICA sin actividades facturadas")
        print("="*80)

        # Configurar respuesta de ICA
        resultado_ica = self.get_resultado_ica_sin_actividades()

        # Ejecutar liquidación
        resultado = self.liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Validaciones
        print(f"\n[OK] Estado: {resultado['estado']}")
        print(f"[OK] Observaciones: {resultado['observaciones']}")

        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "preliquidacion_sin_finalizar")
        self.assertIn("No aplica ICA", resultado["observaciones"])

        print("\n[OK] TEST 6 PASADO")

    # ========================================
    # TESTS: CASOS DE ERROR
    # ========================================

    def test_liquidar_sobretasa_error_bd(self):
        """
        TEST 7: Error al consultar base de datos
        Resultado esperado: Preliquidacion sin finalizar con error
        """
        print("\n" + "="*80)
        print("TEST 7: Error en consulta a base de datos")
        print("="*80)

        # Configurar respuesta de ICA
        resultado_ica = self.get_resultado_ica_exitoso_una_ubicacion()

        # Mock para simular error de BD
        self.mock_db_manager.obtener_tarifa_bomberil.side_effect = Exception("Connection timeout")

        # Ejecutar liquidación
        resultado = self.liquidador.liquidar_sobretasa_bomberil(resultado_ica)

        # Validaciones
        print(f"\n[OK] Estado: {resultado['estado']}")
        print(f"[OK] Observaciones: {resultado['observaciones']}")

        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "preliquidacion_sin_finalizar")
        self.assertIn("Error al consultar la base de datos", resultado["observaciones"])

        print("\n[OK] TEST 7 PASADO")

    def test_liquidar_sobretasa_excepcion_general(self):
        """
        TEST 8: Excepción general durante liquidación
        Resultado esperado: Manejo graceful del error
        """
        print("\n" + "="*80)
        print("TEST 8: Excepción general durante liquidación")
        print("="*80)

        # Resultado ICA malformado (sin estructura esperada)
        resultado_ica_malo = {
            "aplica": True,
            "valor_total_ica": 1000000.0,
            # Falta "actividades_facturadas"
        }

        # Ejecutar liquidación
        resultado = self.liquidador.liquidar_sobretasa_bomberil(resultado_ica_malo)

        # Validaciones
        print(f"\n[OK] Estado: {resultado['estado']}")
        print(f"[OK] Observaciones: {resultado['observaciones']}")

        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "preliquidacion_sin_finalizar")
        self.assertIn("No se pudieron identificar ubicaciones", resultado["observaciones"])

        print("\n[OK] TEST 8 PASADO")

    # ========================================
    # TESTS: MÉTODOS PRIVADOS
    # ========================================

    def test_extraer_ubicaciones_ica(self):
        """
        TEST 9: Extracción de ubicaciones del resultado ICA
        """
        print("\n" + "="*80)
        print("TEST 9: Extracción de ubicaciones")
        print("="*80)

        # Configurar respuesta de ICA con 2 ubicaciones
        resultado_ica = self.get_resultado_ica_exitoso_multiples_ubicaciones()

        # Llamar método privado
        ubicaciones = self.liquidador._extraer_ubicaciones_ica(resultado_ica)

        # Validaciones
        print(f"\n[OK] Ubicaciones extraídas: {len(ubicaciones)}")

        self.assertEqual(len(ubicaciones), 2)

        # Validar primera ubicación
        self.assertEqual(ubicaciones[0]["codigo_ubicacion"], 11001)
        self.assertEqual(ubicaciones[0]["nombre_ubicacion"], "BOGOTÁ D.C.")
        self.assertEqual(ubicaciones[0]["valor_ica"], 2000000.0)

        # Validar segunda ubicación
        self.assertEqual(ubicaciones[1]["codigo_ubicacion"], 5001)
        self.assertEqual(ubicaciones[1]["nombre_ubicacion"], "MEDELLÍN")
        self.assertEqual(ubicaciones[1]["valor_ica"], 1250000.0)

        for ub in ubicaciones:
            print(f"  - {ub['nombre_ubicacion']}: ${ub['valor_ica']:,.2f}")

        print("\n[OK] TEST 9 PASADO")

    def test_obtener_tarifa_bd_existosa(self):
        """
        TEST 10: Obtención de tarifa de BD exitosa
        """
        print("\n" + "="*80)
        print("TEST 10: Obtención de tarifa BD exitosa")
        print("="*80)

        # Mock de respuesta exitosa usando DatabaseManager
        self.mock_db_manager.obtener_tarifa_bomberil.return_value = {
            "success": True,
            "data": {"tarifa": 0.05, "nombre_ubicacion": "BOGOTÁ D.C."},
            "message": "OK"
        }

        # Llamar método privado
        resultado = self.liquidador._obtener_tarifa_bd(11001)

        # Validaciones
        print(f"\n[OK] Tarifa: {resultado['tarifa']}")
        print(f"[OK] Nombre: {resultado['nombre_ubicacion']}")
        print(f"[OK] Error: {resultado['error']}")

        self.assertEqual(resultado["tarifa"], 0.05)
        self.assertEqual(resultado["nombre_ubicacion"], "BOGOTÁ D.C.")
        self.assertFalse(resultado["error"])

        print("\n[OK] TEST 10 PASADO")

    def test_obtener_tarifa_bd_sin_registros(self):
        """
        TEST 11: Obtención de tarifa BD sin registros
        """
        print("\n" + "="*80)
        print("TEST 11: Obtención de tarifa BD sin registros")
        print("="*80)

        # Mock de respuesta sin datos para esta ubicación
        self.mock_db_manager.obtener_tarifa_bomberil.return_value = {
            "success": True,
            "data": None,
            "message": "No aplica para esta ubicación"
        }

        # Llamar método privado
        resultado = self.liquidador._obtener_tarifa_bd(99999)

        # Validaciones
        print(f"\n[OK] Tarifa: {resultado['tarifa']}")
        print(f"[OK] Error: {resultado['error']}")

        self.assertIsNone(resultado["tarifa"])
        self.assertFalse(resultado["error"])

        print("\n[OK] TEST 11 PASADO")


def run_tests():
    """Ejecuta todos los tests"""
    print("\n" + "="*80)
    print("INICIANDO TESTS - LIQUIDADOR SOBRETASA BOMBERIL")
    print("="*80)

    # Crear suite de tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestLiquidadorSobretasaBomberil)

    # Ejecutar tests con verbosidad
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Resumen final
    print("\n" + "="*80)
    print("RESUMEN DE TESTS")
    print("="*80)
    print(f"[OK] Tests ejecutados: {result.testsRun}")
    print(f"[OK] Tests exitosos: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"[ERROR] Tests fallidos: {len(result.failures)}")
    print(f"[ERROR] Errores: {len(result.errors)}")
    print("="*80)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
