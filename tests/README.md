# Tests - Preliquidador de Impuestos Colombianos

## Directorio de Pruebas

Esta carpeta contiene todos los tests del proyecto. **NO se deben crear tests en archivos de producción** (main.py, liquidadores, clasificadores, etc.).

## Objetivo

Mantener el código de producción limpio y separado de las pruebas, siguiendo el **Principio de Separación de Responsabilidades (SRP)**.

## Tests Disponibles

### test_liquidador_sobretasa_bomberil.py
Tests completos para el liquidador de Sobretasa Bomberil con 11 casos de prueba:

**Ejecutar**: `python tests/test_liquidador_sobretasa_bomberil.py`

**Casos de prueba**:
1. ICA con valor > 0 y ubicación con tarifa (exitoso)
2. Múltiples ubicaciones, algunas con tarifa
3. Todas las ubicaciones con tarifa
4. ICA con valor = 0 (no aplica)
5. ICA válido pero ubicación sin tarifa en BD
6. ICA sin actividades facturadas
7. Error al consultar base de datos
8. Excepción general durante liquidación
9. Extracción de ubicaciones del resultado ICA
10. Obtención de tarifa de BD exitosa
11. Obtención de tarifa BD sin registros

**Características**:
- Usa mocks para simular respuestas de ICA y base de datos
- Tests aislados e independientes
- Validación de cálculos: `valor_sobretasa = valor_ica × tarifa`
- Cobertura de casos exitosos, errores y edge cases

## 📁 Estructura Sugerida

```
tests/
├── __init__.py                    # Inicializador del paquete de tests
├── README.md                      # Este archivo
├── test_liquidador.py             # Tests para liquidadores
├── test_clasificador.py           # Tests para clasificadores
├── test_config.py                 # Tests para configuración
├── test_api.py                    # Tests de endpoints API
├── test_integracion.py            # Tests de integración end-to-end
└── fixtures/                      # Datos de prueba
    ├── facturas_prueba/
    └── respuestas_esperadas/
```

## 🔧 Uso de Tests

### Ejecutar todos los tests
```bash
pytest tests/
```

### Ejecutar tests específicos
```bash
pytest tests/test_liquidador.py
pytest tests/test_liquidador.py::test_calculo_retencion
```

### Con cobertura
```bash
pytest tests/ --cov=. --cov-report=html
```

## ✅ Buenas Prácticas

1. **Separación total**: Los tests están en `tests/`, el código en módulos principales
2. **Nombres descriptivos**: `test_calculo_retencion_art383_persona_natural()`
3. **Fixtures reutilizables**: Crear datos de prueba en `fixtures/`
4. **Mocks para IA**: No hacer llamadas reales a Gemini en tests
5. **Tests aislados**: Cada test debe ser independiente

## 🚫 NO Hacer

❌ **NO** agregar tests en `main.py`
❌ **NO** agregar tests en archivos de liquidadores
❌ **NO** agregar tests en archivos de clasificadores
❌ **NO** mezclar código de producción con código de prueba

## ✅ Hacer

✅ **SÍ** crear archivos de test en `tests/`
✅ **SÍ** usar mocks para dependencias externas
✅ **SÍ** mantener tests simples y legibles
✅ **SÍ** documentar casos edge complejos
