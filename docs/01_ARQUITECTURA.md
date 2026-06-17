# Arquitectura

## Principio central

> La IA **identifica** datos. Python **calcula y valida** según la normativa.

Gemini se usa para extraer y clasificar información de los documentos (conceptos
facturados, valores, tipo de tercero, ubicaciones, etc.). El cálculo de cada impuesto
y las validaciones normativas se hacen en código Python determinista. La IA **nunca**
aplica tarifas ni decide normativa: eso garantiza trazabilidad y auditabilidad de los
resultados.

**Fuente de verdad de los datos normativos**: la API de Nexura. El valor del UVT, los
conceptos de retefuente y los códigos de negocio se cargan desde la API al arranque y
por solicitud. No existe ningún archivo `.xlsx` como fuente de datos.

## Capas (Clean Architecture)

```
modelos/        Dominio: modelos de datos (Pydantic) - AnalisisFactura, ResultadoLiquidacion, etc.
app/            Aplicación: orquestación y validación por impuesto, concurrencia
Clasificador/   Infraestructura IA: interacción con Gemini (un clasificador por impuesto)
Liquidador/     Negocio: cálculo y validación por impuesto (un liquidador por dominio)
Extraccion/     Infraestructura: extracción de texto de archivos (PDF, Word, Excel, ZIP, email)
database/       Infraestructura: acceso a datos vía API de Nexura, bajo interfaces (ABC)
Background/     Infraestructura: procesamiento asíncrono post-respuesta y publicación por webhook
Conversor/      Servicios externos: conversión TRM (USD -> COP)
config.py       Configuración central: carga UVT/conceptos/códigos de negocio
main.py         Punto de entrada: app FastAPI, endpoints y ciclo de vida (lifespan)
```

Cada impuesto está separado por responsabilidad única: tiene su clasificador
(`Clasificador/`), su prompt (`prompts/`), su liquidador (`Liquidador/`) y su
orquestador de validación (`app/validar_*.py`).

## Flujo de procesamiento

El endpoint responde de inmediato y procesa en segundo plano; el resultado final se
entrega por webhook.

```
POST /api/procesar-facturas (archivos + datos del negocio)
   │
   ├─ Lee los archivos a bytes y registra una tarea en background
   └─ Responde 200 inmediato { status: "processing", factura_id }
         │
         ▼  (BackgroundProcessor.procesar_factura_background)
   1. Re-autenticación con Nexura (token fresco, con reintentos)
   2. Validación de negocio y detección de impuestos aplicables (según código de negocio / NIT)
   3. Validación y filtrado de archivos
   4. Extracción híbrida de texto (PDF/imágenes/Excel/Word/ZIP/emails)
   5. Clasificación de documentos con Gemini, en dos fases:
        a) Clasificación por lotes (tipo y relevancia de cada documento)
        b) Análisis global (consorcio, recurso/facturación extranjera, ubicación)
   6. Preparación de tareas de análisis por impuesto
   7. Ejecución en paralelo de los análisis (asyncio.gather)
   8. Liquidación por impuesto (retefuente, especiales, IVA/ReteIVA, estampillas
      generales, ICA, sobretasa bomberil, tasa prodeporte, timbre)
   9. Se completan los impuestos que no aplican
  10. Guardado del JSON en Results/AAAA-MM-DD/ (respaldo local)
  11. Publicación del resultado por webhook (POST con reintentos)
```

Trazabilidad en código: `main.py` (`/api/procesar-facturas`) →
`Background/background_processor.py` (`procesar_factura_background` y
`_ejecutar_flujo_completo`) → módulos `app/validar_*.py` y `Liquidador/`.

Si el procesamiento falla, el sistema igualmente publica por webhook una respuesta que
respeta el contrato de la API (estado `preliquidacion_sin_finalizar` con un mensaje
para el usuario), en lugar de un error crudo. El detalle técnico (con traceback) se
guarda solo en el JSON local para soporte interno.

## Cómo extender: agregar un impuesto nuevo

1. `Clasificador/clasificador_X.py` — llamada a Gemini para identificar los datos.
2. `prompts/prompt_X.py` — prompt especializado del impuesto.
3. `Liquidador/liquidador_X.py` — cálculo y validación en Python.
4. `app/validar_X.py` — orquestación del flujo del impuesto.
5. `config.py` — función `nit_aplica_X()` / parámetros desde la base de datos.
6. Integrarlo en el flujo paralelo de `Background/background_processor.py`.
7. `tests/test_X.py` — pruebas en la carpeta `tests/`.

## Decisiones de diseño (y por qué)

- **La IA solo identifica; Python calcula.** Permite auditar cada cifra y cumplir la
  normativa de forma determinista; los modelos no deciden tarifas.
- **La API de Nexura es la fuente de verdad.** UVT, conceptos y códigos de negocio se
  cargan desde Nexura, no desde archivos locales, para que la normativa vigente se
  actualice sin redeploy.
- **Procesamiento asíncrono con respuesta inmediata.** El cliente recibe 200 al
  instante y el resultado llega por webhook; evita timeouts en procesos de 30–60 s.
- **Carga con caché TTL.** El UVT y los códigos de negocio se cachean en memoria con
  expiración para reducir llamadas a la API sin servir datos obsoletos.
- **Fuente de datos única: Nexura.** Existe en el código una implementación de
  respaldo sobre Supabase (`SupabaseDatabase` / `DatabaseWithFallback`) que se utilizó
  durante el desarrollo, cuando la base de datos de Nexura tardaba en levantar.
  Actualmente está **desactivada** (el bloque de fallback se conserva comentado en
  `database/setup.py`): con `DATABASE_TYPE=nexura`, el valor por defecto, el sistema
  opera únicamente contra la API de Nexura.
- **Clasificación en dos fases.** Separar "tipo/relevancia" del "análisis global"
  reduce ruido y permite procesar cualquier cantidad de archivos por lotes en paralelo.
- **Re-autenticación por tarea.** Cada procesamiento obtiene un token fresco de Nexura
  antes de empezar, evitando fallos por tokens expirados.
