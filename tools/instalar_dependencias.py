"""
INSTALADOR DE DEPENDENCIAS - PRELIQUIDADOR v2.0
==============================================

Script para instalar las nuevas dependencias necesarias para 
la conversión PDF → Imagen → OCR.

Ejecutar: python instalar_dependencias.py
"""

import subprocess
import sys
import os
from pathlib import Path

def ejecutar_comando(comando):
    """Ejecuta un comando y muestra el resultado"""
    print(f"Ejecutando: {comando}")
    try:
        resultado = subprocess.run(
            comando, 
            shell=True, 
            check=True, 
            capture_output=True, 
            text=True
        )
        print(f"Comando exitoso")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print(f"   Salida: {e.stdout}")
        print(f"   Error: {e.stderr}")
        return False

def verificar_dependencia(nombre_modulo, nombre_mostrar=None):
    """Verifica si una dependencia está instalada"""
    if not nombre_mostrar:
        nombre_mostrar = nombre_modulo
    
    try:
        __import__(nombre_modulo)
        print(f"{nombre_mostrar} ya está instalado")
        return True
    except ImportError:
        print(f"{nombre_mostrar} no está instalado")
        return False

def main():
    """Función principal de instalación"""
    print("INSTALADOR DE DEPENDENCIAS - PRELIQUIDADOR v2.0")
    print("=" * 50)
    
    # Verificar si estamos en el directorio correcto
    if not Path("requirements.txt").exists():
        print("No se encontró requirements.txt")
        print("   Ejecuta este script desde la carpeta del proyecto")
        return
    
    print("Verificando dependencias actuales...")
    
    # Verificar dependencias principales
    dependencias_principales = [
        ("fastapi", "FastAPI"),
        ("PyPDF2", "PyPDF2"),
        ("pandas", "Pandas"),
        ("google.generativeai", "Google Generative AI"),
        ("google.cloud.vision", "Google Cloud Vision")
    ]
    
    for modulo, nombre in dependencias_principales:
        verificar_dependencia(modulo, nombre)
    
    print("\nVerificando nuevas dependencias v2.0...")
    
    # Verificar nuevas dependencias
    nuevas_dependencias = [
        ("pdf2image", "pdf2image"),
        ("fitz", "PyMuPDF")
    ]
    
    dependencias_faltantes = []
    for modulo, nombre in nuevas_dependencias:
        if not verificar_dependencia(modulo, nombre):
            dependencias_faltantes.append(nombre)
    
    if dependencias_faltantes:
        print(f"\nInstalando dependencias faltantes: {', '.join(dependencias_faltantes)}")
        
        # Instalar desde requirements.txt
        print("\nInstalando todas las dependencias desde requirements.txt...")
        if ejecutar_comando(f"{sys.executable} -m pip install -r requirements.txt"):
            print("\nInstalación completada exitosamente")
        else:
            print("\nError en la instalación")
            return
    else:
        print("\nTodas las dependencias están instaladas")
    
    print("\n🧪 Verificando instalación...")
    
    # Verificar que todo funcione
    try:
        print("   Probando pdf2image...")
        import pdf2image
        print("   pdf2image funcional")
    except Exception as e:
        print(f"   Error con pdf2image: {e}")
    
    try:
        print("   Probando PyMuPDF...")
        import fitz
        print("   PyMuPDF funcional")
    except Exception as e:
        print(f"   Error con PyMuPDF: {e}")
    
    print("\nNOTAS IMPORTANTES:")
    print("=" * 30)
    print("1. Si pdf2image falla en Linux/Mac, instala poppler-utils:")
    print("   - Ubuntu/Debian: sudo apt-get install poppler-utils")
    print("   - macOS: brew install poppler")
    print("   - Windows: Incluido automáticamente")
    print("")
    print("2. 🌐 Asegúrate de tener configurado Google Cloud Vision:")
    print("   - Variable GOOGLE_APPLICATION_CREDENTIALS en .env")
    print("   - Archivo JSON de credenciales válido")
    print("")
    print("3. Reinicia el servidor después de la instalación:")
    print("   - Ctrl+C para detener")
    print("   - python main.py para reiniciar")
    print("")
    print("4. 🧪 Prueba con un PDF que tenga poco texto para verificar OCR")
    
    print("\n¡INSTALACIÓN COMPLETADA!")
    print("   El sistema ahora puede convertir PDF → Imagen → OCR")

if __name__ == "__main__":
    main()
