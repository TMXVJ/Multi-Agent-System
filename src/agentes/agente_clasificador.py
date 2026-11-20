"""src/agentes/agente_clasificador.py
Agente 1: Clasificador de correos con BERT tiny afinado (fine-tuning)
Categorías: facturacion | soporte | comercial | otro
"""
import os
import imaplib
import email
from email.header import decode_header
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


class AgenteClasificador:
    """Agente 1: clasifica correos con BERT tiny afinado (fine-tuning) en
    facturacion | soporte | comercial | otro.

    El modelo se entrena con `entrenar_bert.py` y se carga desde disco, por lo que
    la inferencia es 100 % local (sin HF_TOKEN ni conexión a Hugging Face)."""

    RUTA_MODELO = os.getenv("RUTA_MODELO_CORREOS", "modelos/bert_tiny_correos")
    UMBRAL_CONFIANZA = float(os.getenv("UMBRAL_CONFIANZA", "0.50"))  # calíbralo con el conjunto de validación
    MAX_LEN = 128

    def __init__(self):
        if not os.path.isdir(self.RUTA_MODELO):
            raise FileNotFoundError(
                f"No se encontró el modelo afinado en '{self.RUTA_MODELO}'. "
                "Ejecuta primero: python entrenar_bert.py"
            )
        print("Cargando modelo BERT tiny afinado ...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.RUTA_MODELO, local_files_only=True)
        self.modelo = AutoModelForSequenceClassification.from_pretrained(self.RUTA_MODELO, local_files_only=True)
        self.modelo.eval()
        # Las etiquetas viajan dentro del modelo (config.id2label), así no se desincronizan.
        self.categorias = {int(k): v for k, v in self.modelo.config.id2label.items()}
        print("Modelo BERT tiny cargado correctamente para el agente #1")

    def clasificar(self, contenido: str) -> tuple[str, float]:
        """Devuelve (etiqueta, probabilidad) usando únicamente la salida de BERT tiny."""
        inputs = self.tokenizer(contenido, return_tensors="pt", truncation=True, max_length=self.MAX_LEN)
        with torch.no_grad():
            logits = self.modelo(**inputs).logits
        probs = torch.softmax(logits, dim=1)[0]
        pred = int(torch.argmax(probs))
        return self.categorias[pred], float(probs[pred])

    def ejecutar(self, contenido: str) -> str:
        etiqueta, prob = self.clasificar(contenido)
        salida = f"Correo clasificado como: **{etiqueta}** (Confianza: {prob * 100:.1f}%)"
        if prob < self.UMBRAL_CONFIANZA:
            salida += "Baja confianza: se recomienda revisión humana."
        return salida

    def leer_correos_reales(self, servidor_imap: str, usuario: str, clave: str, max_correos: int = 3) -> str:
        """Se conecta a Gmail u Outlook vía IMAP y clasifica los correos reales."""
        try:
            print(f"Conectando a {servidor_imap} para el usuario {usuario}...")
            mail = imaplib.IMAP4_SSL(servidor_imap, port=993)
            mail.login(usuario, clave)
            mail.select("INBOX")
            
            status, mensajes = mail.search(None, "ALL")
            if status != "OK" or not mensajes[0]:
                mail.logout()
                return "No se encontraron correos en la bandeja de entrada."
            
            ids = mensajes[0].split()
            ultimos_ids = ids[-max_correos:]  # Los últimos correos
            ultimos_ids.reverse()             # Más recientes primero
            
            resultados = []
            for num in ultimos_ids:
                status, data = mail.fetch(num, "(RFC822)")
                if status != "OK":
                    continue
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Decodificar asunto de forma robusta
                asunto_raw = msg.get("Subject", "Sin asunto")
                asunto = "Sin asunto"
                try:
                    partes_asunto = decode_header(asunto_raw)
                    texto_asunto = []
                    for fragmento, enc in partes_asunto:
                        if isinstance(fragmento, bytes):
                            # Manejar encodings no estándar como 'unknown-8bit'
                            enc_valido = enc if enc and enc.lower() not in ["unknown-8bit", "unknown"] else "utf-8"
                            try:
                                texto_asunto.append(fragmento.decode(enc_valido, errors="ignore"))
                            except Exception:
                                texto_asunto.append(fragmento.decode("latin-1", errors="ignore"))
                        else:
                            texto_asunto.append(str(fragmento))
                    asunto = " ".join(texto_asunto)
                except Exception:
                    asunto = str(asunto_raw)
                
                remitente = str(msg.get("From", "Desconocido"))
                
                # Extraer cuerpo de forma segura
                cuerpo = ""
                try:
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                payload = part.get_payload(decode=True)
                                if payload:
                                    try:
                                        cuerpo = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                                    except Exception:
                                        cuerpo = payload.decode("latin-1", errors="ignore")
                                    break
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            try:
                                cuerpo = payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")
                            except Exception:
                                cuerpo = payload.decode("latin-1", errors="ignore")
                except Exception:
                    cuerpo = ""
                
                texto_para_clasificar = f"{asunto}. {cuerpo[:400]}"
                clasif = self.ejecutar(texto_para_clasificar)
                resultados.append(
                    f"De: {remitente}\n"
                    f"Asunto: {asunto}\n"
                    f"{clasif}\n"
                )
            
            mail.logout()
            return "\n".join(resultados)
        except Exception as e:
            return f"Error conectando a la cuenta de correo: {e}"
