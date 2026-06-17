# Despliegue y operación (runbook)

## Requisitos

- **Python 3.11** (imagen base `python:3.11-slim`).
- **poppler-utils** (sistema): dependencia de las librerías de manejo de PDF. Ya viene
  instalada en la imagen Docker; en local Linux/Mac instálala aparte.
- Dependencias Python: `pip install -r requirements.txt`.

## Variables de entorno

Se configuran en un archivo `.env` (local) o en el panel de variables del entorno de
despliegue. **Nunca** se versionan: `.env` está en `.gitignore`.

### Obligatorias

| Variable                | Uso                                                        |
|-------------------------|------------------------------------------------------------|
| `GEMINI_API_KEY`        | API key de Google Gemini. Sin ella el arranque aborta.     |
| `NEXURA_API_BASE_URL`   | URL base de la API Nexura (única fuente de datos).         |
| `NEXURA_LOGIN_USER`     | Usuario para autenticación con Nexura (por tarea).         |
| `NEXURA_LOGIN_PASSWORD` | Contraseña para autenticación con Nexura.                  |

> **Datos:** el sistema opera únicamente contra la API de Nexura (`DATABASE_TYPE=nexura`,
> el valor por defecto). Las variables `SUPABASE_URL` / `SUPABASE_KEY` corresponden a un
> respaldo en Supabase que se usó durante el desarrollo y hoy está **desactivado**; no
> son necesarias en la operación actual (solo se leerían si se reactivara el fallback o
> se pusiera `DATABASE_TYPE=supabase`).

### Opcionales (tienen valor por defecto)

| Variable                 | Default   | Uso                                                  |
|--------------------------|-----------|------------------------------------------------------|
| `DATABASE_TYPE`          | `nexura`  | Selecciona el backend de datos.                      |
| `NEXURA_AUTH_TYPE`       | `none`    | Tipo de autenticación de la API Nexura.              |
| `NEXURA_API_TIMEOUT`     | `30`      | Timeout (s) de las llamadas a la API Nexura.         |
| `NEXURA_JWT_TOKEN`       | —         | Token JWT (si `NEXURA_AUTH_TYPE` lo requiere).       |
| `NEXURA_API_KEY`         | —         | API key (si `NEXURA_AUTH_TYPE` lo requiere).         |
| `WEBHOOK_URL`            | —         | Destino del resultado final. Si falta, el webhook queda deshabilitado (el resultado solo se guarda local). |
| `WEBHOOK_TIMEOUT`        | `30`      | Timeout (s) del POST al webhook.                     |
| `WEBHOOK_MAX_RETRIES`    | `3`       | Reintentos del webhook (backoff exponencial).        |
| `WEBHOOK_AUTH_TYPE`      | `none`    | `none`, `bearer` o `api_key`.                        |
| `WEBHOOK_AUTH_TOKEN`     | —         | Token/clave del webhook (se refresca por tarea).     |
| `USE_RETEFUENTE_NEW`     | `false`   | Bandera interna de comportamiento de retefuente.     |
| `PORT`                   | `8080`    | Puerto de escucha (usado en contenedor).             |

> Verifica el bloque de datos con `GET /api/diagnostico` después de arrancar.

## Ejecución local

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
# Crear .env con las variables de arriba
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

El servicio queda en `http://localhost:8080`. Documentación interactiva:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

## Docker

```bash
docker build -t preliquidador .
docker run --env-file .env -p 8080:8080 preliquidador
```

O con Compose: `docker compose up` (ver `docker-compose.yml`). El contenedor expone
el puerto `8080` y corre como usuario no-root.

## Despliegue en Cloud Run

- La aplicación está dimensionada para ~2 GB de RAM / 1 vCPU. Los topes de
  preprocesamiento de Excel en `config.py` (`EXCEL_MAX_*`) están calibrados para ese
  perfil de memoria.
- Configurar todas las variables de entorno obligatorias en el panel de Variables y
  Secrets del servicio.

## Endpoints de salud y diagnóstico

| Endpoint                          | Para qué sirve                                          |
|-----------------------------------|--------------------------------------------------------|
| `GET /api/diagnostico`            | Diagnóstico completo (variables, módulos, config, conceptos cargados). Devuelve `estado_general: OK` si todo está bien. |
| `GET /api/database/health`        | Salud de la conexión a la base de datos.               |

## Logs de arranque

Al iniciar, el ciclo de vida (lifespan) registra en orden:
1. Carga de configuración.
2. Obtención del valor UVT desde la API (**obligatoria**: si falla, el arranque aborta).
3. Inicialización del gestor de base de datos (si falla, aborta).
4. Creación del publicador de webhook y del procesador en background.

## Dependencias externas y su impacto

| Dependencia        | Si falla...                                                            |
|--------------------|-----------------------------------------------------------------------|
| API de UVT         | El arranque aborta (el UVT es obligatorio para calcular).             |
| Nexura API (datos) | Es la única fuente de datos. Si no responde, la preliquidación afectada se reporta como `preliquidacion_sin_finalizar` (sugerido reintentar). No hay fallback activo. |
| Códigos de negocio | Si no hay datos frescos ni caché válido, la preliquidación se aborta y se reporta `preliquidacion_sin_finalizar` (con `retry_sugerido`). |
| Google Gemini      | El procesamiento de esa factura se reporta como `preliquidacion_sin_finalizar` (sugerido reintentar). |
| Webhook destino    | Se reintenta con backoff; si falla, el resultado queda guardado local en `Results/`. |

## Troubleshooting

- **El servicio no arranca y menciona `GEMINI_API_KEY`**: falta la variable en `.env`.
- **Arranca y aborta al obtener UVT**: la API de UVT no respondió; revisar conectividad.
- **El webhook no recibe nada**: `WEBHOOK_URL` no configurada (el resultado igual se
  guarda en `Results/AAAA-MM-DD/`).
- **Errores de autenticación Nexura por factura**: revisar
  `NEXURA_LOGIN_USER`/`NEXURA_LOGIN_PASSWORD`; la re-autenticación reintenta 3 veces.
- **Nexura no responde**: al ser la única fuente de datos, las facturas afectadas se
  reportan como `preliquidacion_sin_finalizar` (reintentar cuando se restablezca). El
  respaldo en Supabase existe en el código pero está desactivado; reactivarlo requiere
  descomentar el bloque de fallback en `database/setup.py` y configurar `SUPABASE_*`.
