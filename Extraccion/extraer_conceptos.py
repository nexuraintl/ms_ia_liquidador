"""
Script para extraer conceptos del archivo Excel RETEFUENTE_CONCEPTOS.xlsx
y generar la lista para el sistema principal.
"""

import pandas as pd
import json
from pathlib import Path

def extraer_conceptos_excel():
    """Extrae los conceptos del archivo Excel"""
    
    archivo_excel = Path("C:/Users/USUSARIO/Proyectos/PRELIQUIDADOR/RETEFUENTE_CONCEPTOS.xlsx")
    
    if not archivo_excel.exists():
        print(f"❌ No se encontró el archivo: {archivo_excel}")
        return None
    
    try:
        # Leer el archivo Excel
        df = pd.read_excel(archivo_excel)
        
        print(f"✅ Archivo Excel leído exitosamente")
        print(f"📊 Columnas: {list(df.columns)}")
        print(f"📋 Número de filas: {len(df)}")
        print(f"🔍 Primeras 5 filas:")
        print(df.head())
        
        # Extraer conceptos (asumiendo que están en la primera columna)
        columna_conceptos = df.columns[0]  # Primera columna
        conceptos = df[columna_conceptos].dropna().tolist()
        
        print(f"\n📝 Conceptos extraídos ({len(conceptos)}):")
        for i, concepto in enumerate(conceptos, 1):
            print(f"{i:2d}. {concepto}")
        
        # Guardar en archivo JSON
        archivo_json = "conceptos_extraidos.json"
        with open(archivo_json, 'w', encoding='utf-8') as f:
            json.dump({
                "conceptos": conceptos,
                "total": len(conceptos),
                "archivo_origen": str(archivo_excel),
                "columnas_excel": list(df.columns)
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Conceptos guardados en: {archivo_json}")
        
        # Generar código Python para usar en main.py
        codigo_python = "CONCEPTOS_RETEFUENTE = [\n"
        for concepto in conceptos:
            codigo_python += f'    "{concepto}",\n'
        codigo_python += "]"
        
        with open("conceptos_codigo.txt", 'w', encoding='utf-8') as f:
            f.write(codigo_python)
        
        print(f"🐍 Código Python generado en: conceptos_codigo.txt")
        
        return conceptos
        
    except Exception as e:
        print(f"❌ Error procesando Excel: {e}")
        return None

if __name__ == "__main__":
    print("🚀 Extrayendo conceptos de RETEFUENTE_CONCEPTOS.xlsx...")
    conceptos = extraer_conceptos_excel()
    
    if conceptos:
        print(f"\n✅ Proceso completado. {len(conceptos)} conceptos extraídos.")
    else:
        print("\n❌ No se pudieron extraer los conceptos.")
