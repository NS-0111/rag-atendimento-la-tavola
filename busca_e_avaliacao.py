# Projeto 2 - La Tavola (restaurante fictício): busca e avaliação
# Script em células (# %%): funciona no Kaggle, no Colab e no VS Code.
# Mede a busca por BM25 (palavras), embeddings (significado) e híbrida (RRF).

# %% [célula 0] Instalação (tire o # da linha abaixo no Kaggle/Colab)
# !pip install -q sentence-transformers

# %% [célula 1] Configuração
import json, math, re, unicodedata
from collections import Counter
from pathlib import Path

BASE = Path(".")   # pasta que contém data/ e eval/ (ajuste no Kaggle, ex.: Path("/kaggle/working/projeto2-rag"))
MODELO_EMB = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOP_K_MAX = 18     # quantos trechos ranquear (todos)

# %% [célula 2] Trechos: cada título "##" vira um trecho
def carregar_trechos(base):
    trechos = []
    for arq in sorted((base / "data").glob("*.md")):
        texto = arq.read_text(encoding="utf-8")
        # tudo antes do primeiro "## " (título e aviso) é ignorado
        partes = re.split(r"^## ", texto, flags=re.M)[1:]
        for p in partes:
            titulo, _, corpo = p.partition("\n")
            trechos.append({"arquivo": arq.name, "secao": titulo.strip(),
                            "texto": corpo.strip()})
    return trechos

trechos = carregar_trechos(BASE)
print(len(trechos), "trechos")
for i, t in enumerate(trechos):
    print(f"{i:2d}  {t['arquivo']:12s} {t['secao']}")

# %% [célula 3] BM25 implementado à mão
STOP = set("""a o as os um uma uns umas de do da dos das em no na nos nas por para com sem
e ou que se ao aos à às é são ser tem têm ter vocês voce você eu meu minha me mim
qual quais como quanto quanta quando onde posso pode dá da isso isto esse essa aí la lá
mais muito mas já foi vai""".split())

def normalizar(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def tokenizar(s):
    palavras = re.findall(r"[a-z0-9]+", normalizar(s))
    stop = {normalizar(w) for w in STOP}
    return [w for w in palavras if w not in stop]

class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = [tokenizar(d) for d in docs]
        self.n = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / self.n
        df = Counter()
        for d in self.docs:
            df.update(set(d))
        # IDF: palavras raras pesam mais
        self.idf = {w: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.tf = [Counter(d) for d in self.docs]

    def scores(self, pergunta):
        q = tokenizar(pergunta)
        out = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for w in q:
                if w not in self.idf:
                    continue
                f = self.tf[i][w]
                s += self.idf[w] * f * (self.k1 + 1) / (
                    f + self.k1 * (1 - self.b + self.b * len(d) / self.avgdl))
            out.append(s)
        return out

# o texto indexado inclui o título da seção
textos = [f"{t['secao']}. {t['texto']}" for t in trechos]
bm25 = BM25(textos)

def ranking_de_scores(scores):
    """Lista de índices de trechos, do melhor para o pior."""
    return sorted(range(len(scores)), key=lambda i: -scores[i])

def busca_bm25(pergunta):
    return ranking_de_scores(bm25.scores(pergunta))

# %% [célula 4] Embeddings (significado)
from sentence_transformers import SentenceTransformer
import numpy as np

modelo = SentenceTransformer(MODELO_EMB)   # confira se o nome ainda é válido ao instalar
emb_trechos = modelo.encode(textos, normalize_embeddings=True)

def scores_emb(pergunta):
    q = modelo.encode([pergunta], normalize_embeddings=True)[0]
    return (emb_trechos @ q).tolist()   # similaridade do cosseno (vetores já normalizados)

def busca_emb(pergunta):
    return ranking_de_scores(scores_emb(pergunta))

# %% [célula 5] Busca híbrida: Reciprocal Rank Fusion (junta as duas listas por posição)
def rrf(rankings, k=60):
    pontos = Counter()
    for r in rankings:
        for pos, idx in enumerate(r, start=1):
            pontos[idx] += 1 / (k + pos)
    return [i for i, _ in pontos.most_common()]

def busca_hibrida(pergunta):
    return rrf([busca_bm25(pergunta), busca_emb(pergunta)])

# %% [célula 6] Avaliação: top-1, top-3 e MRR
perguntas = json.loads((BASE / "eval" / "perguntas.json").read_text(encoding="utf-8"))
com_resposta = [q for q in perguntas if q["tipo"] != "sem_resposta"]   # sem_resposta não entra aqui

def posicao_certa(ranking, esperadas):
    """Posição (1 = primeiro) da primeira seção esperada no ranking."""
    certas = {(e["arquivo"], e["secao"]) for e in esperadas}
    for pos, idx in enumerate(ranking, start=1):
        if (trechos[idx]["arquivo"], trechos[idx]["secao"]) in certas:
            return pos
    return None

def avaliar(busca, qs):
    pos = [posicao_certa(busca(q["pergunta"]), q["esperadas"]) for q in qs]
    n = len(qs)
    return {"n": n,
            "top1": sum(p == 1 for p in pos) / n,
            "top3": sum(p is not None and p <= 3 for p in pos) / n,
            "mrr": sum(1 / p for p in pos if p) / n}

METODOS = {"BM25": busca_bm25, "Embeddings": busca_emb, "Híbrida": busca_hibrida}
GRUPOS = {"todas": com_resposta,
          "diretas": [q for q in com_resposta if q["tipo"] == "direta"],
          "parafraseadas": [q for q in com_resposta if q["tipo"] == "parafraseada"]}

resultados = {}
for grupo, qs in GRUPOS.items():
    print(f"\n== {grupo} ({len(qs)} perguntas) ==")
    print(f"{'método':12s} {'top-1':>7s} {'top-3':>7s} {'MRR':>7s}")
    for nome, busca in METODOS.items():
        r = avaliar(busca, qs)
        resultados.setdefault(nome, {})[grupo] = r
        print(f"{nome:12s} {r['top1']:7.3f} {r['top3']:7.3f} {r['mrr']:7.3f}")

# %% [célula 7] Lista dos erros de cada método (para a análise do README)
erros = {}
for nome, busca in METODOS.items():
    erros[nome] = []
    print(f"\n--- erros de {nome} (seção certa fora do 1º lugar) ---")
    for q in com_resposta:
        ranking = busca(q["pergunta"])
        pos = posicao_certa(ranking, q["esperadas"])
        if pos != 1:
            achou = trechos[ranking[0]]["secao"]
            esperado = " / ".join(e["secao"] for e in q["esperadas"])
            print(f"[{q['tipo']}] #{q['id']} {q['pergunta']}\n    esperado: {esperado} (posição {pos}) | 1º lugar: {achou}")
            erros[nome].append({"id": q["id"], "tipo": q["tipo"], "pergunta": q["pergunta"],
                                "esperado": esperado, "posicao_certa": pos, "primeiro_lugar": achou})

# %% [célula 8] Salvar resultados (guarde esse arquivo e use SOMENTE esses números no README e no currículo)
saida = {"n_trechos": len(trechos), "n_perguntas_com_resposta": len(com_resposta),
         "modelo_embeddings": MODELO_EMB, "metricas": resultados, "erros": erros}
(BASE / "eval").mkdir(exist_ok=True)
(BASE / "eval" / "resultados_busca.json").write_text(
    json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
print("salvo em eval/resultados_busca.json")
