# 🚀 Preliquidador de Impuestos Colombianos

**Sistema automatizado de liquidación tributaria con Inteligencia Artificial y Arquitectura Profesional.**

> Versión: **3.19.8** · Documentación completa en [`docs/`](docs/README.md)

API REST desarrollada con **FastAPI** que utiliza **Google Gemini AI** para procesar facturas y documentos de soporte, calculando automáticamente múltiples impuestos colombianos (Retención en la Fuente, IVA, ICA, Estampillas, etc.). El proyecto está construido rigurosamente bajo los principios **SOLID** y **Clean Architecture**.

## 📑 Características Principales

- **Inteligencia Artificial (Híbrida)**: Integración con Google Gemini AI (SDK `google-genai` v1.12.1) para la extracción y clasificación precisa de información. Utiliza multimodalidad mediante Google Files API para procesar archivos pesados (PDFs, Imágenes) de manera eficiente.
- **Cálculo Determinista**: Algoritmos deterministas en Python para validaciones normativas y cálculos tributarios exactos basados en la información extraída.
- **Arquitectura Robusta**:
  - Implementación estricta de principios **SOLID**.
  - **Clean Architecture**: Separación clara entre capas (Dominio, Aplicación, Infraestructura).
  - Patrones de diseño aplicados: *Factory*, *Strategy*, *Template Method* y *Facade*.
- **Concurrencia y Rendimiento**: Procesamiento paralelo de facturas con `asyncio` y tareas asíncronas en segundo plano.

## 💰 Impuestos Soportados

El sistema liquida y valida normativamente los siguientes impuestos:

1. **Retención en la Fuente**: Nacional (43 conceptos) y Pagos al Exterior (8 conceptos con convenios internacionales).
2. **IVA y ReteIVA**.
3. **ICA (Industria y Comercio)**: Soporte para múltiples actividades económicas, tarifas y ubicaciones geográficas.
4. **Estampillas**: Universidad Nacional y 6 Estampillas Generales (Procultura, Adulto Mayor, etc.).
5. **Contribución Obra Pública**.
6. **Tasa Prodeporte**: Incluye validaciones presupuestales complejas.

## 🛠️ Stack Tecnológico

- **Backend**: Python 3.11, FastAPI, Pydantic.
- **Inteligencia Artificial**: Google Gemini AI (`google-genai`).
- **Fuente de Verdad de Datos**: API de Nexura (única fuente activa). El código conserva un respaldo en Supabase usado durante el desarrollo, hoy desactivado.
- **Procesamiento Asíncrono**: `asyncio`, tareas en background y Webhooks.

## 📁 Estructura del Proyecto

La arquitectura se divide estratégicamente en responsabilidades únicas:

- `app/`: Lógica de orquestación, manejo de concurrencia y endpoints principales.
- `Background/`: Procesamiento asíncrono y Webhooks de resultados.
- `Clasificador/`: Integración con Gemini AI y módulos clasificadores especializados por impuesto.
- `Liquidador/`: Lógica de negocio tributaria, calculadoras deterministas y validadores normativos.
- `database/`: Capa de acceso a datos vía API de Nexura.
- `modelos/`: Definiciones Pydantic para validación de datos (I/O).
- `Conversor/`: Servicios financieros externos (ej. conversor TRM COP/USD).

## ⚙️ Requisitos Previos

- Python 3.11.
- `poppler-utils` (dependencia de las librerías de manejo de PDF; incluida en la imagen Docker).
- Claves y Credenciales:
  - Google Gemini API Key.
  - Credenciales de la API de Nexura.

## 🚀 Instalación y Configuración

1. **Clonar el repositorio:**
   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd PRELIQUIDADOR
   ```

2. **Crear y activar un entorno virtual:**
   ```bash
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux/Mac:
   source venv/bin/activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno:**
   Crea un archivo `.env` en la raíz del proyecto. El detalle completo de cada
   variable está en [`docs/02_DESPLIEGUE_OPERACION.md`](docs/02_DESPLIEGUE_OPERACION.md).
   ```env
   # Obligatorias
   GEMINI_API_KEY=tu_api_key_de_gemini
   NEXURA_API_BASE_URL=tu_nexura_url
   NEXURA_LOGIN_USER=tu_usuario_nexura
   NEXURA_LOGIN_PASSWORD=tu_password_nexura

   # Opcionales (con valor por defecto)
   NEXURA_API_TIMEOUT=30
   WEBHOOK_URL=url_destino_del_resultado
   WEBHOOK_AUTH_TYPE=bearer
   WEBHOOK_AUTH_TOKEN=token_del_webhook
   ```
   > La fuente de datos es la API de Nexura. `SUPABASE_URL`/`SUPABASE_KEY` solo se
   > necesitan si se reactiva el respaldo en Supabase (hoy desactivado).

## 💻 Uso y Ejecución

Para iniciar el servidor local de desarrollo, ejecuta:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

Una vez que el servidor esté corriendo, puedes acceder a la documentación interactiva de la API en:
- **Swagger UI**: [http://localhost:8080/docs](http://localhost:8080/docs)
- **ReDoc**: [http://localhost:8080/redoc](http://localhost:8080/redoc)

## 🧪 Pruebas

El sistema cuenta con una suite de pruebas para validar las reglas de negocio.
Ejecútalas con el entorno virtual del proyecto (con el Python global falla la
dependencia `python-calamine`):
```bash
.\venv\Scripts\pytest tests/    # Windows
./venv/bin/pytest tests/        # Linux/Mac
```
Estado actual: 760 aprobados, 18 omitidos (integraciones externas), 0 fallos.
Detalle en [`docs/04_PRUEBAS.md`](docs/04_PRUEBAS.md).
