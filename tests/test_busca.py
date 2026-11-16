"""Testes rápidos da busca (só BM25, sem baixar modelos). Rode: pytest tests/test_busca.py"""
from app.busca import Buscador, carregar_trechos


def test_carrega_18_trechos():
    assert len(carregar_trechos()) == 18


def test_reembolso_devolve_a_fonte_reembolso():
    b = Buscador(usar_embeddings=False)
    fontes = [t["secao"] for t in b.buscar("Qual o prazo do reembolso?", k=3)]
    assert fontes[0] == "Reembolso"


def test_horario_devolve_a_fonte_horario():
    b = Buscador(usar_embeddings=False)
    assert b.buscar("Qual o horário de funcionamento da La Tavola?", k=1)[0]["secao"] == "Horário de funcionamento"
