# entrenar_bert.py
"""
Fine-tuning de BERT tiny (prajjwal1/bert-tiny) para clasificar correos en:
facturacion | soporte | comercial | otro

Uso:
    python entrenar_bert.py                      # entrena, evalúa y guarda el modelo
    python entrenar_bert.py --cv 0               # sin validación cruzada (más rápido)
    python entrenar_bert.py --epocas 40 --lr 3e-4

Salidas:
    modelos/bert_tiny_correos/   modelo + tokenizer afinados (los usa el agente 1)
    resultados/metricas.json     métricas para la tabla del artículo
    resultados/reporte.txt       reporte legible (classification_report, matriz de confusión)
    resultados/matriz_confusion_bert.png (si hay matplotlib)
"""
import argparse
import copy
import json
import os
import random
import time

import numpy as np
import pandas as pd
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup, BertTokenizer, BertForSequenceClassification

ETIQUETAS = ["facturacion", "soporte", "comercial", "otro"]
LABEL2ID = {l: i for i, l in enumerate(ETIQUETAS)}
ID2LABEL = {i: l for l, i in LABEL2ID.items()}
MAX_LEN = 128
SEED = 42


def fijar_semilla(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def cargar_csv(ruta):
    df = pd.read_csv(ruta, encoding="utf-8-sig")
    df = df.dropna(subset=["texto", "etiqueta"])
    df["etiqueta"] = df["etiqueta"].str.strip().str.lower()
    desconocidas = set(df["etiqueta"]) - set(ETIQUETAS)
    if desconocidas:
        raise ValueError(f"Etiquetas no válidas en {ruta}: {desconocidas}")
    return df["texto"].tolist(), [LABEL2ID[e] for e in df["etiqueta"]]


# ---------------------------------------------------------------- BERT tiny
def cargar_base(nombre_modelo):
    tok = BertTokenizer.from_pretrained(nombre_modelo)
    modelo = BertForSequenceClassification.from_pretrained(
        nombre_modelo, num_labels=len(ETIQUETAS), id2label=ID2LABEL, label2id=LABEL2ID,
        ignore_mismatched_sizes=True,  # la cabeza de clasificación se crea nueva (es lo que se entrena)
    )
    return tok, modelo


def tokenizar(tok, textos):
    return tok(textos, truncation=True, max_length=MAX_LEN, padding=True, return_tensors="pt")


@torch.no_grad()
def predecir(modelo, tok, textos, lote=32):
    modelo.eval()
    probs = []
    for i in range(0, len(textos), lote):
        enc = tokenizar(tok, textos[i:i + lote])
        probs.append(torch.softmax(modelo(**enc).logits, dim=1).cpu().numpy())
    return np.vstack(probs)


def entrenar_bert(nombre_modelo, X_tr, y_tr, X_val=None, y_val=None, epocas=30, lr=3e-4, lote=16, verbose=True):
    """Fine-tuning completo. Si hay validación, conserva el mejor estado (macro-F1)."""
    fijar_semilla()
    tok, modelo = cargar_base(nombre_modelo)
    opt = torch.optim.AdamW(modelo.parameters(), lr=lr, weight_decay=0.01)
    pasos = epocas * int(np.ceil(len(X_tr) / lote))
    sched = get_linear_schedule_with_warmup(opt, int(0.1 * pasos), pasos)
    y_tr = np.array(y_tr)
    mejor_f1, mejor_estado, mejor_ep = -1.0, None, 0

    for ep in range(1, epocas + 1):
        modelo.train()
        idx = np.random.permutation(len(X_tr))
        perdida = 0.0
        for i in range(0, len(idx), lote):
            b = idx[i:i + lote]
            enc = tokenizar(tok, [X_tr[j] for j in b])
            out = modelo(**enc, labels=torch.tensor(y_tr[b]))
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
            opt.step(); sched.step(); opt.zero_grad()
            perdida += out.loss.item() * len(b)
        if X_val is not None:
            f1 = f1_score(y_val, predecir(modelo, tok, X_val).argmax(1), average="macro")
            if f1 > mejor_f1:
                mejor_f1, mejor_estado, mejor_ep = f1, copy.deepcopy(modelo.state_dict()), ep
            if verbose and (ep % 5 == 0 or ep == 1):
                print(f"  época {ep:3d} | loss {perdida/len(X_tr):.4f} | F1-macro val {f1:.3f}")
        elif verbose and (ep % 10 == 0 or ep == 1):
            print(f"  época {ep:3d} | loss {perdida/len(X_tr):.4f}")
    if mejor_estado is not None:
        modelo.load_state_dict(mejor_estado)
        if verbose:
            print(f"  -> mejor época por validación: {mejor_ep} (F1-macro val {mejor_f1:.3f})")
    return tok, modelo


# ---------------------------------------------------------------- baseline
def entrenar_baseline(X_tr, y_tr):
    vec = TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", lowercase=True)
    clf = LogisticRegression(max_iter=1000, C=10)
    clf.fit(vec.fit_transform(X_tr), y_tr)
    return vec, clf


def predecir_baseline(vec, clf, textos):
    return clf.predict_proba(vec.transform(textos))


# ---------------------------------------------------------------- métricas
def metricas(y_true, probs, nombre):
    y_pred = probs.argmax(1)
    return {
        "modelo": nombre,
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "f1_macro": round(float(f1_score(y_true, y_pred, average="macro")), 4),
        "confianza_media": round(float(probs.max(1).mean()), 4),
    }


def texto_reporte(y_true, probs, titulo):
    y_pred = probs.argmax(1)
    cm = confusion_matrix(y_true, y_pred, labels=range(len(ETIQUETAS)))
    return (
        f"=== {titulo} ===\n"
        + classification_report(y_true, y_pred, labels=range(len(ETIQUETAS)), target_names=ETIQUETAS, digits=3, zero_division=0)
        + "\nMatriz de confusión (filas = real, columnas = predicho; orden: " + ", ".join(ETIQUETAS) + ")\n"
        + str(cm) + "\n\n"
    )


def guardar_matriz_png(y_true, probs, ruta, titulo):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    cm = confusion_matrix(y_true, probs.argmax(1), labels=range(len(ETIQUETAS)))
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(ETIQUETAS))); ax.set_xticklabels(ETIQUETAS, rotation=30, ha="right")
    ax.set_yticks(range(len(ETIQUETAS))); ax.set_yticklabels(ETIQUETAS)
    ax.set_xlabel("Predicho"); ax.set_ylabel("Real"); ax.set_title(titulo)
    for i in range(len(ETIQUETAS)):
        for j in range(len(ETIQUETAS)):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.tight_layout(); fig.savefig(ruta, dpi=200); plt.close(fig)


