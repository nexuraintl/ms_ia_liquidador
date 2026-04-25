# 🚀 Preliquidador de Impuestos Colombianos

**Sistema automatizado de liquidación tributaria con Inteligencia Artificial y Arquitectura Profesional.**

API REST desarrollada con **FastAPI** que utiliza **Google Gemini AI** para procesar facturas y documentos de soporte, calculando automáticamente múltiples impuestos colombianos (Retención en la Fuente, IVA, ICA, Estampillas, etc.). El proyecto está construido rigurosamente bajo los principios **SOLID** y **Clean Architecture**.

## 📑 Características Principales

- **Inteligencia Artificial (Híbrida)**: Integración con Google Gemini AI (SDK `google-genai` v0.2.0+) para la extracción y clasificación precisa de información. Utiliza multimodalidad mediante Google Files API para procesar archivos pesados (PDFs, Imágenes) de manera eficiente.
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

- **Backend**: Python 3.9+, FastAPI, Pydantic.
- **Inteligencia Artificial**: Google Gemini AI (`google-genai`).
- **Base de Datos / Fuentes de Verdad**: Estrategia híbrida con Nexura API (Primaria) y Supabase (Respaldo).
- **Procesamiento Asíncrono**: `asyncio`, tareas en background y Webhooks.

## 📁 Estructura del Proyecto

La arquitectura se divide estratégicamente en responsabilidades únicas:

- `app/`: Lógica de orquestación, manejo de concurrencia y endpoints principales.
- `Background/`: Procesamiento asíncrono y Webhooks de resultados.
- `Clasificador/`: Integración con Gemini AI y módulos clasificadores especializados por impuesto.
- `Liquidador/`: Lógica de negocio tributaria, calculadoras deterministas y validadores normativos.
- `database/`: Capa de acceso a datos dinámica (Nexura API / Supabase).
- `modelos/`: Definiciones Pydantic para validación de datos (I/O).
- `Conversor/`: Servicios financieros externos (ej. conversor TRM COP/USD).

## ⚙️ Requisitos Previos

- Python 3.9 o superior.
- Claves y Credenciales:
  - Google Gemini API Key.
  - Supabase URL y Key.
  - Credenciales de Nexura API.

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
   Crea un archivo `.env` en la raíz del proyecto basándote en la configuración de `config.py`.
   ```env
   GEMINI_API_KEY=tu_api_key_de_gemini
   SUPABASE_URL=tu_supabase_url
   SUPABASE_KEY=tu_supabase_key
   NEXURA_API_URL=tu_nexura_url
   NEXURA_JWT_TOKEN=tu_token_jwt
   ```

## 💻 Uso y Ejecución

Para iniciar el servidor local de desarrollo, ejecuta:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Una vez que el servidor esté corriendo, puedes acceder a la documentación interactiva de la API en:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## 🧪 Pruebas

El sistema cuenta con una suite de pruebas para validar las reglas de negocio. Para ejecutarlas:
```bash
pytest
```
