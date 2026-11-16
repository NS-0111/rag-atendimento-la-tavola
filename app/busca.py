"""Busca híbrida (BM25 + embeddings, fusão RRF). Mesma lógica do busca_e_avaliacao.py."""
import math
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
MODELO_EMB = os.getenv("MODELO_EMB", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

STOP = set("""a o as os um uma uns umas de do da dos das em no na nos nas por para com sem
e ou que se ao aos à às é são ser tem têm ter vocês voce você eu meu minha me mim
qual quais como quanto quanta quando onde posso pode dá da isso isto esse essa aí la lá
mais muito mas já foi vai""".split())


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


_STOP_NORM = {normalizar(w) for w in STOP}


def tokenizar(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", normalizar(s)) if w not in _STOP_NORM]


def carregar_trechos(data_dir: Path = DATA_DIR) -> list[dict]:
    """Cada título '##' vira um trecho (o que vem antes do primeiro '##' é ignorado)."""
    trechos = []
    for arq in sorted(Path(data_dir).glob("*.md")):
        partes = re.split(r"^## ", arq.read_text(encoding="utf-8"), flags=re.M)[1:]
        for p in partes:
            titulo, _, corpo = p.partition("\n")
            trechos.append({"arquivo": arq.name, "secao": titulo.strip(), "texto": corpo.strip()})
    return trechos


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [tokenizar(d) for d in docs]
        self.n = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / self.n
        df = Counter()
        for d in self.docs:
            df.update(set(d))
        self.idf = {w: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.tf = [Counter(d) for d in self.docs]

    def scores(self, pergunta: str) -> list[float]:
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


def ranking_de_scores(scores) -> list[int]:
    return sorted(range(len(scores)), key=lambda i: -scores[i])


def rrf(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: junta as listas pela posição. Devolve (índice, pontos)."""
    pontos = Counter()
    for r in rankings:
        for pos, idx in enumerate(r, start=1):
            pontos[idx] += 1 / (k + pos)
    return pontos.most_common()


class Buscador:
    """Carregue UMA vez (na inicialização da API) e reutilize."""

    def __init__(self, data_dir: Path = DATA_DIR, usar_embeddings: bool = True):
        self.trechos = carregar_trechos(data_dir)
        if not self.trechos:
            raise RuntimeError(f"Nenhum trecho encontrado em {data_dir}")
        self.textos = [f"{t['secao']}. {t['texto']}" for t in self.trechos]
        self.bm25 = BM25(self.textos)
        self.modelo = None
        if usar_embeddings:
            from sentence_transformers import SentenceTransformer
            self.modelo = SentenceTransformer(MODELO_EMB)
            self.emb = self.modelo.encode(self.textos, normalize_embeddings=True)

    def buscar(self, pergunta: str, k: int = 3) -> list[dict]:
        r_bm25 = ranking_de_scores(self.bm25.scores(pergunta))
        if self.modelo is None:               # só BM25 (útil em testes rápidos)
            fundida = [(i, 1 / (60 + p)) for p, i in enumerate(r_bm25, start=1)]
        else:
            q = self.modelo.encode([pergunta], normalize_embeddings=True)[0]
            r_emb = ranking_de_scores((self.emb @ q).tolist())
            fundida = rrf([r_bm25, r_emb])
        return [{**self.trechos[i], "score": round(s, 4)} for i, s in fundida[:k]]
