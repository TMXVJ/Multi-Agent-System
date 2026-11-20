"""src/config.py
Configuración global y variables de entorno del sistema multiagente.
"""
import os
import sys
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

# Asegurar codificación UTF-8 en consolas Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Credenciales y rutas
HF_TOKEN = os.getenv("HF_TOKEN", "")
RUTA_MODELO_CORREOS = os.getenv("RUTA_MODELO_CORREOS", "modelos/bert_tiny_correos")
UMBRAL_CONFIANZA = float(os.getenv("UMBRAL_CONFIANZA", "0.50"))

EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", os.getenv("GMAIL_PSW", ""))

# Rutas de salida predeterminadas
DIR_SALIDAS = "salidas"
DIR_ORGANIZADOS = os.path.join(DIR_SALIDAS, "organizados")
DIR_RESUMENES_PDF = os.path.join(DIR_SALIDAS, "resumenes_pdf")
RUTA_REPORTE_CONSOLIDADO = os.path.join(DIR_SALIDAS, "reporte_consolidado.xlsx")
