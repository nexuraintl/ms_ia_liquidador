"""
Tests para la carga de codigos de negocio (estampilla / obra publica) desde la API
con cache TTL, en reemplazo de los valores hardcodeados.

Cubre:
- refrescar_codigos_negocio: pobla los 3 dicts con claves int desde la API
- Respeto del TTL: con cache fresco no se vuelve a consultar la API
- Aborto sin fallback: si la API falla y no hay cache valido, lanza RuntimeError
- Integracion: detectar_impuestos_aplicables_por_codigo aplica/no aplica segun la
  lista cargada desde la API
- database_service: passthrough y mock
"""

import unittest

import config
from database.database_service import MockBusinessDataService


CODIGOS_API = {
    "69164": "PATRIMONIO AUTONOMO INNPULSA COLOMBIA",
    "69166": "PATRIMONIO AUTONOMO COLOMBIA PRODUCTIVA",
    "99664": "PATRIMONIO AUTONOMO FONDO MUJER EMPRENDE",
}


class _BusinessServiceOK(MockBusinessDataService):
    """Mock que devuelve codigos y reporta recursos publicos (para el flujo completo)."""

    def __init__(self, codigos=None):
        super().__init__(mock_codigos_negocio=codigos if codigos is not None else dict(CODIGOS_API))
        self.llamadas_codigos = 0

    def obtener_codigos_negocios_fiduciaria(self):
        self.llamadas_codigos += 1
        return super().obtener_codigos_negocios_fiduciaria()

    def validar_tipo_recurso_negocio(self, codigo_negocio):
        return {"success": True, "tipo_recurso": "Publicos", "aplica_impuestos": True}


class _BusinessServiceFail:
    """Mock cuya consulta de codigos falla."""

    def obtener_codigos_negocios_fiduciaria(self):
        return {"success": False, "data": None, "message": "API caida"}


class TestRefrescarCodigosNegocio(unittest.TestCase):

    def setUp(self):
        config.limpiar_cache_codigos_negocio()

    def tearDown(self):
        config.limpiar_cache_codigos_negocio()

    def test_pobla_los_tres_dicts_con_claves_int(self):
        bs = _BusinessServiceOK()
        config.refrescar_codigos_negocio(bs)

        self.assertEqual(set(config.CODIGOS_NEGOCIO_ESTAMPILLA.keys()), {69164, 69166, 99664})
        self.assertTrue(all(isinstance(k, int) for k in config.CODIGOS_NEGOCIO_ESTAMPILLA))
        # El alias de obra publica replica el mismo contenido
        self.assertEqual(config.CODIGOS_NEGOCIO_OBRA_PUBLICA, config.CODIGOS_NEGOCIO_ESTAMPILLA)
        # Terceros derivados de los nombres en MAYUSCULAS
        self.assertIn("PATRIMONIO AUTONOMO INNPULSA COLOMBIA", config.TERCEROS_RECURSOS_PUBLICOS)

    def test_cache_ttl_no_reconsulta_con_cache_fresco(self):
        bs = _BusinessServiceOK()
        config.refrescar_codigos_negocio(bs)
        config.refrescar_codigos_negocio(bs)
        config.refrescar_codigos_negocio(bs)
        self.assertEqual(bs.llamadas_codigos, 1)

    def test_aborta_sin_cache_cuando_api_falla(self):
        with self.assertRaises(RuntimeError):
            config.refrescar_codigos_negocio(_BusinessServiceFail())

    def test_aborta_si_business_service_none_sin_cache(self):
        with self.assertRaises(RuntimeError):
            config.refrescar_codigos_negocio(None)

    def test_cache_expirado_y_api_falla_aborta(self):
        bs = _BusinessServiceOK()
        config.refrescar_codigos_negocio(bs)
        # Forzar expiracion del cache
        config._cache_codigos_negocio_timestamp = None
        with self.assertRaises(RuntimeError):
            config.refrescar_codigos_negocio(_BusinessServiceFail())


class TestDeteccionConCodigosDesdeAPI(unittest.TestCase):

    def setUp(self):
        config.limpiar_cache_codigos_negocio()

    def tearDown(self):
        config.limpiar_cache_codigos_negocio()

    def test_codigo_valido_aplica_ambos_impuestos(self):
        bs = _BusinessServiceOK()
        resultado = config.detectar_impuestos_aplicables_por_codigo(
            69164, nit_administrativo="830054060", business_service=bs
        )
        self.assertTrue(resultado["aplica_estampilla_universidad"])
        self.assertTrue(resultado["aplica_contribucion_obra_publica"])

    def test_codigo_no_listado_no_aplica(self):
        bs = _BusinessServiceOK()
        resultado = config.detectar_impuestos_aplicables_por_codigo(
            11111, nit_administrativo="830054060", business_service=bs
        )
        self.assertFalse(resultado["aplica_estampilla_universidad"])
        self.assertFalse(resultado["aplica_contribucion_obra_publica"])

    def test_codigo_dinamico_se_refleja_en_validacion(self):
        # Si la API solo devuelve un codigo, los demas dejan de aplicar
        bs = _BusinessServiceOK(codigos={"77777": "PATRIMONIO NUEVO"})
        resultado = config.detectar_impuestos_aplicables_por_codigo(
            77777, nit_administrativo="830054060", business_service=bs
        )
        self.assertTrue(resultado["aplica_estampilla_universidad"])

        resultado_viejo = config.detectar_impuestos_aplicables_por_codigo(
            69164, nit_administrativo="830054060", business_service=bs
        )
        self.assertFalse(resultado_viejo["aplica_estampilla_universidad"])


class TestDatabaseServicePassthrough(unittest.TestCase):

    def test_mock_devuelve_codigos_por_defecto(self):
        bs = MockBusinessDataService()
        resultado = bs.obtener_codigos_negocios_fiduciaria()
        self.assertTrue(resultado["success"])
        self.assertIn("69164", resultado["data"])

    def test_business_service_sin_db_devuelve_error(self):
        from database.database_service import BusinessDataService
        bs = BusinessDataService(database_manager=None)
        resultado = bs.obtener_codigos_negocios_fiduciaria()
        self.assertFalse(resultado["success"])


if __name__ == "__main__":
    unittest.main()
