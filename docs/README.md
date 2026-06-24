# Documentación del Preliquidador de Impuestos

Versión del sistema: **3.19.8**

El Preliquidador es un servicio REST que recibe facturas y documentos de soporte
(PDF, imágenes, Excel, Word, ZIP, correos `.msg`/`.eml`), extrae su contenido y
calcula automáticamente múltiples impuestos colombianos. La inteligencia artificial
**identifica** datos (conceptos, valores, tipo de tercero); el código en Python
**calcula y valida** según la normativa. La IA nunca aplica tarifas ni normativa.

## Impuestos soportados

1. Retención en la Fuente (nacional, 43+ conceptos, y pagos al exterior con convenios)
2. IVA y ReteIVA
3. ICA (Industria y Comercio) y Sobretasa Bomberil
4. Estampilla Pro Universidad Nacional
5. Contribución a Obra Pública (5%)
6. Estampillas Generales
7. Impuesto al Timbre
8. Tasa Prodeporte
9. Tratamiento especial de Consorcios

## Cómo navegar esta documentación

| Si eres...                     | Empieza por                                                        |
|--------------------------------|-------------------------------------------------------------------|
| Desarrollador que continúa     | [01_ARQUITECTURA.md](01_ARQUITECTURA.md)                          |
| Operaciones / DevOps           | [02_DESPLIEGUE_OPERACION.md](02_DESPLIEGUE_OPERACION.md)          |
| Integrador / consumidor de API | [03_API.md](03_API.md)                                            |
| QA / responsable de calidad    | [04_PRUEBAS.md](04_PRUEBAS.md)                                    |
| Analista funcional / tributario| [05_REGLAS_NEGOCIO.md](05_REGLAS_NEGOCIO.md)                      |

## Documentos

- **[01_ARQUITECTURA.md](01_ARQUITECTURA.md)** — Capas, flujo de procesamiento,
  decisiones de diseño y cómo extender el sistema.
- **[02_DESPLIEGUE_OPERACION.md](02_DESPLIEGUE_OPERACION.md)** — Variables de
  entorno, ejecución local, Docker, Cloud Run, salud, logs y troubleshooting.
- **[03_API.md](03_API.md)** — Endpoints, parámetros, respuestas y contrato del webhook.
- **[04_PRUEBAS.md](04_PRUEBAS.md)** — Cómo ejecutar la suite de tests y su estado.
- **[05_REGLAS_NEGOCIO.md](05_REGLAS_NEGOCIO.md)** — Resumen de la lógica tributaria
  por impuesto.

> El historial detallado de cambios por versión está en `CHANGELOG.md` (raíz del proyecto).
