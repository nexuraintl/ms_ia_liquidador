# Pruebas

La suite de pruebas vive íntegramente en `tests/` (convención del proyecto: ningún
código de prueba se mezcla con el de producción). Usa `pytest`.

## Cómo ejecutar

Ejecuta siempre con el **entorno virtual del proyecto**, no con el Python global:

```bash
# Windows
.\venv\Scripts\pytest tests/

# Linux/Mac
./venv/bin/pytest tests/
```

> **Importante:** correr `pytest` con el intérprete global de la máquina produce un
> fallo de importación de `python-calamine` (usado en el preprocesamiento de Excel,
> `test_preprocesado_excel.py`). Con el venv del proyecto la dependencia está presente
> y la suite pasa correctamente.

Para ver el motivo de cada test omitido:

```bash
.\venv\Scripts\pytest tests/ -rs
```

## Estado actual

- **760 aprobados**
- **18 omitidos**
- **0 fallos**

## Por qué se omiten 18 tests

Todos los omitidos requieren dependencias externas o archivos de prueba locales que no
están en el repositorio; se saltan de forma segura para no producir falsos negativos:

| Archivo                              | Omitidos | Motivo                                                                 |
|--------------------------------------|----------|-----------------------------------------------------------------------|
| `test_conversor_trm.py`              | 3        | Pruebas de integración con llamadas de red reales; ejecución manual.  |
| `test_extractor_adjuntos.py`         | 12       | Falta el fixture local `test_archivo4.msg` (correo de prueba con datos reales, no se versiona). |
| `test_integracion_tasa_prodeporte.py`| 3        | Requieren conexión y credenciales válidas con la API Nexura.          |

Para habilitarlos: proveer el fixture `.msg` correspondiente y/o configurar las
credenciales y conectividad de los servicios externos en el `.env`.

## Convención

- Todos los tests nuevos van en `tests/` con el patrón `test_*.py`.
- Los datos de prueba (fixtures) van en `testsfixtures/`.
- Evitar tests que hagan llamadas externas reales a nivel de módulo: bloquean el
  recolector de pytest e inducen timeouts. Si una prueba necesita un servicio externo,
  márcala como integración/manual para que se omita por defecto.
