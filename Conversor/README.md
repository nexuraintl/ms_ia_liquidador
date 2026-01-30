# Modulo Conversor TRM

Cliente Python para consumir el servicio web de TRM (Tasa Representativa del Mercado) de la Superintendencia Financiera de Colombia.

## Descripcion

Este modulo proporciona una interfaz limpia y robusta para obtener la tasa de cambio oficial COP/USD y realizar conversiones de moneda siguiendo los principios SOLID.

## Caracteristicas

- Obtencion de TRM actual o historica
- Conversion USD a COP y viceversa
- Manejo robusto de errores
- Validacion de datos
- Soporte para context manager
- Tests comprehensivos incluidos

## Arquitectura SOLID

### Single Responsibility Principle (SRP)
- `ConversorTRM`: Solo maneja comunicacion con el servicio TRM
- `exceptions.py`: Solo define excepciones del modulo

### Open/Closed Principle (OCP)
- Extensible para nuevos tipos de conversion sin modificar codigo existente

### Dependency Inversion Principle (DIP)
- Depende de abstracciones (requests HTTP) no de implementaciones concretas

## Instalacion

Asegurese de tener las dependencias instaladas:

```bash
pip install requests
```

## Uso Basico

### Importar el modulo

```python
from Conversor import ConversorTRM
from Conversor.exceptions import TRMServiceError, TRMValidationError
```

### Obtener TRM actual

```python
conversor = ConversorTRM()
try:
    resultado = conversor.obtener_trm()
    print(f"TRM actual: {resultado['value']} COP/USD")
    print(f"Vigencia desde: {resultado['validityFrom']}")
    print(f"Vigencia hasta: {resultado['validityTo']}")
finally:
    conversor.cerrar_sesion()
```

### Obtener TRM historica

```python
conversor = ConversorTRM()
try:
    resultado = conversor.obtener_trm("2020-03-06")
    print(f"TRM 2020-03-06: {resultado['value']} COP/USD")
finally:
    conversor.cerrar_sesion()
```

### Obtener solo el valor de TRM

```python
conversor = ConversorTRM()
try:
    trm_valor = conversor.obtener_trm_valor()
    print(f"TRM: {trm_valor}")
finally:
    conversor.cerrar_sesion()
```

### Usar como Context Manager (Recomendado)

```python
with ConversorTRM() as conversor:
    trm_valor = conversor.obtener_trm_valor()
    print(f"TRM: {trm_valor}")
```

### Convertir USD a COP

```python
with ConversorTRM() as conversor:
    monto_cop = conversor.convertir_usd_a_cop(100.0)
    print(f"100 USD = {monto_cop} COP")
```

### Convertir COP a USD

```python
with ConversorTRM() as conversor:
    monto_usd = conversor.convertir_cop_a_usd(3500000.0)
    print(f"3,500,000 COP = {monto_usd} USD")
```

### Convertir con fecha especifica

```python
with ConversorTRM() as conversor:
    monto_cop = conversor.convertir_usd_a_cop(100.0, fecha="2020-03-06")
    print(f"100 USD = {monto_cop} COP (TRM del 2020-03-06)")
```

## Manejo de Errores

```python
from Conversor import ConversorTRM
from Conversor.exceptions import TRMServiceError, TRMValidationError

with ConversorTRM() as conversor:
    try:
        # Intentar obtener TRM
        resultado = conversor.obtener_trm("2020-03-06")

    except TRMValidationError as e:
        print(f"Error de validacion: {e}")
        # Formato de fecha invalido, monto negativo, etc.

    except TRMServiceError as e:
        print(f"Error del servicio: {e}")
        # Timeout, error SSL, error HTTP, etc.
```

## Configuracion

### Timeout personalizado

```python
# Timeout de 60 segundos
conversor = ConversorTRM(timeout=60)
```

## Estructura del Resultado

El metodo `obtener_trm()` retorna un diccionario con la siguiente estructura:

```python
{
    'id': '2521951',                                    # ID de la TRM
    'unit': 'COP',                                      # Unidad monetaria
    'validityFrom': '2020-03-06T00:00:00-05:00',       # Vigencia desde
    'validityTo': '2020-03-06T00:00:00-05:00',         # Vigencia hasta
    'value': 3468.78,                                   # Valor TRM (float)
    'success': 'true'                                   # Exito de la consulta
}
```

