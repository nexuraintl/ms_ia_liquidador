"""
VISOR DE EXTRACCIONES GUARDADAS
==============================

Script utilitario para revisar y analizar los textos extraídos
automáticamente por el sistema.

Uso:
    python revisar_extracciones.py [fecha]
    
Ejemplos:
    python revisar_extracciones.py                    # Hoy
    python revisar_extracciones.py 2025-07-24         # Fecha específica
    python revisar_extracciones.py --todos            # Todas las fechas

Autor: Miguel Angel Jaramillo Durango
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

def obtener_carpeta_base() -> Path:
    """Obtiene la carpeta base de extracciones"""
    return Path("Results/Extracciones")

def listar_fechas_disponibles() -> List[str]:
    """Lista todas las fechas con extracciones disponibles"""
    carpeta_base = obtener_carpeta_base()
    if not carpeta_base.exists():
        return []
    
    fechas = []
    for item in carpeta_base.iterdir():
        if item.is_dir() and item.name.count('-') == 2:  # Formato YYYY-MM-DD
            fechas.append(item.name)
    
    return sorted(fechas, reverse=True)

def analizar_extracciones_fecha(fecha: str) -> Dict[str, Any]:
    """Analiza las extracciones de una fecha específica"""
    carpeta_fecha = obtener_carpeta_base() / fecha
    
    if not carpeta_fecha.exists():
        return {"error": f"No se encontraron extracciones para {fecha}"}
    
    archivos = list(carpeta_fecha.glob("*.txt"))
    
    analisis = {
        "fecha": fecha,
        "total_archivos": len(archivos),
        "extracciones": [],
        "estadisticas": {
            "tipos_extraccion": {},
            "tamaño_total_mb": 0,
            "caracteres_totales": 0,
            "errores": 0
        }
    }
    
    for archivo in archivos:
        try:
            # Leer contenido
            with open(archivo, 'r', encoding='utf-8') as f:
                contenido = f.read()
            
            # Extraer información del nombre del archivo
            partes = archivo.name.split("_")
            if len(partes) >= 3:
                timestamp = partes[0]
                metodo = partes[1]
                nombre_original = "_".join(partes[2:]).replace(".txt", "")
            else:
                timestamp = "unknown"
                metodo = "unknown"
                nombre_original = archivo.name
            
            # Extraer metadatos del contenido
            metadatos = {}
            if "METADATOS ADICIONALES:" in contenido:
                inicio_meta = contenido.find("METADATOS ADICIONALES:") + len("METADATOS ADICIONALES:")
                fin_meta = contenido.find("============================================", inicio_meta)
                if fin_meta > inicio_meta:
                    try:
                        texto_meta = contenido[inicio_meta:fin_meta].strip()
                        metadatos = json.loads(texto_meta)
                    except:
                        metadatos = {"error": "No se pudieron parsear metadatos"}
            
            # Extraer texto extraído
            texto_extraido = ""
            if "TEXTO EXTRAÍDO:" in contenido:
                inicio_texto = contenido.find("TEXTO EXTRAÍDO:") + len("TEXTO EXTRAÍDO:")
                inicio_texto = contenido.find("=", inicio_texto)
                inicio_texto = contenido.find("\n", inicio_texto) + 1
                
                fin_texto = contenido.find("============================================\nFIN DE LA EXTRACCIÓN")
                if fin_texto > inicio_texto:
                    texto_extraido = contenido[inicio_texto:fin_texto].strip()
            
            # Determinar si es error
            es_error = "ERROR" in metodo or "error" in contenido.lower()
            
            extraccion_info = {
                "archivo": archivo.name,
                "timestamp": timestamp,
                "metodo": metodo,
                "nombre_original": nombre_original,
                "tamaño_kb": round(archivo.stat().st_size / 1024, 2),
                "caracteres_extraidos": len(texto_extraido),
                "es_error": es_error,
                "metadatos": metadatos,
                "preview_texto": texto_extraido[:200] + "..." if len(texto_extraido) > 200 else texto_extraido
            }
            
            analisis["extracciones"].append(extraccion_info)
            
            # Actualizar estadísticas
            analisis["estadisticas"]["tipos_extraccion"][metodo] = analisis["estadisticas"]["tipos_extraccion"].get(metodo, 0) + 1
            analisis["estadisticas"]["tamaño_total_mb"] += archivo.stat().st_size / (1024 * 1024)
            analisis["estadisticas"]["caracteres_totales"] += len(texto_extraido)
            
            if es_error:
                analisis["estadisticas"]["errores"] += 1
                
        except Exception as e:
            print(f"⚠️ Error procesando {archivo.name}: {e}")
    
    analisis["estadisticas"]["tamaño_total_mb"] = round(analisis["estadisticas"]["tamaño_total_mb"], 2)
    
    return analisis

def mostrar_resumen_fecha(fecha: str):
    """Muestra un resumen de las extracciones de una fecha"""
    print(f"\n📊 RESUMEN DE EXTRACCIONES - {fecha}")
    print("=" * 60)
    
    analisis = analizar_extracciones_fecha(fecha)
    
    if "error" in analisis:
        print(f"❌ {analisis['error']}")
        return
    
    stats = analisis["estadisticas"]
    
    print(f"📁 Total de archivos: {analisis['total_archivos']}")
    print(f"💾 Tamaño total: {stats['tamaño_total_mb']} MB")
    print(f"📝 Caracteres extraídos: {stats['caracteres_totales']:,}")
    print(f"❌ Errores: {stats['errores']}")
    
    print(f"\n📋 Tipos de extracción:")
    for tipo, cantidad in stats["tipos_extraccion"].items():
        emoji = "❌" if "ERROR" in tipo else "✅"
        print(f"  {emoji} {tipo}: {cantidad}")
    
    if analisis["extracciones"]:
        print(f"\n📄 ARCHIVOS PROCESADOS:")
        print("-" * 60)
        
        for ext in sorted(analisis["extracciones"], key=lambda x: x["timestamp"]):
            status = "❌" if ext["es_error"] else "✅"
            print(f"{status} {ext['timestamp']} | {ext['metodo']:12} | {ext['nombre_original']}")
            print(f"   📊 {ext['caracteres_extraidos']:,} chars, {ext['tamaño_kb']} KB")
            
            if not ext["es_error"] and ext["preview_texto"]:
                preview = ext["preview_texto"].replace('\n', ' ')[:100]
                print(f"   👁️ \"{preview}\"")
            
            print()

def mostrar_detalle_archivo(fecha: str, nombre_archivo: str):
    """Muestra el detalle completo de un archivo específico"""
    carpeta_fecha = obtener_carpeta_base() / fecha
    archivo_path = carpeta_fecha / nombre_archivo
    
    if not archivo_path.exists():
        print(f"❌ Archivo no encontrado: {nombre_archivo}")
        return
    
    print(f"\n📄 CONTENIDO COMPLETO - {nombre_archivo}")
    print("=" * 80)
    
    try:
        with open(archivo_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        print(contenido)
        
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")

def main():
    """Función principal"""
    print("🔍 VISOR DE EXTRACCIONES - Preliquidador v2.0")
    print("=" * 50)
    
    # Verificar carpeta base
    carpeta_base = obtener_carpeta_base()
    if not carpeta_base.exists():
        print(f"❌ No se encontró la carpeta de extracciones: {carpeta_base}")
        print("   Ejecuta el sistema primero para generar extracciones.")
        return
    
    # Obtener fechas disponibles
    fechas_disponibles = listar_fechas_disponibles()
    
    if not fechas_disponibles:
        print("📭 No se encontraron extracciones guardadas.")
        return
    
    print(f"📅 Fechas con extracciones disponibles: {', '.join(fechas_disponibles)}")
    
    # Procesar argumentos
    if len(sys.argv) > 1:
        if sys.argv[1] == "--todos":
            # Mostrar todas las fechas
            for fecha in fechas_disponibles:
                mostrar_resumen_fecha(fecha)
        elif sys.argv[1] in fechas_disponibles:
            # Mostrar fecha específica
            mostrar_resumen_fecha(sys.argv[1])
            
            # Si hay un tercer argumento, mostrar archivo específico
            if len(sys.argv) > 2:
                mostrar_detalle_archivo(sys.argv[1], sys.argv[2])
        else:
            print(f"❌ Fecha no encontrada: {sys.argv[1]}")
            print(f"   Fechas disponibles: {', '.join(fechas_disponibles)}")
    else:
        # Mostrar fecha de hoy por defecto
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        if fecha_hoy in fechas_disponibles:
            mostrar_resumen_fecha(fecha_hoy)
        else:
            print(f"📭 No hay extracciones para hoy ({fecha_hoy})")
            if fechas_disponibles:
                print(f"   Última fecha con extracciones: {fechas_disponibles[0]}")
                mostrar_resumen_fecha(fechas_disponibles[0])
    
    print(f"\n💡 USO:")
    print(f"   python revisar_extracciones.py                    # Hoy")
    print(f"   python revisar_extracciones.py 2025-07-24         # Fecha específica")
    print(f"   python revisar_extracciones.py 2025-07-24 archivo.txt  # Archivo específico")
    print(f"   python revisar_extracciones.py --todos            # Todas las fechas")

if __name__ == "__main__":
    main()
