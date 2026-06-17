"""
Tests para el modulo validar_bomberil.py

Tests implementados:
- Validacion de sobretasa bomberil con ICA exitoso
- Validacion cuando no hay resultado de ICA
- Validacion del metodo _debe_procesar_sobretasa
- Validacion del metodo _ejecutar_liquidacion
- Manejo de errores en liquidacion
- Lazy initialization del liquidador
- Logging de resultados

Autor: Sistema Preliquidador
Version: 1.0
"""

import pytest
import logging
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from typing import Dict, Any

from app.validar_bomberil import ValidadorSobretasa, validar_sobretasa_bomberil


class TestValidadorSobretasa:
    """Tests para la clase ValidadorSobretasa"""

    @pytest.fixture
    def mock_db_manager(self):
        """Fixture para mock de database manager"""
        return Mock()

    @pytest.fixture
    def mock_liquidador(self):
        """Fixture para mock de liquidador sobretasa"""
        mock = Mock()
        mock.liquidar_sobretasa_bomberil = Mock(return_value={
            "aplica": True,
            "estado": "liquidado",
            "valor_total_sobretasa": 50000.0,
            "ubicaciones": [
                {
                    "municipio": "Bogotá",
                    "tarifa_bomberil": 0.05,
                    "valor_ica_municipio": 1000000.0,
                    "valor_sobretasa": 50000.0
                }
            ]
        })
        return mock

    @pytest.fixture
    def validador(self, mock_db_manager):
        """Fixture para crear instancia de ValidadorSobretasa"""
        return ValidadorSobretasa(db_manager=mock_db_manager)

    @pytest.fixture
    def resultado_final_con_ica(self):
        """Fixture para resultado final con ICA liquidado"""
        return {
            "impuestos": {
                "ica": {
                    "aplica": True,
                    "estado": "liquidado",
                    "valor_total_ica": 1000000.0,
                    "ubicaciones": [
                        {
                            "municipio": "Bogotá",
                            "tarifa_ica": 0.01,
                            "base_gravable": 100000000.0,
                            "valor_ica": 1000000.0
                        }
                    ]
                }
            }
        }

    @pytest.fixture
    def resultado_final_sin_ica(self):
        """Fixture para resultado final sin ICA"""
        return {
            "impuestos": {
                "retefuente": {
                    "aplica": True,
                    "valor_retencion": 50000.0
                }
            }
        }

    # =========================================================================
    # TESTS DEL METODO validar()
    # =========================================================================

    @pytest.mark.asyncio
    async def test_validar_con_ica_exitoso(
        self,
        validador,
        mock_liquidador,
        resultado_final_con_ica
    ):
        """Test: Validacion exitosa cuando existe resultado de ICA"""
        # Inyectar liquidador mock
        validador.liquidador_sobretasa = mock_liquidador

        # Ejecutar validacion
        resultado = await validador.validar(resultado_final_con_ica)

        # Verificar que se llamo al liquidador
        mock_liquidador.liquidar_sobretasa_bomberil.assert_called_once()

        # Verificar estructura de resultado
        assert resultado is not None
        assert resultado["aplica"] is True
        assert resultado["estado"] == "liquidado"
        assert resultado["valor_total_sobretasa"] == 50000.0
        assert "ubicaciones" in resultado
        assert len(resultado["ubicaciones"]) == 1

    @pytest.mark.asyncio
    async def test_validar_sin_ica_retorna_none(
        self,
        validador,
        resultado_final_sin_ica
    ):
        """Test: Retorna None cuando no existe resultado de ICA"""
        resultado = await validador.validar(resultado_final_sin_ica)

        assert resultado is None

    @pytest.mark.asyncio
    async def test_validar_con_resultado_final_vacio_retorna_none(
        self,
        validador
    ):
        """Test: Retorna None cuando resultado_final esta vacio"""
        resultado_vacio = {}
        resultado = await validador.validar(resultado_vacio)

        assert resultado is None

    @pytest.mark.asyncio
    async def test_validar_maneja_error_en_liquidacion(
        self,
        validador,
        mock_liquidador,
        resultado_final_con_ica
    ):
        """Test: Maneja errores durante la liquidacion"""
        # Configurar mock para lanzar excepcion
        mock_liquidador.liquidar_sobretasa_bomberil.side_effect = Exception(
            "Error de prueba en liquidacion"
        )
        validador.liquidador_sobretasa = mock_liquidador

        # Ejecutar validacion
        resultado = await validador.validar(resultado_final_con_ica)

        # Verificar estructura de error
        assert resultado is not None
        assert resultado["aplica"] is False
        assert resultado["estado"] == "preliquidacion_sin_finalizar"
        assert "error" in resultado
        assert "Error de prueba en liquidacion" in resultado["error"]
        assert resultado["valor_total_sobretasa"] == 0.0
        assert resultado["ubicaciones"] == []
        assert len(resultado["observaciones"]) > 0

    # =========================================================================
    # TESTS DEL METODO _debe_procesar_sobretasa()
    # =========================================================================

    def test_debe_procesar_sobretasa_con_ica_presente(
        self,
        validador,
        resultado_final_con_ica
    ):
        """Test: Debe procesar cuando ICA esta presente"""
        resultado = validador._debe_procesar_sobretasa(resultado_final_con_ica)
        assert resultado is True

    def test_debe_procesar_sobretasa_sin_ica(
        self,
        validador,
        resultado_final_sin_ica
    ):
        """Test: No debe procesar cuando ICA no esta presente"""
        resultado = validador._debe_procesar_sobretasa(resultado_final_sin_ica)
        assert resultado is False

    def test_debe_procesar_sobretasa_sin_impuestos(
        self,
        validador
    ):
        """Test: No debe procesar cuando no existe clave 'impuestos'"""
        resultado_sin_impuestos = {"otros_datos": "valor"}
        resultado = validador._debe_procesar_sobretasa(resultado_sin_impuestos)
        assert resultado is False

    # =========================================================================
    # TESTS DEL METODO _ejecutar_liquidacion()
    # =========================================================================

    def test_ejecutar_liquidacion_con_liquidador_inyectado(
        self,
        validador,
        mock_liquidador
    ):
        """Test: Usa liquidador inyectado si esta disponible"""
        validador.liquidador_sobretasa = mock_liquidador

        resultado_ica = {
            "aplica": True,
            "valor_total_ica": 1000000.0
        }

        resultado = validador._ejecutar_liquidacion(resultado_ica)

        # Verificar que se uso el liquidador inyectado
        mock_liquidador.liquidar_sobretasa_bomberil.assert_called_once_with(resultado_ica)
        assert resultado["aplica"] is True

    @patch('app.validar_bomberil.LiquidadorSobretasaBomberil')
    def test_ejecutar_liquidacion_lazy_initialization(
        self,
        mock_liquidador_class,
        validador
    ):
        """Test: Crea liquidador si no fue inyectado (lazy initialization)"""
        # Configurar mock de la clase
        mock_instance = Mock()
        mock_instance.liquidar_sobretasa_bomberil = Mock(return_value={
            "aplica": True,
            "valor_total_sobretasa": 50000.0
        })
        mock_liquidador_class.return_value = mock_instance

        # Asegurar que liquidador es None
        validador.liquidador_sobretasa = None

        resultado_ica = {"aplica": True, "valor_total_ica": 1000000.0}

        # Ejecutar
        resultado = validador._ejecutar_liquidacion(resultado_ica)

        # Verificar que se creo el liquidador
        mock_liquidador_class.assert_called_once_with(
            database_manager=validador.db_manager
        )

        # Verificar que se uso el nuevo liquidador
        mock_instance.liquidar_sobretasa_bomberil.assert_called_once_with(resultado_ica)

    # =========================================================================
    # TESTS DEL METODO _log_resultado()
    # =========================================================================

    def test_log_resultado_exitoso(
        self,
        validador,
        caplog
    ):
        """Test: Logging correcto de resultado exitoso"""
        resultado_sobretasa = {
            "estado": "liquidado",
            "valor_total_sobretasa": 75000.50
        }

        with caplog.at_level(logging.INFO):
            validador._log_resultado(resultado_sobretasa)

        # Verificar logs generados
        assert "Sobretasa Bomberil - Estado: liquidado" in caplog.text
        assert "Sobretasa Bomberil - Valor total: $75,000.50" in caplog.text

    def test_log_resultado_sin_aplicar(
        self,
        validador,
        caplog
    ):
        """Test: Logging correcto cuando no aplica"""
        resultado_sobretasa = {
            "estado": "no_aplica_impuesto",
            "valor_total_sobretasa": 0.0
        }

        with caplog.at_level(logging.INFO):
            validador._log_resultado(resultado_sobretasa)

        assert "Estado: no_aplica_impuesto" in caplog.text
        assert "$0.00" in caplog.text

    def test_log_resultado_con_valores_faltantes(
        self,
        validador,
        caplog
    ):
        """Test: Logging usa valores por defecto si faltan datos"""
        resultado_incompleto = {}

        with caplog.at_level(logging.INFO):
            validador._log_resultado(resultado_incompleto)

        # Debe usar valores por defecto
        assert "Estado: Desconocido" in caplog.text
        assert "$0.00" in caplog.text

    # =========================================================================
    # TESTS DEL METODO _manejar_error()
    # =========================================================================

    def test_manejar_error_genera_estructura_correcta(
        self,
        validador,
        caplog
    ):
        """Test: Genera estructura de error correcta"""
        excepcion = ValueError("Error de prueba en validacion")

        with caplog.at_level(logging.ERROR):
            resultado = validador._manejar_error(excepcion)

        # Verificar estructura
        assert resultado["aplica"] is False
        assert resultado["estado"] == "preliquidacion_sin_finalizar"
        assert "error" in resultado
        assert resultado["error"] == "Error de prueba en validacion"
        assert resultado["valor_total_sobretasa"] == 0.0
        assert resultado["ubicaciones"] == []
        assert isinstance(resultado["observaciones"], list)
        assert len(resultado["observaciones"]) > 0

        # Verificar logging
        assert "Error liquidando Sobretasa Bomberil" in caplog.text

    # =========================================================================
    # TESTS DE LA FUNCION WRAPPER validar_sobretasa_bomberil()
    # =========================================================================

    @pytest.mark.asyncio
    async def test_validar_sobretasa_bomberil_wrapper_exitoso(
        self,
        mock_db_manager,
        resultado_final_con_ica
    ):
        """Test: Wrapper function crea validador y delega correctamente"""
        with patch('app.validar_bomberil.ValidadorSobretasa') as mock_validador_class:
            # Configurar mock con AsyncMock para el metodo async
            mock_instance = Mock()
            mock_instance.validar = AsyncMock(return_value={
                "aplica": True,
                "valor_total_sobretasa": 50000.0
            })
            mock_validador_class.return_value = mock_instance

            # Ejecutar wrapper
            resultado = await validar_sobretasa_bomberil(
                resultado_final=resultado_final_con_ica,
                db_manager=mock_db_manager
            )

            # Verificar que se creo el validador con db_manager
            mock_validador_class.assert_called_once_with(db_manager=mock_db_manager)

            # Verificar resultado
            assert resultado is not None
            assert resultado["aplica"] is True

    @pytest.mark.asyncio
    async def test_validar_sobretasa_bomberil_wrapper_retorna_none(
        self,
        mock_db_manager,
        resultado_final_sin_ica
    ):
        """Test: Wrapper retorna None cuando no aplica"""
        resultado = await validar_sobretasa_bomberil(
            resultado_final=resultado_final_sin_ica,
            db_manager=mock_db_manager
        )

        assert resultado is None

    # =========================================================================
    # TESTS DE INTEGRACION
    # =========================================================================

    @pytest.mark.asyncio
    async def test_flujo_completo_con_multiples_ubicaciones(
        self,
        validador,
        mock_liquidador
    ):
        """Test: Flujo completo con ICA de multiples municipios"""
        # Configurar mock con multiples ubicaciones
        mock_liquidador.liquidar_sobretasa_bomberil = Mock(return_value={
            "aplica": True,
            "estado": "liquidado",
            "valor_total_sobretasa": 150000.0,
            "ubicaciones": [
                {
                    "municipio": "Bogotá",
                    "tarifa_bomberil": 0.05,
                    "valor_ica_municipio": 1000000.0,
                    "valor_sobretasa": 50000.0
                },
                {
                    "municipio": "Medellín",
                    "tarifa_bomberil": 0.05,
                    "valor_ica_municipio": 2000000.0,
                    "valor_sobretasa": 100000.0
                }
            ]
        })
        validador.liquidador_sobretasa = mock_liquidador

        resultado_final = {
            "impuestos": {
                "ica": {
                    "aplica": True,
                    "valor_total_ica": 3000000.0,
                    "ubicaciones": [
                        {"municipio": "Bogotá", "valor_ica": 1000000.0},
                        {"municipio": "Medellín", "valor_ica": 2000000.0}
                    ]
                }
            }
        }

        resultado = await validador.validar(resultado_final)

        assert resultado["aplica"] is True
        assert resultado["valor_total_sobretasa"] == 150000.0
        assert len(resultado["ubicaciones"]) == 2
        assert resultado["ubicaciones"][0]["municipio"] == "Bogotá"
        assert resultado["ubicaciones"][1]["municipio"] == "Medellín"


# =========================================================================
# TESTS PARAMETRIZADOS
# =========================================================================

class TestValidadorSobretasaParametrizado:
    """Tests parametrizados para ValidadorSobretasa"""

    @pytest.mark.parametrize("resultado_final,esperado", [
        # Caso: Con ICA
        (
            {"impuestos": {"ica": {"aplica": True}}},
            True
        ),
        # Caso: Sin ICA
        (
            {"impuestos": {"retefuente": {"aplica": True}}},
            False
        ),
        # Caso: Sin impuestos
        (
            {"otros_datos": "valor"},
            False
        ),
        # Caso: Diccionario vacio
        (
            {},
            False
        ),
        # Caso: ICA en None
        (
            {"impuestos": {"ica": None}},
            True  # Porque "ica" in dict es True aunque sea None
        ),
    ])
    def test_debe_procesar_sobretasa_casos(
        self,
        resultado_final,
        esperado
    ):
        """Test parametrizado: Casos de _debe_procesar_sobretasa"""
        mock_db = Mock()
        validador = ValidadorSobretasa(db_manager=mock_db)

        resultado = validador._debe_procesar_sobretasa(resultado_final)

        assert resultado == esperado
