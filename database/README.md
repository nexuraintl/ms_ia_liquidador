# 🗄️ Database Module - SOLID Architecture

> **Módulo de base de datos implementando principios SOLID y Clean Architecture para el Sistema Preliquidador**

## 🏗️ **Arquitectura en Capas**

```
📁 database/
├── 🔧 database.py           # Data Access Layer (Strategy Pattern)
├── 🏢 database_service.py   # Business Logic Layer (Service Pattern)
├── 📋 __init__.py          # Module exports and initialization
└── 📚 README.md            # Architecture documentation
```

## 🎯 **Principios SOLID Aplicados**

### ✅ **Single Responsibility Principle (SRP)**

#### `database.py` - Data Access Layer
- **Una responsabilidad**: Acceso a datos y conectividad
- **No mezcla**: Sin lógica de negocio ni validaciones
- **Enfoque**: Cómo conectar y consultar diferentes bases de datos

#### `database_service.py` - Business Logic Layer
- **Una responsabilidad**: Lógica de negocio para datos de negocio
- **No mezcla**: Sin detalles de conectividad específica
- **Enfoque**: Qué operaciones de negocio realizar

### ✅ **Open/Closed Principle (OCP)**

```python
# ✅ Abierto para extensión - Agregar nueva base de datos
class PostgreSQLDatabase(DatabaseInterface):
    def obtener_por_codigo(self, codigo: str) -> Dict[str, Any]:
        # Nueva implementación sin modificar código existente
        pass

# ✅ Abierto para extensión - Agregar nueva lógica de negocio
class AdvancedBusinessDataService(IBusinessDataService):
    def obtener_datos_negocio_completos(self, codigo: int) -> Dict[str, Any]:
        # Nueva funcionalidad sin modificar servicio existente
        pass
```

### ✅ **Liskov Substitution Principle (LSP)**

```python
# ✅ Cualquier implementación puede sustituir a la interfaz
def procesar_datos(service: IBusinessDataService):
    # Funciona con BusinessDataService, MockBusinessDataService, etc.
    result = service.obtener_datos_negocio(12345)
```

### ✅ **Interface Segregation Principle (ISP)**

```python
# ✅ Interfaces específicas para cada responsabilidad
class DatabaseInterface(ABC):        # Solo para acceso a datos
class IBusinessDataService(ABC):     # Solo para operaciones de negocio
```

### ✅ **Dependency Inversion Principle (DIP)**

```python
# ✅ Servicio depende de abstracción, no de implementación concreta
class BusinessDataService:
    def __init__(self, database_manager: DatabaseInterface):  # Abstracción
        self.database_manager = database_manager
```

## 🔄 **Patrones de Diseño Implementados**

### 🎯 **Strategy Pattern** (`database.py`)
```python
# Context
DatabaseManager(database_implementation)

# Strategies
SupabaseDatabase()      # Para Supabase
PostgreSQLDatabase()    # Para PostgreSQL (extensible)
MySQLDatabase()         # Para MySQL (extensible)
```

### 🏢 **Service Pattern** (`database_service.py`)
```python
# Service encapsula lógica de negocio
BusinessDataService.obtener_datos_negocio(codigo)
```

### 🏭 **Factory Pattern**
```python
# Factory para creación simplificada
BusinessDataServiceFactory.crear_servicio(db_manager)
crear_business_service(db_manager)  # Función de conveniencia
```

### 💉 **Dependency Injection**
```python
# Inyección en constructor
service = BusinessDataService(database_manager)  # DIP
```

## 📊 **Flujo de Datos**

```mermaid
graph TD
    A[main.py] -->|business_service.obtener_datos_negocio()| B[BusinessDataService]
    B -->|database_manager.obtener_negocio_por_codigo()| C[DatabaseManager]
    C -->|supabase_db.obtener_por_codigo()| D[SupabaseDatabase]
    D -->|SQL Query| E[(Supabase DB)]

    style A fill:#e1f5fe
    style B fill:#f3e5f5
    style C fill:#e8f5e8
    style D fill:#fff3e0
    style E fill:#fce4ec
```

## 🧪 **Testing Strategy**

### **Unit Tests - Business Logic**
```python
# Mock del data access layer
mock_db = Mock(spec=DatabaseManager)
service = BusinessDataService(mock_db)

# Test de lógica de negocio pura
result = service.obtener_datos_negocio(12345)
assert result["codigo_consultado"] == 12345
```

### **Integration Tests - Data Access**
```python
# Test de conectividad real
db = SupabaseDatabase(url, key)
manager = DatabaseManager(db)
result = manager.obtener_negocio_por_codigo("12345")
assert result["success"] == True
```

