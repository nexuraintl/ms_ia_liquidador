"""
Configuracion de pytest para tests del Preliquidador.

Este archivo se ejecuta automaticamente antes de todos los tests
y configura el entorno necesario.
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raiz al PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Cargar variables de entorno desde .env
from dotenv import load_dotenv

env_path = root_dir / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"Variables de entorno cargadas desde: {env_path}")
    print(f"   DATABASE_TYPE: {os.getenv('DATABASE_TYPE')}")
    print(f"   NEXURA_API_BASE_URL: {os.getenv('NEXURA_API_BASE_URL')}")
else:
    print(f"Archivo .env no encontrado en: {env_path}")