## Excepciones

### `ConversorTRMError`
Excepcion base del modulo.

### `TRMValidationError`
Se lanza cuando hay errores de validacion:
- Formato de fecha invalido
- Monto negativo en conversiones

### `TRMServiceError`
Se lanza cuando hay errores de comunicacion con el servicio:
- Timeout de conexion
- Error SSL/Certificado
- Error HTTP (4xx, 5xx)
- Error de conexion
- Respuesta XML invalida

## Tests

### Ejecutar todos los tests

```bash
cd tests
python -m pytest test_conversor_trm.py -v
```

O con unittest:

```bash
cd tests
python test_conversor_trm.py
```

### Ejecutar tests de integracion (requiere internet)

Los tests de integracion estan deshabilitados por defecto. Para ejecutarlos:

```python
# En test_conversor_trm.py, remover @unittest.skip de los tests de integracion
python test_conversor_trm.py
```

### Cobertura de tests

Los tests cubren:
- Construccion de requests SOAP
- Validacion de formatos de fecha
- Extraccion de datos de respuestas XML
- Manejo de errores HTTP
- Conversiones de moneda
- Context manager
- Configuracion personalizada

## Notas Importantes

1. **Formato de fecha**: Debe ser YYYY-MM-DD (ej: "2020-03-06")

2. **TRM de fin de semana**: Si se consulta un sabado o domingo, el servicio retorna la TRM vigente para esos dias.

3. **TRM futura**: Si se consulta una fecha futura para la que aun no se ha publicado TRM, el servicio retorna la mas reciente disponible.

4. **Certificado SSL**: El modulo verifica el certificado SSL del servidor. No deshabilitar esta verificacion.

5. **Timeout**: El timeout por defecto es 30 segundos. Ajustar segun necesidades.

## Dependencias

- Python 3.7+
- requests >= 2.25.0

## Servicio Web

Este modulo consume el servicio oficial de la Superintendencia Financiera de Colombia:

- **URL WSDL**: https://www.superfinanciera.gov.co/SuperfinancieraWebServiceTRM/TCRMServicesWebService/TCRMServicesWebService?WSDL
- **TLS**: 1.2 y 1.3
- **Documentacion**: Ver PDF incluido en el proyecto

## Ejemplo Completo

```python
from Conversor import ConversorTRM
from Conversor.exceptions import TRMServiceError, TRMValidationError

def obtener_conversion_usd():
    """Ejemplo completo de uso del conversor"""

    with ConversorTRM(timeout=30) as conversor:
        try:
            # Obtener TRM actual
            print("=== TRM ACTUAL ===")
            resultado = conversor.obtener_trm()
            print(f"Valor: {resultado['value']}")
            print(f"Vigencia: {resultado['validityFrom']} - {resultado['validityTo']}")

            # Convertir USD a COP
            print("\n=== CONVERSION USD A COP ===")
            monto_usd = 1000.0
            monto_cop = conversor.convertir_usd_a_cop(monto_usd)
            print(f"{monto_usd} USD = {monto_cop:,.2f} COP")

            # Convertir COP a USD
            print("\n=== CONVERSION COP A USD ===")
            monto_cop = 3500000.0
            monto_usd = conversor.convertir_cop_a_usd(monto_cop)
            print(f"{monto_cop:,.0f} COP = {monto_usd:.2f} USD")

            # Obtener TRM historica
            print("\n=== TRM HISTORICA ===")
            fecha = "2020-03-06"
            resultado_historico = conversor.obtener_trm(fecha)
            print(f"TRM {fecha}: {resultado_historico['value']}")

        except TRMValidationError as e:
            print(f"Error de validacion: {e}")

        except TRMServiceError as e:
            print(f"Error del servicio TRM: {e}")

        except Exception as e:
            print(f"Error inesperado: {e}")

if __name__ == "__main__":
    obtener_conversion_usd()
```

## Licencia

Este modulo es parte del proyecto PRELIQUIDADOR.

## Contacto

Para reportar problemas o sugerir mejoras, crear un issue en el repositorio del proyecto.