### **Mock Implementation**
```python
# Para testing sin base de datos
mock_service = MockBusinessDataService({
    12345: {"negocio": "Test Business", "nit": "123456789"}
})
```

## 🔧 **Uso del Módulo**

### **Importación Limpia**
```python
from database import (
    DatabaseManager,
    SupabaseDatabase,
    BusinessDataService,
    crear_business_service
)
```

### **Inicialización Completa**
```python
# Método 1: Manual
supabase_db = SupabaseDatabase(url, key)
db_manager = DatabaseManager(supabase_db)
business_service = BusinessDataService(db_manager)

# Método 2: Factory
business_service = crear_business_service(db_manager)

# Método 3: Stack completo
from database import crear_database_stack_completo
db_manager, business_service = crear_database_stack_completo()
```

### **Uso en Endpoint**
```python
# ANTES: Violación SRP
if db_manager:
    try:
        resultado = db_manager.obtener_negocio_por_codigo(str(codigo))
        if resultado['success']:
            # Lógica mezclada...

# DESPUÉS: SOLID compliant
resultado = business_service.obtener_datos_negocio(codigo_del_negocio)
datos_negocio = resultado.get('data') if resultado.get('success') else None
```

## 🚀 **Extensibilidad**

### **Agregar Nueva Base de Datos**
```python
# 1. Crear implementación
class MongoDB(DatabaseInterface):
    def obtener_por_codigo(self, codigo: str) -> Dict[str, Any]:
        # Implementación MongoDB
        pass

# 2. Usar sin cambios en business service
mongo_db = MongoDB(connection_string)
db_manager = DatabaseManager(mongo_db)
business_service = crear_business_service(db_manager)
```

### **Agregar Nueva Lógica de Negocio**
```python
# 1. Extender interface si es necesario
class IAdvancedBusinessService(IBusinessDataService):
    def obtener_datos_consolidados(self, codigo: int) -> Dict[str, Any]:
        pass

# 2. Implementar nueva funcionalidad
class AdvancedBusinessService(IAdvancedBusinessService):
    def obtener_datos_consolidados(self, codigo: int) -> Dict[str, Any]:
        # Nueva lógica sin afectar código existente
        pass
```

## 📋 **Beneficios de la Arquitectura**

### ✅ **Mantenibilidad**
- **Separación clara**: Cada capa tiene responsabilidades específicas
- **Bajo acoplamiento**: Cambios en una capa no afectan otras
- **Alta cohesión**: Componentes relacionados agrupados

### ✅ **Testabilidad**
- **Mocking fácil**: Interfaces permiten substituir implementaciones
- **Pruebas aisladas**: Cada capa se puede testear independientemente
- **TDD friendly**: Diseño facilita desarrollo dirigido por tests

### ✅ **Escalabilidad**
- **Extensión sin modificación**: OCP permite agregar funcionalidad
- **Migración de DB**: Strategy pattern facilita cambio de base de datos
- **Nuevos requisitos**: Service pattern permite agregar lógica de negocio

### ✅ **Flexibilidad**
- **Configuración dinámica**: Factory patterns para diferentes configuraciones
- **Inyección de dependencias**: Runtime dependency injection
- **Graceful degradation**: Sistema funciona aunque DB no esté disponible

## 🔍 **Debugging y Logging**

El módulo incluye logging comprehensivo:

```python
# Business service logs
logger.info("🔍 Consultando datos de negocio para código: {codigo}")
logger.info("✅ Negocio encontrado: {negocio} - NIT: {nit}")
logger.warning("⚠️ No se encontró negocio con código: {codigo}")
logger.error("❌ Error consultando base de datos: {error}")

# Database logs
logger.info("✅ DatabaseManager inicializado correctamente")
logger.warning("💥 Health check fallido: {error}")
```

## 📈 **Métricas y Monitoreo**

### **Health Checks**
```python
# Verificar disponibilidad
business_service.validar_disponibilidad_database()

# Health check endpoint
GET /api/database/health
```

### **Testing Endpoints**
```python
# Test de consulta específica
GET /api/database/test/{codigo_negocio}
```

## 🎯 **Siguiente Nivel: Microservicios**

Esta arquitectura está preparada para evolución a microservicios:

```yaml
# Futuro: database-service
version: '3.8'
services:
  database-service:
    build: ./database
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
    ports:
      - "3001:3001"
```

---

**🏗️ Arquitectura SOLID + Clean Architecture implementada correctamente**
**📚 Documentación actualizada según normativas del proyecto**
**🎯 Lista para escalamiento y evolución futura**