# 🔧 Tools - Herramientas de Desarrollo

Esta carpeta contiene scripts utilitarios y herramientas de desarrollo para el Preliquidador.

## 📁 Contenido

### 📊 `revisar_extracciones.py`
**Propósito:** Script para revisar y analizar los textos extraídos automáticamente por el sistema.

**Uso:**
```bash
cd tools
python revisar_extracciones.py                    # Revisar extracciones de hoy
python revisar_extracciones.py 2025-08-09         # Fecha específica
python revisar_extracciones.py --todos            # Todas las fechas
```

**Funcionalidades:**
- Lista fechas con extracciones disponibles
- Analiza estadísticas de extracciones por fecha
- Muestra metadatos de archivos procesados
- Útil para debugging y auditoría

### ⚙️ `instalar_dependencias.py`
**Propósito:** Script para instalar dependencias necesarias para OCR y conversión PDF.

**Uso:**
```bash
cd tools
python instalar_dependencias.py
```

**Funcionalidades:**
- Instala `pdf2image` para conversión PDF → Imagen
- Instala `PyMuPDF` como alternativa de conversión
- Verifica dependencias existentes
- Manejo robusto de errores de instalación

## 🛠️ Desarrollo

### Agregar nuevas herramientas
Para agregar nuevos scripts utilitarios:

1. Crear el script en esta carpeta
2. Documentar su propósito y uso en este README
3. Seguir las convenciones de naming: `verbo_sustantivo.py`
4. Incluir docstrings detallados
5. Manejar errores apropiadamente

### Convenciones
- **Prefijo:** Usar verbos descriptivos (`revisar_`, `instalar_`, `procesar_`)
- **Logging:** Usar emoji para claridad visual (🔄 ✅ ❌)
- **Argumentos:** Soportar help con `--help` cuando aplique
- **Errores:** Exit codes apropiados (0=éxito, 1=error)

## 📋 Roadmap de Herramientas

### Próximas herramientas planeadas:
- [ ] `validar_conceptos.py` - Validar archivo RETEFUENTE_CONCEPTOS.xlsx
- [ ] `limpiar_resultados.py` - Limpiar carpeta Results/ antigua
- [ ] `backup_sistema.py` - Crear backup completo del sistema
- [ ] `test_integracion.py` - Tests de integración completos
- [ ] `monitorear_performance.py` - Monitor de performance y métricas

---

**Nota:** Estos scripts son para desarrollo y administración. No forman parte del flujo principal del Preliquidador.
