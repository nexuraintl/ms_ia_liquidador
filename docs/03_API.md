# API REST

Base URL local: `http://localhost:8080`. Documentación interactiva autogenerada en
`/docs` (Swagger UI) y `/redoc`.

## Endpoint principal

### `POST /api/procesar-facturas`

Recibe los archivos de una factura y sus parámetros de negocio, responde de inmediato
y procesa en segundo plano. El resultado final se entrega por **webhook** (ver abajo).

**Content-Type:** `multipart/form-data`

| Campo                      | Tipo            | Obligatorio | Descripción                                          |
|----------------------------|-----------------|-------------|------------------------------------------------------|
| `facturaId`                | int             | Sí          | Identificador único de la factura (lo asigna el cliente). Se devuelve tal cual en el webhook. |
| `archivos`                 | archivo[]       | Sí          | Uno o más archivos (factura, RUT, anexos, contratos). |
| `codigo_del_negocio`       | int             | Sí          | Código del negocio para consultar en la base de datos. |
| `proveedor`                | string          | Sí          | Nombre del proveedor que emite la factura.           |
| `nit_proveedor`            | string          | Sí          | NIT del proveedor.                                   |
| `estructura_contable`      | int             | Sí          | Estructura contable asociada.                        |
| `observaciones_tp`         | string          | No          | Observaciones para Tasa Prodeporte.                  |
| `genera_presupuesto`       | string          | No          | Indicador presupuestal (Tasa Prodeporte).            |
| `rubro`                    | string          | No          | Rubro presupuestal.                                  |
| `centro_costos`            | int             | No          | Centro de costos.                                    |
| `numero_contrato`          | string          | No          | Número de contrato.                                  |
| `valor_contrato_municipio` | float           | No          | Valor del contrato por municipio.                    |
| `tipoMoneda`               | string          | No (`COP`)  | Moneda de la factura (`COP`, `USD`, ...).            |

**Respuesta inmediata `200 OK`:**

```json
{
  "factura_id": 12345,
  "status": "processing",
  "message": "Procesamiento iniciado en background",
  "timestamp": "2026-06-16T10:00:00.000000",
  "archivos_recibidos": 3,
  "codigo_negocio": 69164,
  "proveedor": "NOMBRE PROVEEDOR"
}
```

`status: "processing"` significa que la factura se aceptó y se está procesando. El
resultado **no** viaja en esta respuesta.

**Errores:** si falla la inicialización del job, responde `500` con un objeto
`detail` que incluye `tipo: "INITIALIZATION_ERROR"`.

### Restricciones de entrada

Definidas en `config.py` (`CONFIG`):
- Extensiones soportadas: `.pdf`, `.xlsx`, `.xls`, `.jpg`, `.jpeg`, `.png`, `.docx`, `.doc`
  (además ZIP y correos `.msg`/`.eml`, procesados por los extractores).
- Tamaño máximo por archivo: 50 MB.

## Contrato del webhook (resultado final)

Cuando el procesamiento termina, el servicio hace un `POST` a `WEBHOOK_URL` con el
resultado. Reintenta hasta `WEBHOOK_MAX_RETRIES` veces con backoff exponencial y
considera éxito los códigos `200`, `201` o `202`.

**Headers:** `Content-Type: application/json`. Si `WEBHOOK_AUTH_TYPE` es `bearer`
agrega `Authorization: Bearer <token>`; si es `api_key` agrega `X-API-Key: <token>`.

**Cuerpo del POST:**

```json
{
  "facturaId": 12345,
  "timestamp": "2026-06-16T10:01:00.000000",
  "data": {
    "impuestos_procesados": ["RETENCION_FUENTE", "IVA", "RETENCION_ICA"],
    "nit_administrativo": "800178148",
    "nombre_entidad": "Fiduciaria Colombiana de Comercio Exterior S.A.",
    "timestamp": "2026-06-16T10:01:00.000000",
    "version": "3.0.0",
    "impuestos": {
      "retefuente": { },
      "estampilla_universidad": { },
      "contribucion_obra_publica": { },
      "iva_reteiva": { },
      "estampillas_generales": { },
      "ica": { },
      "sobretasa_bomberil": { },
      "tasa_prodeporte": { },
      "timbre": { }
    },
    "es_consorcio": false,
    "es_facturacion_extranjera": false,
    "documentos_procesados": 3,
    "documentos_clasificados": ["factura.pdf", "rut.pdf"]
  }
}
```

### Envoltura del POST

| Campo       | Tipo   | Descripción                                                  |
|-------------|--------|--------------------------------------------------------------|
| `facturaId` | int    | El mismo `facturaId` que envió el cliente al endpoint.       |
| `timestamp` | string | Momento del envío (ISO 8601).                                |
| `data`      | object | Resultado de la liquidación (ver abajo).                     |

### Objeto `data`

| Campo                     | Tipo    | Descripción                                                        |
|---------------------------|---------|-------------------------------------------------------------------|
| `impuestos_procesados`    | array   | Impuestos que aplican al negocio.                                 |
| `nit_administrativo`      | string  | NIT de la entidad administrativa.                                |
| `nombre_entidad`          | string  | Nombre de la entidad.                                            |
| `version`                 | string  | Versión del contrato del resultado.                              |
| `impuestos`               | object  | Detalle por impuesto (una clave por impuesto). Ver abajo.        |
| `es_consorcio`            | bool    | Si el proveedor es un consorcio (cambia la forma de `retefuente`).|
| `es_facturacion_extranjera` | bool  | Si la factura es del exterior.                                   |
| `documentos_procesados`   | int     | Cantidad de archivos procesados.                                |
| `documentos_clasificados` | array   | Nombres de los documentos relevantes clasificados.              |

