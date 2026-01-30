"""
BACKUP DE MAIN.PY - 2025-08-04
PROBLEMA: Endpoints duplicados /api/procesar-facturas
"""

import os
import json
import asyncio
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# FastAPI y dependencias web
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Configuración de logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===============================
# IMPORTAR MÓDULOS LOCALES
# ===============================

# Importar clases desde módulos
from Clasificador import ProcesadorGemini
from Liquidador import LiquidadorRetencion
from Extraccion import ProcesadorArchivos

# Cargar configuración global
from config import inicializar_configuracion, obtener_nits_disponibles, validar_nit_administrativo, nit_aplica_retencion_fuente

# BACKUP GUARDADO EXITOSAMENTE
