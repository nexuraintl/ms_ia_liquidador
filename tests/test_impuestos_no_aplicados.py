"""
Tests para el modulo impuestos_no_aplicados.py

Tests implementados:
- Validacion del constructor con inyeccion de logger
- Metodo principal agregar_impuestos_no_aplicados
- Metodo auxiliar _debe_agregar_impuesto (edge cases)
- Metodo auxiliar _construir_mensajes_error (edge cases)
- Metodo _agregar_estampilla_no_aplicada (edge cases)
- Metodo _agregar_obra_publica_no_aplicada (edge cases)
- Metodo _agregar_iva_no_aplicado (edge cases)
- Metodo _agregar_tasa_prodeporte_no_aplicada (edge cases)
- Metodo _agregar_timbre_no_aplicado (edge cases)
- Funcion wrapper agregar_impuestos_no_aplicados
- Verificacion de estructura JSON completa
- Verificacion de logging
- Modificacion in-place de resultado_final

Autor: Sistema Preliquidador
Version: 1.0
"""

import pytest
import logging
from unittest.mock import Mock, patch, call
from typing import Dict, Any

from app.impuestos_no_aplicados import ValidadorNoAplicacion, agregar_impuestos_no_aplicados


class TestValidadorNoAplicacion:
    """Tests para la clase ValidadorNoAplicacion"""

    @pytest.fixture
    def mock_logger(self):
        """Fixture para mock de logger"""
        return Mock(spec=logging.Logger)

    @pytest.fixture
    def validador(self, mock_logger):
        """Fixture para crear instancia de ValidadorNoAplicacion"""
        return ValidadorNoAplicacion(logger=mock_logger)

    @pytest.fixture
    def resultado_final_vacio(self):
        """Fixture para resultado_final vacio"""
        return {
            "impuestos": {}
        }

    @pytest.fixture
    def resultado_final_con_estampilla(self):
        """Fixture para resultado_final que ya tiene estampilla"""
        return {
            "impuestos": {
                "estampilla_universidad": {
                    "aplica": True,
                    "valor_estampilla": 100000.0
                }
            }
        }

    @pytest.fixture
    def deteccion_impuestos_completo(self):
        """Fixture para deteccion_impuestos con todos los campos"""
        return {
            "razon_no_aplica_estampilla": "Negocio sin recurso de estampilla",
            "razon_no_aplica_obra_publica": "Negocio sin recurso de obra publica",
            "estado_especial": "recurso_no_identificado",
            "validacion_recurso": {
                "observaciones": "No se identifico contrato de estampilla"
            }
        }

    @pytest.fixture
    def deteccion_impuestos_minimo(self):
        """Fixture para deteccion_impuestos sin campos opcionales"""
        return {}

    @pytest.fixture
    def deteccion_impuestos_sin_observaciones(self):
        """Fixture para deteccion_impuestos con validacion_recurso pero sin observaciones"""
        return {
            "razon_no_aplica_estampilla": "Negocio sin recurso",
            "validacion_recurso": {}
        }

    # =================================================================
    # TESTS DEL CONSTRUCTOR
    # =================================================================

    def test_constructor_con_logger(self, mock_logger):
        """Test: Constructor inicializa correctamente con logger"""
        validador = ValidadorNoAplicacion(logger=mock_logger)

        assert validador.logger == mock_logger

    # =================================================================
    # TESTS DE _debe_agregar_impuesto
    # =================================================================

    def test_debe_agregar_impuesto_cuando_no_aplica_y_no_existe(self, validador, resultado_final_vacio):
        """Test: Debe agregar cuando aplica=False y no existe en resultado_final"""
        resultado = validador._debe_agregar_impuesto(
            aplica=False,
            impuesto_key="estampilla_universidad",
            resultado_final=resultado_final_vacio
        )

        assert resultado is True

    def test_no_debe_agregar_impuesto_cuando_aplica_true(self, validador, resultado_final_vacio):
        """Test: No debe agregar cuando aplica=True"""
        resultado = validador._debe_agregar_impuesto(
            aplica=True,
            impuesto_key="estampilla_universidad",
            resultado_final=resultado_final_vacio
        )

        assert resultado is False

    def test_no_debe_agregar_impuesto_cuando_ya_existe(self, validador, resultado_final_con_estampilla):
        """Test: No debe agregar cuando ya existe en resultado_final"""
        resultado = validador._debe_agregar_impuesto(
            aplica=False,
            impuesto_key="estampilla_universidad",
            resultado_final=resultado_final_con_estampilla
        )

        assert resultado is False

    def test_debe_agregar_impuesto_cuando_aplica_false_y_existe_otro(self, validador):
        """Test: Debe agregar si aplica=False aunque existan otros impuestos"""
        resultado_final = {
            "impuestos": {
                "iva_reteiva": {"aplica": True}
            }
        }

        resultado = validador._debe_agregar_impuesto(
            aplica=False,
            impuesto_key="estampilla_universidad",
            resultado_final=resultado_final
        )

        assert resultado is True

    # =================================================================
    # TESTS DE _construir_mensajes_error
    # =================================================================

    def test_construir_mensajes_error_con_observaciones(self, validador, deteccion_impuestos_completo):
        """Test: Usa observaciones cuando validacion_recurso.observaciones existe"""
        mensajes = validador._construir_mensajes_error(
            deteccion_impuestos=deteccion_impuestos_completo,
            razon_default="Razon por defecto"
        )

        assert mensajes == ["No se identifico contrato de estampilla"]
        assert len(mensajes) == 1

    def test_construir_mensajes_error_sin_observaciones(self, validador, deteccion_impuestos_minimo):
        """Test: Usa razon_default cuando no hay observaciones"""
        mensajes = validador._construir_mensajes_error(
            deteccion_impuestos=deteccion_impuestos_minimo,
            razon_default="Razon por defecto"
        )

        assert mensajes == ["Razon por defecto"]
        assert len(mensajes) == 1

    def test_construir_mensajes_error_validacion_recurso_sin_observaciones(
        self, validador, deteccion_impuestos_sin_observaciones
    ):
        """Test: Usa razon_default cuando validacion_recurso existe pero observaciones es None"""
        mensajes = validador._construir_mensajes_error(
            deteccion_impuestos=deteccion_impuestos_sin_observaciones,
            razon_default="Razon por defecto"
        )

        assert mensajes == ["Razon por defecto"]

    def test_construir_mensajes_error_observaciones_vacia(self, validador):
        """Test: Usa razon_default cuando observaciones es string vacio"""
        deteccion = {
            "validacion_recurso": {
                "observaciones": ""
            }
        }

        mensajes = validador._construir_mensajes_error(
            deteccion_impuestos=deteccion,
            razon_default="Razon por defecto"
        )

        assert mensajes == ["Razon por defecto"]

    # =================================================================
    # TESTS DE _agregar_estampilla_no_aplicada
    # =================================================================

    def test_agregar_estampilla_estructura_completa(
        self, validador, mock_logger, resultado_final_vacio, deteccion_impuestos_completo
    ):
        """Test: Agrega estructura completa de estampilla con todos los campos"""
        validador._agregar_estampilla_no_aplicada(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_estampilla=False,
            nombre_negocio="Universidad Nacional"
        )

        estampilla = resultado_final_vacio["impuestos"]["estampilla_universidad"]

        assert estampilla["aplica"] is False
        assert estampilla["estado"] == "recurso_no_identificado"
        assert estampilla["valor_estampilla"] == 0.0
        assert estampilla["tarifa_aplicada"] == 0.0
        assert estampilla["valor_factura_sin_iva"] == 0.0
        assert estampilla["rango_uvt"] == ""
        assert estampilla["valor_contrato_pesos"] == 0.0
        assert estampilla["valor_contrato_uvt"] == 0.0
        assert estampilla["mensajes_error"] == ["No se identifico contrato de estampilla"]
        assert estampilla["razon"] == "Negocio sin recurso de estampilla"

        # Verificar logging
        mock_logger.info.assert_called_once()
        assert "Estampilla Universidad" in mock_logger.info.call_args[0][0]

    def test_agregar_estampilla_sin_razon_usa_default(
        self, validador, resultado_final_vacio, deteccion_impuestos_minimo
    ):
        """Test: Usa razon por defecto cuando no hay razon_no_aplica_estampilla"""
        validador._agregar_estampilla_no_aplicada(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_minimo,
            aplica_estampilla=False,
            nombre_negocio="Universidad Nacional"
        )

        estampilla = resultado_final_vacio["impuestos"]["estampilla_universidad"]

        assert estampilla["razon"] == "El negocio Universidad Nacional no aplica este impuesto"

    def test_agregar_estampilla_sin_estado_especial_usa_default(
        self, validador, resultado_final_vacio, deteccion_impuestos_minimo
    ):
        """Test: Usa estado por defecto cuando no hay estado_especial"""
        validador._agregar_estampilla_no_aplicada(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_minimo,
            aplica_estampilla=False,
            nombre_negocio="Universidad Nacional"
        )

        estampilla = resultado_final_vacio["impuestos"]["estampilla_universidad"]

        assert estampilla["estado"] == "no_aplica_impuesto"

    def test_agregar_estampilla_no_agrega_si_aplica_true(
        self, validador, resultado_final_vacio, deteccion_impuestos_completo
    ):
        """Test: No agrega estampilla si aplica=True"""
        validador._agregar_estampilla_no_aplicada(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_estampilla=True,
            nombre_negocio="Universidad Nacional"
        )

        assert "estampilla_universidad" not in resultado_final_vacio["impuestos"]

    def test_agregar_estampilla_no_agrega_si_ya_existe(
        self, validador, resultado_final_con_estampilla, deteccion_impuestos_completo
    ):
        """Test: No sobrescribe si estampilla ya existe"""
        valor_original = resultado_final_con_estampilla["impuestos"]["estampilla_universidad"]["valor_estampilla"]

        validador._agregar_estampilla_no_aplicada(
            resultado_final=resultado_final_con_estampilla,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_estampilla=False,
            nombre_negocio="Universidad Nacional"
        )

        # No debe cambiar el valor original
        assert resultado_final_con_estampilla["impuestos"]["estampilla_universidad"]["valor_estampilla"] == valor_original

    # =================================================================
    # TESTS DE _agregar_obra_publica_no_aplicada
    # =================================================================

    def test_agregar_obra_publica_estructura_completa(
        self, validador, resultado_final_vacio, deteccion_impuestos_completo
    ):
        """Test: Agrega estructura completa de obra publica"""
        validador._agregar_obra_publica_no_aplicada(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_obra_publica=False,
            nombre_negocio="Universidad Nacional"
        )

        obra_publica = resultado_final_vacio["impuestos"]["contribucion_obra_publica"]

        assert obra_publica["aplica"] is False
        assert obra_publica["estado"] == "recurso_no_identificado"
        assert obra_publica["tarifa_aplicada"] == 0.0
        assert obra_publica["valor_contribucion"] == 0.0
        assert obra_publica["valor_factura_sin_iva"] == 0.0
        assert obra_publica["mensajes_error"] == ["No se identifico contrato de estampilla"]
        assert obra_publica["razon"] == "Negocio sin recurso de obra publica"

    def test_agregar_obra_publica_no_agrega_si_aplica_true(
        self, validador, resultado_final_vacio, deteccion_impuestos_completo
    ):
        """Test: No agrega obra publica si aplica=True"""
        validador._agregar_obra_publica_no_aplicada(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_obra_publica=True,
            nombre_negocio="Universidad Nacional"
        )

        assert "contribucion_obra_publica" not in resultado_final_vacio["impuestos"]

    # =================================================================
    # TESTS DE _agregar_iva_no_aplicado
    # =================================================================

    def test_agregar_iva_estructura_completa(self, validador, resultado_final_vacio):
        """Test: Agrega estructura completa de IVA/ReteIVA"""
        validador._agregar_iva_no_aplicado(
            resultado_final=resultado_final_vacio,
            aplica_iva=False,
            nit_administrativo="900123456"
        )

        iva = resultado_final_vacio["impuestos"]["iva_reteiva"]

        assert iva["aplica"] is False
        assert iva["valor_iva_identificado"] == 0
        assert iva["valor_subtotal_sin_iva"] == 0
        assert iva["valor_reteiva"] == 0
        assert iva["porcentaje_iva"] == 0
        assert iva["tarifa_reteiva"] == 0
        assert iva["es_fuente_nacional"] is False
        assert iva["estado_liquidacion"] == "no_aplica_impuesto"
        assert iva["observaciones"] == ["El NIT 900123456 no esta configurado para IVA/ReteIVA"]
        assert iva["calculo_exitoso"] is False

    def test_agregar_iva_no_agrega_si_aplica_true(self, validador, resultado_final_vacio):
        """Test: No agrega IVA si aplica=True"""
        validador._agregar_iva_no_aplicado(
            resultado_final=resultado_final_vacio,
            aplica_iva=True,
            nit_administrativo="900123456"
        )

        assert "iva_reteiva" not in resultado_final_vacio["impuestos"]

    # =================================================================
    # TESTS DE _agregar_tasa_prodeporte_no_aplicada
    # =================================================================

    def test_agregar_tasa_prodeporte_estructura_completa(self, validador, resultado_final_vacio):
        """Test: Agrega estructura completa de tasa prodeporte"""
        validador._agregar_tasa_prodeporte_no_aplicada(
            resultado_final=resultado_final_vacio,
            aplica_tasa_prodeporte=False,
            nit_administrativo="900123456"
        )

        tasa = resultado_final_vacio["impuestos"]["tasa_prodeporte"]

        assert tasa["estado"] == "no_aplica_impuesto"
        assert tasa["aplica"] is False
        assert tasa["valor_imp"] == 0.0
        assert tasa["tarifa"] == 0.0
        assert tasa["valor_convenio_sin_iva"] == 0.0
        assert tasa["porcentaje_convenio"] == 0.0
        assert tasa["valor_contrato_municipio"] == 0.0
        assert tasa["factura_sin_iva"] == 0.0
        assert tasa["factura_con_iva"] == 0.0
        assert tasa["municipio_dept"] == ""
        assert tasa["numero_contrato"] == ""
        assert "PATRIMONIO AUTONOMO FONTUR" in tasa["observaciones"]
        assert "900649119" in tasa["observaciones"]
        assert "fecha_calculo" in tasa

    def test_agregar_tasa_prodeporte_no_agrega_si_aplica_true(self, validador, resultado_final_vacio):
        """Test: No agrega tasa prodeporte si aplica=True"""
        validador._agregar_tasa_prodeporte_no_aplicada(
            resultado_final=resultado_final_vacio,
            aplica_tasa_prodeporte=True,
            nit_administrativo="900123456"
        )

        assert "tasa_prodeporte" not in resultado_final_vacio["impuestos"]

    # =================================================================
    # TESTS DE _agregar_timbre_no_aplicado
    # =================================================================

    def test_agregar_timbre_estructura_completa(self, validador, resultado_final_vacio):
        """Test: Agrega estructura completa de timbre"""
        validador._agregar_timbre_no_aplicado(
            resultado_final=resultado_final_vacio,
            aplica_timbre=False,
            nit_administrativo="900123456"
        )

        timbre = resultado_final_vacio["impuestos"]["timbre"]

        assert timbre["aplica"] is False
        assert timbre["estado"] == "no_aplica_impuesto"
        assert timbre["valor"] == 0.0
        assert timbre["tarifa"] == 0.0
        assert timbre["tipo_cuantia"] == ""
        assert timbre["base_gravable"] == 0.0
        assert timbre["ID_contrato"] == ""
        assert timbre["observaciones"] == "Nit 900123456 no aplica impuesto al timbre"

    def test_agregar_timbre_no_agrega_si_aplica_true(self, validador, resultado_final_vacio):
        """Test: No agrega timbre si aplica=True"""
        validador._agregar_timbre_no_aplicado(
            resultado_final=resultado_final_vacio,
            aplica_timbre=True,
            nit_administrativo="900123456"
        )

        assert "timbre" not in resultado_final_vacio["impuestos"]

    # =================================================================
    # TESTS DEL METODO PRINCIPAL agregar_impuestos_no_aplicados
    # =================================================================

    def test_agregar_impuestos_no_aplicados_todos_aplican(
        self, validador, resultado_final_vacio, deteccion_impuestos_completo
    ):
        """Test: No agrega nada si todos los impuestos aplican"""
        validador.agregar_impuestos_no_aplicados(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_estampilla=True,
            aplica_obra_publica=True,
            aplica_iva=True,
            aplica_tasa_prodeporte=True,
            aplica_timbre=True,
            nit_administrativo="900123456",
            nombre_negocio="Universidad Nacional"
        )

        assert len(resultado_final_vacio["impuestos"]) == 0

    def test_agregar_impuestos_no_aplicados_solo_estampilla(
        self, validador, resultado_final_vacio, deteccion_impuestos_completo
    ):
        """Test: Agrega solo estampilla si es el unico que no aplica"""
        validador.agregar_impuestos_no_aplicados(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_estampilla=False,
            aplica_obra_publica=True,
            aplica_iva=True,
            aplica_tasa_prodeporte=True,
            aplica_timbre=True,
            nit_administrativo="900123456",
            nombre_negocio="Universidad Nacional"
        )

        assert "estampilla_universidad" in resultado_final_vacio["impuestos"]
        assert len(resultado_final_vacio["impuestos"]) == 1

    def test_agregar_impuestos_no_aplicados_multiples(
        self, validador, resultado_final_vacio, deteccion_impuestos_completo
    ):
        """Test: Agrega multiples impuestos cuando varios no aplican"""
        validador.agregar_impuestos_no_aplicados(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_estampilla=False,
            aplica_obra_publica=False,
            aplica_iva=False,
            aplica_tasa_prodeporte=True,
            aplica_timbre=True,
            nit_administrativo="900123456",
            nombre_negocio="Universidad Nacional"
        )

        assert "estampilla_universidad" in resultado_final_vacio["impuestos"]
        assert "contribucion_obra_publica" in resultado_final_vacio["impuestos"]
        assert "iva_reteiva" in resultado_final_vacio["impuestos"]
        assert len(resultado_final_vacio["impuestos"]) == 3

    def test_agregar_impuestos_no_aplicados_todos_los_impuestos(
        self, validador, resultado_final_vacio, deteccion_impuestos_completo
    ):
        """Test: Agrega todos los impuestos cuando ninguno aplica"""
        validador.agregar_impuestos_no_aplicados(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_estampilla=False,
            aplica_obra_publica=False,
            aplica_iva=False,
            aplica_tasa_prodeporte=False,
            aplica_timbre=False,
            nit_administrativo="900123456",
            nombre_negocio="Universidad Nacional"
        )

        assert "estampilla_universidad" in resultado_final_vacio["impuestos"]
        assert "contribucion_obra_publica" in resultado_final_vacio["impuestos"]
        assert "iva_reteiva" in resultado_final_vacio["impuestos"]
        assert "tasa_prodeporte" in resultado_final_vacio["impuestos"]
        assert "timbre" in resultado_final_vacio["impuestos"]
        assert len(resultado_final_vacio["impuestos"]) == 5

    def test_agregar_impuestos_no_aplicados_modificacion_in_place(
        self, validador, deteccion_impuestos_completo
    ):
        """Test: Verifica que resultado_final se modifica in-place"""
        resultado_original = {"impuestos": {}}
        id_original = id(resultado_original)

        validador.agregar_impuestos_no_aplicados(
            resultado_final=resultado_original,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_estampilla=False,
            aplica_obra_publica=False,
            aplica_iva=False,
            aplica_tasa_prodeporte=False,
            aplica_timbre=False,
            nit_administrativo="900123456",
            nombre_negocio="Universidad Nacional"
        )

        # El ID del diccionario no cambia (modificacion in-place)
        assert id(resultado_original) == id_original
        # Pero si tiene nuevos impuestos
        assert len(resultado_original["impuestos"]) == 5

    # =================================================================
    # TESTS DE LA FUNCION WRAPPER
    # =================================================================

    @patch('app.impuestos_no_aplicados.ValidadorNoAplicacion')
    def test_funcion_wrapper_crea_validador(self, mock_validador_class):
        """Test: Funcion wrapper crea instancia de ValidadorNoAplicacion"""
        mock_instance = Mock()
        mock_validador_class.return_value = mock_instance

        resultado_final = {"impuestos": {}}
        deteccion_impuestos = {}

        agregar_impuestos_no_aplicados(
            resultado_final=resultado_final,
            deteccion_impuestos=deteccion_impuestos,
            aplica_estampilla=False,
            aplica_obra_publica=False,
            aplica_iva=False,
            aplica_tasa_prodeporte=False,
            aplica_timbre=False,
            nit_administrativo="900123456",
            nombre_negocio="Universidad Nacional"
        )

        # Verifica que se creo la instancia
        mock_validador_class.assert_called_once()
        # Verifica que se llamo al metodo
        mock_instance.agregar_impuestos_no_aplicados.assert_called_once()

    def test_funcion_wrapper_modificacion_in_place(self):
        """Test: Funcion wrapper modifica resultado_final in-place"""
        resultado_final = {"impuestos": {}}
        id_original = id(resultado_final)

        agregar_impuestos_no_aplicados(
            resultado_final=resultado_final,
            deteccion_impuestos={},
            aplica_estampilla=False,
            aplica_obra_publica=False,
            aplica_iva=False,
            aplica_tasa_prodeporte=False,
            aplica_timbre=False,
            nit_administrativo="900123456",
            nombre_negocio="Universidad Nacional"
        )

        # El ID no cambia (modificacion in-place)
        assert id(resultado_final) == id_original
        # Pero si tiene impuestos agregados
        assert len(resultado_final["impuestos"]) == 5

    # =================================================================
    # TESTS DE LOGGING
    # =================================================================

    def test_logging_estampilla(self, validador, mock_logger, resultado_final_vacio, deteccion_impuestos_completo):
        """Test: Verifica que se registra log para estampilla"""
        validador._agregar_estampilla_no_aplicada(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_estampilla=False,
            nombre_negocio="Universidad Nacional"
        )

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "Estampilla Universidad" in log_message
        assert "recurso_no_identificado" in log_message

    def test_logging_multiple_impuestos(self, validador, mock_logger, resultado_final_vacio, deteccion_impuestos_completo):
        """Test: Verifica logs para multiples impuestos"""
        validador.agregar_impuestos_no_aplicados(
            resultado_final=resultado_final_vacio,
            deteccion_impuestos=deteccion_impuestos_completo,
            aplica_estampilla=False,
            aplica_obra_publica=False,
            aplica_iva=False,
            aplica_tasa_prodeporte=False,
            aplica_timbre=False,
            nit_administrativo="900123456",
            nombre_negocio="Universidad Nacional"
        )

        # Debe haber 5 llamadas al logger (una por cada impuesto)
        assert mock_logger.info.call_count == 5

        # Verificar que se loguean todos los impuestos
        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("Estampilla Universidad" in msg for msg in log_messages)
        assert any("Contribucion Obra Publica" in msg for msg in log_messages)
        assert any("IVA/ReteIVA" in msg for msg in log_messages)
        assert any("Tasa Prodeporte" in msg for msg in log_messages)
        assert any("Timbre" in msg for msg in log_messages)
