# DEPLOYMENT - Sistema de Fallback Nexura → Supabase v3.11.0

## Configuracion para Cloud Run (GCP)

### Variables de entorno requeridas

Asegurate de tener configuradas estas variables de entorno en Cloud Run:

```bash
# === Database Configuration ===
DATABASE_TYPE=nexura

# === Nexura API (Primaria) ===
NEXURA_API_BASE_URL=https://preproduccion-fiducoldex.nexura.com/api
NEXURA_AUTH_TYPE=none
NEXURA_API_TIMEOUT=5

# === Supabase (Fallback) - OBLIGATORIAS ===
SUPABASE_URL=https://gfcseujjfnaoicdenymt.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmY3NldWpqZm5hb2ljZGVueW10Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTEwMzA4MDgsImV4cCI6MjA2NjYwNjgwOH0.ghHQ-wDB7itkoEEKq04iOCmLUyrL1hLSjLXhq1gN62k
```

### Como funciona el fallback

1. **Sistema intenta Nexura primero** (timeout 5 segundos)
2. **Si Nexura falla** → Automáticamente usa Supabase
3. **Logs WARNING** cuando se activa el fallback
4. **Sin intervención manual** requerida

### Que hacer si Nexura esta caida

**NO HACER NADA** - El sistema automáticamente:
- Detecta que Nexura no responde (5 segundos)
- Cambia a Supabase sin interrumpir el servicio
- Loguea WARNING para monitoreo
- Continúa operando normalmente

### Monitoreo en Cloud Run Logs

#### Funcionamiento normal (Nexura OK):
```
[INFO] DatabaseWithFallback inicializado: NexuraAPIDatabase -> SupabaseDatabase
[DEBUG] obtener_por_codigo exitoso con NexuraAPIDatabase
```

#### Fallback activado (Nexura caída):
```
[WARNING] FALLBACK ACTIVADO: NexuraAPIDatabase falló en obtener_por_codigo
[INFO] obtener_por_codigo completado exitosamente usando SupabaseDatabase (FALLBACK)
```

#### Error crítico (ambas caídas):
```
[ERROR] ERROR CRÍTICO: Tanto NexuraAPIDatabase como SupabaseDatabase fallaron
```

### Deployment a Cloud Run

1. **Commit y push** de los cambios:
```bash
git add .
git commit -m "feat: Sistema de fallback automático Nexura -> Supabase v3.11.0"
git push origin feature
```

2. **Cloud Run detectará el push** y hará deploy automático

3. **Verificar variables de entorno** en Cloud Run:
   - Ir a Cloud Run console
   - Seleccionar el servicio
   - Tab "Variables y Secrets"
   - Verificar que SUPABASE_URL y SUPABASE_KEY estén configuradas

4. **Verificar logs** después del deploy:
```
[INFO] ✅ Sistema de fallback Nexura -> Supabase configurado correctamente
```

### Testing local antes de deploy

```bash
# 1. Configurar variables de entorno locales
cp .env.example .env
# Editar .env con las variables arriba

# 2. Probar fallback (simular Nexura caída)
# Cambiar temporalmente en .env:
NEXURA_API_BASE_URL=https://invalid-url-for-testing.com

# 3. Ejecutar servicio
python main.py

# 4. Hacer request y verificar logs
# Deberías ver WARNING de fallback y respuesta exitosa desde Supabase
```

### Troubleshooting

#### Problema: Sistema falla y no usa fallback
**Causa**: Variables SUPABASE_URL o SUPABASE_KEY no configuradas en Cloud Run

**Solución**:
1. Ir a Cloud Run console
2. Editar servicio
3. Variables y Secrets → Agregar:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
4. Deploy nueva revisión

#### Problema: Logs no muestran WARNING cuando Nexura falla
**Causa**: Nivel de logging configurado como ERROR

**Solución**: Configurar `LOG_LEVEL=INFO` en variables de entorno

#### Problema: Timeout muy largo antes de fallback
**Causa**: `NEXURA_API_TIMEOUT` no configurado

**Solución**: Configurar `NEXURA_API_TIMEOUT=5` en Cloud Run

### Verificación post-deployment

1. **Check de health** del servicio
2. **Revisar logs** para mensaje de inicialización exitosa
3. **Hacer request de prueba** y verificar respuesta
4. **Verificar métricas** en Cloud Run (latencia, errores)

### Contacto

Si tienes problemas con el deployment, verifica:
- ✅ Variables de entorno correctamente configuradas
- ✅ Logs de Cloud Run para mensajes de error
- ✅ Version v3.11.0 deployada correctamente
- ✅ Código en rama `feature` pusheado

---

**Version**: 3.11.0
**Fecha**: 2025-12-03
**Feature**: Sistema de Fallback Automático Nexura → Supabase
