"""src/supervisor/clasificador_intencion.py
Clasificador de intención basado en TF-IDF y Regresión Logística.
Detecta si la petición corresponde a:
  0: Clasificar correo (Agente 1)
  1: Generar reporte / Excel (Agente 2)
  2: Organizar / resumir PDF (Agente 3)
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


class ClasificadorIntencion:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()
        self.modelo = LogisticRegression()
        self._entrenar()

    def _entrenar(self):
        frases = [
            # 0: Clasificar correo
            "clasifica este correo", "clasificar email", "clasificar correo",
            "revisar correo", "analizar este mensaje", "tengo un correo para clasificar",
            "clasifica un email", "leer correo", "categorizar correo", "clasificacion de correo",
            # 1: Generar reporte / Excels
            "genera un reporte", "hacer reporte", "consolidar excels",
            "unir archivos de excel", "analizar datos de excel", "crear informe de excel",
            "resumen de ventas", "procesar tablas de excel", "generar resumen de excel", "consolidar reportes",
            # 2: Organizar PDF
            "organiza este pdf", "archivar documento", "mover archivo",
            "resumir pdf", "organizar documento pdf", "leer y resumir pdf",
            "analizar archivo pdf", "organizar contratos", "clasificar pdf", "resumen de documento"
        ]
        intenciones = [
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
            2, 2, 2, 2, 2, 2, 2, 2, 2, 2
        ]
        X = self.vectorizer.fit_transform(frases)
        self.modelo.fit(X, intenciones)

    def predecir(self, texto: str) -> int:
        X = self.vectorizer.transform([texto])
        return int(self.modelo.predict(X)[0])
