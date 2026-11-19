"""Testes do agente SEM chamar nenhuma API. Rode: pytest tests/test_agente.py"""
import json
from pathlib import Path

from agente.agente import rodar_agente
from agente.eval_agente import avaliar_caso
from agente.providers import Roteirizado
from agente.tools import calcular_pedido, verificar_horario, executar, PIZZAS, OUTROS

CARDAPIO = (Path(__file__).resolve().parent.parent / "data" / "cardapio.md").read_text(encoding="utf-8")


def test_precos_do_codigo_batem_com_o_cardapio():
    for precos in PIZZAS.values():
        assert f"R$ {precos[0]} / R$ {precos[1]} / R$ {precos[2]}" in CARDAPIO
    for nome, (preco, _) in OUTROS.items():
        assert f"R$ {preco}" in CARDAPIO, nome


def test_entrega_com_taxa_de_14():
    r = calcular_pedido([{"nome": "Margherita", "quantidade": 1, "tamanho": "grande", "borda": True},
                         {"nome": "refrigerante", "quantidade": 2}], "entrega", 4)
    assert r["subtotal"] == 84 and r["taxa_entrega"] == 14 and r["total"] == 98


def test_retirada_nao_da_desconto_em_bebida_alcoolica():
    r = calcular_pedido([{"nome": "Calabresa", "quantidade": 2, "tamanho": "media"},
                         {"nome": "chope", "quantidade": 1}], "retirada")
    assert r["desconto"] == 9.2 and r["total"] == 98.8


def test_frete_gratis_acima_de_120_ate_3km():
    r = calcular_pedido([{"nome": "Quatro Queijos", "quantidade": 2, "tamanho": "gigante"}], "entrega", 3)
    assert r["taxa_entrega"] == 0


def test_erros_voltam_para_o_modelo():
    assert "mínimo" in calcular_pedido([{"nome": "agua sem gas", "quantidade": 1}], "entrega", 2)["erro"]
    assert "6 km" in calcular_pedido([{"nome": "lasanha", "quantidade": 3}], "entrega", 8)["erro"]
    assert "grande e gigante" in calcular_pedido(
        [{"nome": "Margherita", "quantidade": 1, "tamanho": "media", "borda": True}], "retirada")["erro"]
    assert "tamanho" in calcular_pedido([{"nome": "Margherita", "quantidade": 1}], "retirada")["erro"]


def test_horario():
    assert verificar_horario("sexta", "23:30")["funciona"] is True
    assert verificar_horario("terça-feira", "17:00")["funciona"] is False
    assert verificar_horario("segunda")["funciona"] is False


def test_loop_executa_ferramenta_e_devolve_resultado_ao_modelo():
    falso = Roteirizado([
        ("", [{"id": "1", "nome": "verificar_horario", "args": {"dia_semana": "segunda"}}]),
        ("Segunda estamos fechados.", []),
    ])
    r = rodar_agente(falso, "Abrem na segunda?")
    assert r["passos"] == 2 and r["chamadas"][0]["resultado"]["funciona"] is False
    assert falso.recebidos[0][0]["funciona"] is False       # o resultado voltou para o "modelo"


def test_avaliacao_dos_casos():
    casos = {c["id"]: c for c in json.loads(
        (Path(__file__).resolve().parent.parent / "eval" / "casos_agente.json").read_text(encoding="utf-8"))}
    bom = {"resposta": "O total é R$ 98,00.", "chamadas": [{"nome": "calcular_pedido"}]}
    ruim = {"resposta": "Dá uns R$ 90.", "chamadas": []}
    assert avaliar_caso(casos[4], bom)["passou"] and not avaliar_caso(casos[4], ruim)["passou"]


def test_resposta_vazia_refaz_uma_vez():
    falso = Roteirizado([("", []), ("Estamos abertos.", [])])
    r = rodar_agente(falso, "Estão abertos?")
    assert r["tentativas"] == 2 and r["resposta"] == "Estamos abertos."


def test_tamanho_dentro_do_nome_e_lista_vazia():
    r = calcular_pedido([{"nome": "Quatro Queijos gigante", "quantidade": 1}], "retirada")
    assert r["subtotal"] == 90
    r = calcular_pedido([{"nome": "pizza Margherita", "quantidade": 1, "tamanho": "grande"}], "retirada")
    assert r["subtotal"] == 56
    assert "vazia" in calcular_pedido([], "retirada")["erro"]


def test_executar_devolve_erros_claros():
    assert "itens" in executar("calcular_pedido", {"modo": "entrega", "distancia_km": 2})["erro"]
    mistura = {"itens": [{"nome": "lasanha", "quantidade": 1}, {"distancia_km": 2}], "modo": "entrega"}
    assert "nome" in executar("calcular_pedido", mistura)["erro"]
    assert "desconhecido" in executar("verificar_horario", {"dia_semana": "sexta", "foo": 1})["erro"]
    assert "desconhecida" in executar("inexistente", {})["erro"]
    assert executar("verificar_horario", {"dia_semana": "sexta"})["funciona"] is True
