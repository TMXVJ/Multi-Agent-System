"""src/agentes/agente_organizador.py
Agente 3: Organizador de Documentos (con Resumen de PDF)
"""
import os
import re
import time
import shutil
from collections import Counter
import pypdf
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


class AgenteOrganizador:
    def _clasificar_tipo_documento(self, texto: str) -> tuple[str, str]:
        """Detecta con precisión la categoría documental empresarial utilizando límites de palabra completos."""
        t_low = texto.lower()
        
        # Palabras clave exactas con límites de palabra \b para evitar falsos positivos (ej: 'iva' en 'repetitiva')
        criterios = {
            "Certificados_y_Afiliaciones": [
                r'\bcertificado\b', r'\bconstancia\b', r'\bafiliaci[oó]n\b', r'\bafiliad[ao]s?\b', 
                r'\brisk\b', r'\briesgos laborales\b', r'\barl\b', r'\beps\b', r'\bcesant[ií]as\b',
                r'\bcobertura\b', r'\bhace constar\b', r'\bcotizante\b'
            ],
            "Articulos_e_Informes": [
                r'\bart[ií]culo\b', r'\bresumen\b', r'\babstract\b', r'\bmetodolog[ií]a\b', 
                r'\bconclusiones\b', r'\binvestigaci[oó]n\b', r'\breferencias\b', r'\bautores\b',
                r'\bframework\b', r'\bproceso\b', r'\bdesarrollo de un sistema\b', r'\bkeywords\b'
            ],
            "Facturas": [
                r'\bfactura\b', r'\bcuenta de cobro\b', r'\biva\b', r'\bvalor a pagar\b', 
                r'\bnit\b', r'\btotal a pagar\b', r'\bretenci[oó]n\b', r'\brecibo de caja\b', 
                r'\bfactura electr[oó]nica\b'
            ],
            "Contratos": [
                r'\bcontrato\b', r'\bcl[aá]usula\b', r'\bcomparecen\b', r'\bacuerdo\b', 
                r'\bprestaci[oó]n de servicios\b', r'\barrendamiento\b', r'\bvigencia del contrato\b', 
                r'\blas partes\b'
            ],
            "Recursos_Humanos": [
                r'\bcertificado laboral\b', r'\bhoja de vida\b', r'\bn[oó]mina\b', r'\bsalario\b', 
                r'\bempleado\b', r'\bliqidaci[oó]n\b', r'\bcontrataci[oó]n\b'
            ]
        }
        
        puntuaciones = {}
        for cat, patrones in criterios.items():
            total_matches = 0
            for p in patrones:
                total_matches += len(re.findall(p, t_low))
            puntuaciones[cat] = total_matches
            
        cat_max = max(puntuaciones, key=puntuaciones.get)
        if puntuaciones[cat_max] >= 2:
            prefijos = {
                "Certificados_y_Afiliaciones": "Certificado",
                "Articulos_e_Informes": "Articulo",
                "Facturas": "Factura",
                "Contratos": "Contrato",
                "Recursos_Humanos": "RRHH"
            }
            return cat_max, prefijos.get(cat_max, "Doc")
        return "General", "Doc"

    def _detectar_titulo_y_tema(self, texto_bruto: str, lineas: list[str]) -> str:
        """Extrae el título real y concreto del documento sin mezclarlo con fechas o ciudades."""
        t_clean = texto_bruto.replace("\x00", " ")
        t_mayus = t_clean.upper()
        
        # 1. Si es un certificado o constancia
        if "HACE CONSTAR" in t_mayus or "CERTIFICADO" in t_mayus or "AFILIAD" in t_mayus:
            # Buscar entidad emisora
            entidad = "ARL SURA" if "SURA" in t_mayus else ("UNIVERSIDAD LIBRE" if "UNIVERSIDAD LIBRE" in t_mayus else "")
            
            # Buscar persona o asunto
            match_persona = re.search(r'C\d{6,12}\s+([A-ZÁÉÍÓÚÑ\s]{10,40})\s+\d', t_mayus)
            if match_persona:
                nombre = match_persona.group(1).strip().title()
                return f"Certificado de Afiliación a Riesgos Laborales - {nombre} ({entidad})".strip()
            
            if "RIESGOS LABORALES" in t_mayus:
                return f"Certificado de Afiliación en Riesgos Laborales - {entidad}".strip()
            return f"Certificado Institucional - {entidad}".strip()

        # 2. Si es un artículo científico o reporte académico
        match_art = re.search(r'(DESARROLLO DE [^\n\.\,]{10,90})', t_mayus)
        if match_art:
            return match_art.group(1).strip().title()
        
        if "RESUMEN" in t_mayus or "ABSTRACT" in t_mayus:
            # Tomar la primera línea que no sea número de página ni encabezado de revista
            for l in lineas[:8]:
                l_s = l.strip()
                if len(l_s) > 15 and not re.match(r'^(page|\d+|http|issn|vol)', l_s.lower()):
                    return l_s.title()

        # 3. Si es un contrato
        match_contrato = re.search(r'(CONTRATO DE [^\n\.\,]{5,60})', t_mayus)
        if match_contrato:
            return match_contrato.group(1).strip().title()

        # 4. Si es una factura
        match_factura = re.search(r'(FACTURA [^\n\.\,]{3,40})', t_mayus)
        if match_factura:
            return match_factura.group(1).strip().title()

        # 5. Búsqueda de la línea principal de encabezado excluyendo ciudades y fechas
        for l in lineas[:10]:
            l_s = l.strip()
            if 15 <= len(l_s) <= 80:
                if not re.match(r'^(medell[ií]n|bogot[aá]|pereira|cali|\d{1,2}\s+de|\d{2,4}[-/]|p[aá]gina|http|www|direcci[oó]n)', l_s.lower()):
                    return l_s.title()

        return "Documento Administrativo General"

    def _resumir_texto(self, texto_bruto: str, max_oraciones: int = 2) -> tuple[str, str, str]:
        """Genera un título exacto y una síntesis ejecutiva clara y concisa."""
        lineas = [l.strip() for l in texto_bruto.split("\n") if len(l.strip()) > 3]
        if not lineas:
            return "No se pudo extraer texto.", "Sin Título", ""
        
        # 1. Obtener título exacto y limpio
        titulo_detectado = self._detectar_titulo_y_tema(texto_bruto, lineas)
        
        # 2. Sintetizar oraciones clave de forma limpia
        # Extraer oraciones evitando encabezados de fechas o tablas de códigos
        parrafos = [p.strip() for p in re.split(r'(?<=[.!?])\s+', " ".join(lineas)) if len(p.strip()) > 40]
        
        oraciones_validas = []
        for p in parrafos:
            p_low = p.lower()
            # Descartar líneas de IP, códigos de validación o fechas iniciales
            if any(p_low.startswith(x) for x in ["medell", "bogot", "pereira", "direcci", "código", "ip:", "si desea validar"]):
                continue
            oraciones_validas.append(p)
            
        if not oraciones_validas:
            oraciones_validas = parrafos[:max_oraciones]
            
        # Tomar las 2 oraciones más explicativas
        cuerpo_sintesis = " ".join(oraciones_validas[:max_oraciones]) if oraciones_validas else "Contenido documental procesado exitosamente."
        
        vista_previa = f"Título/Tema: {titulo_detectado}\n     Síntesis principal: {cuerpo_sintesis}"
        return vista_previa, titulo_detectado, cuerpo_sintesis

    def _crear_pdf_resumen(self, ruta_destino_pdf: str, nombre_original: str, titulo: str, resumen: str, total_paginas: int):
        """Crea un documento PDF profesional con el resumen y metadatos del documento analizado."""
        doc = SimpleDocTemplate(
            ruta_destino_pdf,
            pagesize=letter,
            rightMargin=54, leftMargin=54,
            topMargin=54, bottomMargin=54
        )
        styles = getSampleStyleSheet()
        
        style_title = ParagraphStyle(
            'HeaderTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1A365D"),
            spaceAfter=6
        )
        style_meta = ParagraphStyle(
            'MetaText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#4A5568")
        )
        style_body = ParagraphStyle(
            'BodySummary',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#2D3748"),
            spaceBefore=10
        )
        
        elementos = []
        elementos.append(Paragraph("Resumen Ejecutivo de Documento", style_title))
        elementos.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#2B6CB0"), spaceAfter=12))
        
        fecha_actual = time.strftime("%d/%m/%Y %H:%M:%S")
        elementos.append(Paragraph(f"<b>Archivo Analizado:</b> {nombre_original}", style_meta))
        elementos.append(Paragraph(f"<b>Páginas Procesadas:</b> {total_paginas}", style_meta))
        elementos.append(Paragraph(f"<b>Fecha de Generación:</b> {fecha_actual}", style_meta))
        if titulo:
            elementos.append(Paragraph(f"<b>Tema / Título Detectado:</b> {titulo}", style_meta))
        elementos.append(Spacer(1, 14))
        
        elementos.append(Paragraph("<b>Síntesis Analítica:</b>", ParagraphStyle('Sub', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor("#2B6CB0"))))
        elementos.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E0"), spaceAfter=8))
        elementos.append(Paragraph(resumen.replace("\n", "<br/>"), style_body))
        
        elementos.append(Spacer(1, 25))
        elementos.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceAfter=6))
        elementos.append(Paragraph("<i>Generado automáticamente por el Agente Organizador y Resumidor de Documentos</i>", ParagraphStyle('Foot', parent=styles['Italic'], fontSize=9, textColor=colors.HexColor("#718096"))))
        
        doc.build(elementos)

    def ejecutar(self, ruta_pdf: str) -> str:
        ruta_pdf = ruta_pdf.strip().strip('"').strip("'")
        if not os.path.exists(ruta_pdf):
            return f"Error: archivo '{ruta_pdf}' no encontrado"
        
        # 1. Extraer texto y metadatos con pypdf
        texto_completo = ""
        total_paginas = 0
        try:
            reader = pypdf.PdfReader(ruta_pdf)
            total_paginas = len(reader.pages)
            for pag in reader.pages[:10]:  # Leer hasta las primeras 10 páginas para eficiencia
                pag_text = pag.extract_text()
                if pag_text:
                    texto_completo += pag_text + "\n"
        except Exception as e:
            return f"Error extrayendo contenido del PDF: {e}"
        
        # 2. Generar resumen acertado y clasificar categoría
        if texto_completo.strip():
            resumen_texto, titulo_detectado, cuerpo_sintesis = self._resumir_texto(texto_completo)
            categoria_doc, prefijo_doc = self._clasificar_tipo_documento(texto_completo)
        else:
            resumen_texto = "No se pudo extraer texto legible (el PDF podría ser una imagen escaneada)."
            titulo_detectado = ""
            cuerpo_sintesis = resumen_texto
            categoria_doc, prefijo_doc = "Sin_Texto", "Doc"
        
        # 3. Organizar inteligentemente en subcarpeta según su categoría real
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        nombre_base = os.path.splitext(os.path.basename(ruta_pdf))[0]
        
        # Crear subcarpeta temática (ej: salidas/organizados/Contratos/, salidas/organizados/Facturas/)
        carpeta_categoria = os.path.join("salidas", "organizados", categoria_doc)
        os.makedirs(carpeta_categoria, exist_ok=True)
        
        # Nombre semántico limpio (ej: Contratos_Acuerdo_20261014.pdf)
        slug_titulo = re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ_]', '_', titulo_detectado)[:35].strip('_') if titulo_detectado else nombre_base
        nombre_organizado = f"{prefijo_doc}_{slug_titulo}_{timestamp}.pdf"
        ruta_destino_orig = os.path.join(carpeta_categoria, nombre_organizado)
        shutil.copy2(ruta_pdf, ruta_destino_orig)
        
        # 4. Generar el nuevo archivo PDF que contiene el resumen
        carpeta_resumenes = os.path.join("salidas", "resumenes_pdf", categoria_doc)
        os.makedirs(carpeta_resumenes, exist_ok=True)
        ruta_pdf_resumen = os.path.join(carpeta_resumenes, f"Resumen_{prefijo_doc}_{slug_titulo}_{timestamp}.pdf")
        
        try:
            self._crear_pdf_resumen(
                ruta_destino_pdf=ruta_pdf_resumen,
                nombre_original=os.path.basename(ruta_pdf),
                titulo=f"[{categoria_doc}] {titulo_detectado}" if titulo_detectado else categoria_doc,
                resumen=cuerpo_sintesis,
                total_paginas=total_paginas
            )
            mensaje_pdf = f"   • PDF con el resumen generado en: {ruta_pdf_resumen}\n"
        except Exception as err_pdf:
            mensaje_pdf = f"   • No se pudo generar el archivo PDF de resumen ({err_pdf})\n"
        
        resultado = (
            f" Documento clasificado y organizado con éxito:\n"
            f"   • Tipo/Categoría detectada: **{categoria_doc}**\n"
            f"   • Archivo original organizado en: {ruta_destino_orig}\n"
            f"{mensaje_pdf}"
            f"   • Total de páginas analizadas: {total_paginas}\n"
            f"   • Vista previa del resumen:\n"
            f"     \"{resumen_texto}\""
        )
        return resultado
