"""API do assistente da La Tavola (restaurante fictício). Rode: uvicorn app.main:app --port 8000"""
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.busca import Buscador
from app.geracao import Gerador

K_TRECHOS = 3
estado = {}                      # modelos carregados UMA vez, na inicialização
trava = threading.Lock()         # um modelo só gera uma resposta por vez


@asynccontextmanager
async def lifespan(app: FastAPI):
    estado["buscador"] = Buscador()
    estado["gerador"] = Gerador()
    yield
    estado.clear()


app = FastAPI(title="Assistente La Tavola (dados fictícios)", lifespan=lifespan)


class PerguntaIn(BaseModel):
    pergunta: str = Field(..., min_length=3, max_length=500, examples=["Qual o prazo do reembolso?"])


class Fonte(BaseModel):
    arquivo: str
    secao: str
    score: float


class RespostaOut(BaseModel):
    resposta: str
    fontes: list[Fonte]


@app.get("/health")
def health():
    return {"status": "ok", "modelos_carregados": bool(estado)}


@app.post("/perguntar", response_model=RespostaOut)
def perguntar(corpo: PerguntaIn):
    trechos = estado["buscador"].buscar(corpo.pergunta, k=K_TRECHOS)
    with trava:
        resposta = estado["gerador"].gerar(corpo.pergunta, trechos)
    return RespostaOut(resposta=resposta,
                       fontes=[Fonte(arquivo=t["arquivo"], secao=t["secao"], score=t["score"]) for t in trechos])