Dentro de `impuestos` solo aparecen las claves de los impuestos que aplican al negocio.
Cada impuesto trae su propio detalle de cálculo, valores base y un campo `estado`.

**Estados posibles** (campo `estado` de cada impuesto):

| Estado                          | Significado                                                        |
|---------------------------------|-------------------------------------------------------------------|
| `preliquidado`                  | Se calculó correctamente.                                        |
| `no_aplica_impuesto`            | El impuesto no aplica a lo facturado (p. ej. ningún concepto mapea). |
| `preliquidacion_sin_finalizar`  | No se pudo completar (datos incompletos o fallo de un servicio externo); se sugiere revisar/reintentar. |

## Detalle de retención en la fuente

`data.impuestos.retefuente` **cambia de forma** según el tipo de tercero. Hay tres
variantes; el consumidor debe distinguirlas (la señal principal es `es_consorcio` en
`data`, y la presencia de la clave `consorciados` en el objeto).

### 1. Tercero normal (persona natural o jurídica)

Estructura plana: una sola retención para el proveedor.

```json
{
  "aplica": true,
  "estado": "preliquidado",
  "valor_factura_sin_iva": 10000000.0,
  "valor_retencion": 400000.0,
  "valor_base": 10000000.0,
  "conceptos_aplicados": [
    { "concepto": "Servicios generales (declarantes)", "tarifa_retencion": 4.0, "base_gravable": 10000000.0 }
  ],
  "observaciones": []
}
```

Si la factura es del exterior, se agrega `pais_proveedor`.

### 2. Consorcio

La retención se desglosa **por consorciado**, y dentro de cada uno **por concepto**.
No trae `valor_retencion` plano: el total va en `retencion_total`. La base mínima
normativa se valida contra la base gravable **individual** (proporcional a la
participación), por lo que un mismo concepto puede aplicar a un consorciado y no a otro.

```json
{
  "es_consorcio": true,
  "nombre_consorcio": "CONSORCIO EJEMPLO",
  "consorciados": [
    {
      "nombre": "EMPRESA A S.A.S.",
      "nit": "900111222",
      "porcentaje_participacion": 60.0,
      "aplica": true,
      "valor_retencion": 240000.0,
      "valor_base": 6000000.0,
      "conceptos_liquidados": [
        {
          "nombre_concepto": "Servicios generales (declarantes)",
          "codigo_concepto": "365",
          "tarifa_retencion": 0.04,
          "base_gravable_individual": 6000000.0,
          "base_minima_normativa": 100000.0,
          "aplica_concepto": true,
          "valor_retencion_concepto": 240000.0
        }
      ]
    },
    {
      "nombre": "EMPRESA B LTDA",
      "nit": "900333444",
      "porcentaje_participacion": 40.0,
      "aplica": false,
      "valor_retencion": 0.0,
      "valor_base": 4000000.0,
      "conceptos_liquidados": [],
      "razon_no_aplicacion": "Autorretenedor"
    }
  ],
  "retencion_total": 240000.0,
  "valor_factura_sin_iva": 10000000.0,
  "conceptos_aplicados": [
    { "concepto": "Servicios generales (declarantes)", "tarifa_retencion": 4.0, "base_gravable": 10000000.0 }
  ],
  "resumen_conceptos": "Servicios generales (declarantes) (4%)",
  "estado": "preliquidado",
  "observaciones": [],
  "procesamiento_exitoso": true
}
```

Puntos clave de la variante consorcio:
- **`consorciados[]`**: cada miembro con su `porcentaje_participacion`, su
  `valor_retencion`, su `valor_base` y el detalle `conceptos_liquidados[]`.
- **`aplica` por consorciado**: puede ser `false` por naturaleza tributaria
  (autorretenedor, régimen simple) o porque ningún concepto superó la base mínima
  individual; en ese caso aparece `razon_no_aplicacion`.
- **`conceptos_liquidados[].aplica_concepto`**: indica, por concepto y por
  consorciado, si superó la base mínima (`base_gravable_individual` ≥
  `base_minima_normativa`). Si no, trae `razon_no_aplicacion` y retención 0.
- **`retencion_total`**: suma de las retenciones de todos los consorciados (es el total
  del consorcio; no existe un `valor_retencion` plano como en el caso normal).
- **`observaciones`**: alertas no bloqueantes; por ejemplo, conceptos facturados que no
  se pudieron relacionar con la base de datos (se omiten sin abortar). La liquidación
  solo queda `preliquidacion_sin_finalizar` si **ningún** concepto mapea o si falta
  información de un consorciado (p. ej. el porcentaje de participación).

### 3. Recurso de fuente extranjera

Cuando el negocio administra recursos de fuente extranjera, retefuente no se liquida y
se devuelve una estructura vacía (`aplica: false`, `valor_retencion: 0`) con el estado
correspondiente y las observaciones del caso.

## Caso de procesamiento no finalizado

Si ocurre un error (por ejemplo, falla la conexión con la IA o con la API de datos),
`data` igualmente respeta el contrato y trae el estado `preliquidacion_sin_finalizar`
con un mensaje para el usuario y un bloque de diagnóstico (`retry_sugerido`,
`servicio_externo`, etc.). El detalle técnico (traceback) no se envía: queda en el JSON
local de `Results/`.

## Endpoints auxiliares

| Endpoint                          | Método | Descripción                               |
|-----------------------------------|--------|-------------------------------------------|
| `/api/diagnostico`                | GET    | Diagnóstico completo del sistema.         |
| `/api/database/health`            | GET    | Salud de la base de datos.                |
