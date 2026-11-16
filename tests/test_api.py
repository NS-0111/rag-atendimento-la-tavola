"""Teste da API completa (carrega os modelos: demora). Rode: pytest tests/test_api.py -s"""
from fastapi.testclient import TestClient
from app.main import app


def test_health_e_perguntar():
    with TestClient(app) as c:                       # o "with" dispara o carregamento dos modelos
        assert c.get("/health").json()["status"] == "ok"
        r = c.post("/perguntar", json={"pergunta": "Qual o prazo do reembolso?"})
        assert r.status_code == 200
        dados = r.json()
        assert dados["resposta"]
        assert "Reembolso" in [f["secao"] for f in dados["fontes"]]


def test_pergunta_sem_resposta_nao_inventa_preco_ou_horario():
    # Conferir À MÃO se a resposta recusa; o teste só garante que a API responde com fontes.
    with TestClient(app) as c:
        r = c.post("/perguntar", json={"pergunta": "Vocês têm estacionamento próprio?"})
        print("\nRESPOSTA:", r.json()["resposta"])
        assert r.status_code == 200 and r.json()["fontes"]
