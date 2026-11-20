"""src/supervisor/orquestador.py
Agente Supervisor y herramientas LangChain (@tool).
Coordina la detección de intención y enruta la tarea al agente especializado correspondiente.
"""
from langchain.tools import tool
from src.supervisor.clasificador_intencion import ClasificadorIntencion
from src.agentes import AgenteClasificador, AgenteReportes, AgenteOrganizador

# Instancias singleton de agentes y clasificador
clasificador_intencion = ClasificadorIntencion()
agente_clasificador = AgenteClasificador()
agente_reportes = AgenteReportes()
agente_organizador = AgenteOrganizador()


# =========================================================
# REGISTRO DE AGENTES COMO HERRAMIENTAS DE LANGCHAIN
# =========================================================
@tool
def tool_clasificar_correo(contenido: str) -> str:
    """Clasifica un correo electrónico en facturación, soporte, comercial u otro.
    Input: el contenido del correo como string."""
    return agente_clasificador.ejecutar(contenido)


@tool
def tool_generar_reporte(rutas_archivos: str) -> str:
    """Genera un reporte consolidado a partir de archivos Excel.
    Input: lista de rutas de archivos separadas por coma."""
    return agente_reportes.ejecutar(rutas_archivos)


@tool
def tool_organizar_documento(ruta_pdf: str) -> str:
    """Organiza, renombra y mueve un documento PDF.
    Input: ruta del archivo PDF."""
    return agente_organizador.ejecutar(ruta_pdf)


# =========================================================
# SUPERVISOR (orquestador con LangChain)
# =========================================================
def supervisor(texto_usuario: str, datos_adicionales: dict) -> str:
    # 1. Clasificar la intención del usuario
    intencion = clasificador_intencion.predecir(texto_usuario)

    # Mapeo de intenciones a nombres y agentes
    info_intenciones = {
        0: {"nombre": "clasificar_correo", "agente": "Agente 1 (Clasificador de Correos - BERT tiny fine-tuned)"},
        1: {"nombre": "generar_reporte", "agente": "Agente 2 (Generador de Reportes y Análisis - Pandas)"},
        2: {"nombre": "organizar_documento", "agente": "Agente 3 (Organizador y Resumidor de PDFs - PyPDF)"}
    }

    info = info_intenciones.get(intencion, {"nombre": "desconocida", "agente": "Ninguno"})
    print(f"\n[Supervisor] Intención detectada: {info['nombre']}")
    print(f"[Supervisor] Tarea asignada a: {info['agente']}\n")

    # 2. Ejecutar la herramienta correspondiente
    if intencion == 0:
        contenido = datos_adicionales.get("contenido", "")
        return tool_clasificar_correo.invoke({"contenido": contenido})
    elif intencion == 1:
        archivos = datos_adicionales.get("archivos", "")
        return tool_generar_reporte.invoke({"rutas_archivos": archivos})
    elif intencion == 2:
        ruta = datos_adicionales.get("ruta_pdf", "")
        return tool_organizar_documento.invoke({"ruta_pdf": ruta})
    else:
        return "La solicitud no es clara. Por favor, sea más específico."