def latencia_ms(fn, textos, repeticiones=3):
    fn(textos[:2])  # calentamiento
    t0 = time.perf_counter()
    for _ in range(repeticiones):
        for t in textos:
            fn([t])
    return round((time.perf_counter() - t0) / (repeticiones * len(textos)) * 1000, 2)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", default="datos/correos_etiquetados.csv")
    ap.add_argument("--externo", default="datos/correos_prueba_externa.csv")
    ap.add_argument("--modelo", default="prajjwal1/bert-tiny", help="nombre en HuggingFace o ruta local")
    ap.add_argument("--salida", default="modelos/bert_tiny_correos")
    ap.add_argument("--epocas", type=int, default=30)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--cv", type=int, default=5, help="folds de validación cruzada (0 = desactivar)")
    a = ap.parse_args()

    os.makedirs("resultados", exist_ok=True)
    X, y = cargar_csv(a.datos)
    print(f"Dataset: {len(X)} correos | distribución: " + ", ".join(f"{ID2LABEL[i]}={y.count(i)}" for i in range(len(ETIQUETAS))))

    # 70 / 15 / 15 estratificado
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.30, stratify=y, random_state=SEED)
    X_val, X_te, y_val, y_te = train_test_split(X_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=SEED)
    print(f"Split -> train {len(X_tr)} | val {len(X_val)} | test {len(X_te)}\n")

    print("Entrenando baseline TF-IDF + Regresión Logística...")
    vec, clf = entrenar_baseline(X_tr, y_tr)
    print("Fine-tuning BERT tiny...")
    tok, modelo = entrenar_bert(a.modelo, X_tr, y_tr, X_val, y_val, epocas=a.epocas, lr=a.lr)

    p_bert_te = predecir(modelo, tok, X_te)
    p_base_te = predecir_baseline(vec, clf, X_te)

    res = {
        "n_train": len(X_tr), "n_val": len(X_val), "n_test": len(X_te),
        "hiperparametros": {"epocas": a.epocas, "lr": a.lr, "max_len": MAX_LEN, "seed": SEED, "modelo_base": a.modelo},
        "test": [metricas(y_te, p_bert_te, "BERT tiny (fine-tuned)"), metricas(y_te, p_base_te, "TF-IDF + LogReg (baseline)")],
    }
    reporte = texto_reporte(y_te, p_bert_te, "BERT tiny - conjunto de prueba")
    reporte += texto_reporte(y_te, p_base_te, "Baseline TF-IDF + LogReg - conjunto de prueba")
    guardar_matriz_png(y_te, p_bert_te, "resultados/matriz_confusion_bert.png", "BERT tiny - test")

    # Prueba externa (correos reales del buzón, NO usados en entrenamiento)
    if a.externo and os.path.exists(a.externo):
        Xe, ye = cargar_csv(a.externo)
        p_bert_e = predecir(modelo, tok, Xe)
        p_base_e = predecir_baseline(vec, clf, Xe)
        res["externo"] = [metricas(ye, p_bert_e, "BERT tiny (fine-tuned)"), metricas(ye, p_base_e, "TF-IDF + LogReg (baseline)")]
        reporte += texto_reporte(ye, p_bert_e, f"BERT tiny - prueba externa (n={len(Xe)})")
        reporte += texto_reporte(ye, p_base_e, f"Baseline - prueba externa (n={len(Xe)})")
        print("\nDetalle prueba externa (BERT tiny):")
        for t, real, p in zip(Xe, ye, p_bert_e):
            ok = "OK " if p.argmax() == real else "ERR"
            print(f"  [{ok}] real={ID2LABEL[real]:11s} pred={ID2LABEL[int(p.argmax())]:11s} conf={p.max()*100:5.1f}%  {t[:60]}")

    # Latencia en CPU (RNF4)
    muestra = X_te[:10]
    res["latencia_ms_por_correo"] = {
        "bert_tiny": latencia_ms(lambda t: predecir(modelo, tok, t), muestra),
        "tfidf_logreg": latencia_ms(lambda t: predecir_baseline(vec, clf, t), muestra),
        "parametros_bert": int(sum(p.numel() for p in modelo.parameters())),
    }

    # Validación cruzada opcional (recomendada: el test de 24 correos es muy pequeño)
    if a.cv and a.cv > 1:
        print(f"\nValidación cruzada estratificada ({a.cv} folds)...")
        skf = StratifiedKFold(n_splits=a.cv, shuffle=True, random_state=SEED)
        f1_b, f1_t, ac_b, ac_t = [], [], [], []
        Xa, ya = np.array(X, dtype=object), np.array(y)
        for k, (i_tr, i_te) in enumerate(skf.split(Xa, ya), 1):
            xtr, ytr, xte, yte = list(Xa[i_tr]), list(ya[i_tr]), list(Xa[i_te]), list(ya[i_te])
            tk, md = entrenar_bert(a.modelo, xtr, ytr, epocas=a.epocas, lr=a.lr, verbose=False)
            pb = predecir(md, tk, xte).argmax(1)
            v, c = entrenar_baseline(xtr, ytr)
            pt = predecir_baseline(v, c, xte).argmax(1)
            ac_b.append(accuracy_score(yte, pb)); f1_b.append(f1_score(yte, pb, average="macro"))
            ac_t.append(accuracy_score(yte, pt)); f1_t.append(f1_score(yte, pt, average="macro"))
            print(f"  fold {k}: BERT acc={ac_b[-1]:.3f} F1={f1_b[-1]:.3f} | TF-IDF acc={ac_t[-1]:.3f} F1={f1_t[-1]:.3f}")
        res["cv"] = {
            "folds": a.cv,
            "bert_tiny": {"accuracy": f"{np.mean(ac_b):.3f} ± {np.std(ac_b):.3f}", "f1_macro": f"{np.mean(f1_b):.3f} ± {np.std(f1_b):.3f}"},
            "tfidf_logreg": {"accuracy": f"{np.mean(ac_t):.3f} ± {np.std(ac_t):.3f}", "f1_macro": f"{np.mean(f1_t):.3f} ± {np.std(f1_t):.3f}"},
        }

    # Guardar el modelo para el agente 1
    os.makedirs(a.salida, exist_ok=True)
    modelo.save_pretrained(a.salida)
    tok.save_pretrained(a.salida)

    with open("resultados/metricas.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    with open("resultados/reporte.txt", "w", encoding="utf-8") as f:
        f.write(reporte)

    print("\n" + reporte)
    print(json.dumps({k: v for k, v in res.items() if k in ("test", "externo", "cv", "latencia_ms_por_correo")}, ensure_ascii=False, indent=2))
    print(f"\nModelo guardado en: {a.salida}\nMétricas en: resultados/metricas.json y resultados/reporte.txt")


if __name__ == "__main__":
    main()
