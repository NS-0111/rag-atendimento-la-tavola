"""Ferramentas do agente da La Tavola (restaurante fictício).

Cada ferramenta é uma função Python comum + um schema JSON (SCHEMAS) que descreve
o que ela faz para o modelo. O schema é neutro: os adaptadores em providers.py o
convertem para o formato de cada API (Claude, GPT, Gemini).
"""
import unicodedata
from datetime import datetime

from app.busca import Buscador

# Espelha data/cardapio.md (tests/test_agente.py confere que os preços batem).
PIZZAS = {  # nome: (média, grande, gigante)
    "margherita": (44, 56, 74), "calabresa": (46, 58, 78), "napolitana": (48, 60, 80),
    "portuguesa": (52, 64, 86), "quatro queijos": (54, 68, 90),
    "prosciutto e rucula": (62, 78, 104), "burrata e tomate seco": (66, 82, 108),
    "trufada": (68, 84, 112),
}
TAMANHOS = {"media": 0, "grande": 1, "gigante": 2}
OUTROS = {  # nome: (preço, alcoólico?)
    "bruschetta de tomate": (28, False), "focaccia": (24, False), "arancini": (32, False),
    "carpaccio": (46, False), "burrata": (52, False),
    "carbonara": (58, False), "fettuccine alfredo": (54, False), "lasanha": (56, False),
    "gnocchi": (50, False), "ravioli": (57, False), "penne ao pomodoro": (46, False),
    "tiramisu": (26, False), "panna cotta": (24, False), "cannoli": (22, False), "gelato": (20, False),
    "refrigerante": (8, False), "suco": (14, False), "agua sem gas": (6, False),
    "agua com gas": (7, False), "cerveja": (14, True), "chope": (16, True),
    "aperol spritz": (34, True), "limoncello": (18, True),
}
BORDA = 12  # só grande e gigante

HORARIOS = {  # dia -> (abre, fecha) em horas; fecha 24 = meia-noite
    "segunda": None, "terca": (18, 23), "quarta": (18, 23), "quinta": (18, 23),
    "sexta": (18, 24), "sabado": (18, 24), "domingo": (12, 22),
}

_buscador = None


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _separar_tamanho(nome: str) -> tuple[str, str]:
    """Modelos pequenos às vezes mandam 'Quatro Queijos gigante' no nome: separa o tamanho."""
    nome = nome.removeprefix("pizza ").strip()
    for t in TAMANHOS:
        if nome.endswith(" " + t):
            return nome[: -len(t) - 1].strip(), t
    return nome, ""


def buscar_informacoes(pergunta: str) -> dict:
    """Busca nos documentos (cardápio e FAQ) e devolve os 3 trechos mais relevantes."""
    global _buscador
    if _buscador is None:
        try:
            _buscador = Buscador()
        except ImportError:                      # sem sentence-transformers: só BM25
            _buscador = Buscador(usar_embeddings=False)
    return {"trechos": [{"fonte": f"{t['arquivo']} - {t['secao']}", "texto": t["texto"]}
                        for t in _buscador.buscar(pergunta, k=3)]}


def calcular_pedido(itens: list[dict], modo: str, distancia_km: float | None = None) -> dict:
    """Calcula o total do pedido seguindo as regras do FAQ (taxa, mínimo, desconto de retirada)."""
    subtotal = alcool = 0.0
    linhas = []
    if not itens:
        return {"erro": "A lista de itens está vazia. Informe os itens do pedido."}
    for it in itens:
        nome, qtd = _norm(it["nome"]), int(it.get("quantidade", 1))
        nome, tam_no_nome = _separar_tamanho(nome)
        if nome in PIZZAS:
            tam = _norm(it.get("tamanho") or "") or tam_no_nome
            if tam not in TAMANHOS:
                return {"erro": f"Informe o tamanho (media, grande ou gigante) da pizza {it['nome']}."}
            preco = PIZZAS[nome][TAMANHOS[tam]]
            if it.get("borda"):
                if tam == "media":
                    return {"erro": "Borda recheada só existe nos tamanhos grande e gigante."}
                preco += BORDA
            eh_alcool = False
        elif nome in OUTROS:
            preco, eh_alcool = OUTROS[nome]
        else:
            return {"erro": f"Item '{it['nome']}' não encontrado no cardápio calculável."}
        valor = preco * qtd
        subtotal += valor
        alcool += valor if eh_alcool else 0
        linhas.append({"item": it["nome"], "quantidade": qtd, "valor": valor})

    resp = {"itens": linhas, "subtotal": subtotal, "taxa_entrega": 0.0, "desconto": 0.0}
    if modo == "retirada":
        resp["desconto"] = round(0.10 * (subtotal - alcool), 2)   # 10%, exceto bebida alcoólica
    elif modo == "entrega":
        if distancia_km is None:
            return {"erro": "Informe a distância da entrega em km."}
        if distancia_km > 6:
            return {"erro": "Entregamos apenas em um raio de até 6 km."}
        if subtotal < 40:
            return {"erro": f"Pedido mínimo para entrega é R$ 40 (subtotal atual: R$ {subtotal:.0f})."}
        if distancia_km <= 3:
            resp["taxa_entrega"] = 0.0 if subtotal > 120 else 8.0
        else:
            resp["taxa_entrega"] = 14.0
    else:
        return {"erro": "modo deve ser 'entrega' ou 'retirada'."}
    resp["total"] = round(subtotal + resp["taxa_entrega"] - resp["desconto"], 2)
    return resp


def verificar_horario(dia_semana: str, hora: str | None = None) -> dict:
    """Diz se a pizzaria funciona no dia (e, se informada a hora 'HH:MM', naquele horário)."""
    dia = _norm(dia_semana).replace("-feira", "").replace(" feira", "")
    if dia not in HORARIOS:
        return {"erro": f"Dia inválido: {dia_semana}"}
    faixa = HORARIOS[dia]
    if faixa is None:
        return {"funciona": False, "horario": "fechado às segundas"}
    texto = f"das {faixa[0]}h às {'00' if faixa[1] == 24 else faixa[1]}h"
    if hora is None:
        return {"funciona": True, "horario": texto}
    h, m = (int(x) for x in hora.split(":"))
    return {"funciona": faixa[0] <= h + m / 60 < faixa[1], "horario": texto}


FERRAMENTAS = {f.__name__: f for f in (buscar_informacoes, calcular_pedido, verificar_horario)}

SCHEMAS = [
    {"name": "buscar_informacoes",
     "description": "Busca no cardápio e no FAQ da La Tavola (horários, entrega, pagamento, reembolso, "
                    "reservas, ingredientes, alergênicos). Use para qualquer pergunta factual.",
     "parameters": {"type": "object", "properties": {
         "pergunta": {"type": "string", "description": "A dúvida do cliente, reescrita de forma clara."}},
         "required": ["pergunta"]}},
    {"name": "calcular_pedido",
     "description": "Calcula o total de um pedido (subtotal, taxa de entrega, desconto de retirada). "
                    "Use SEMPRE que o cliente pedir o valor/total de itens; nunca some de cabeça.",
     "parameters": {"type": "object", "properties": {
         "itens": {"type": "array", "description": "Itens do pedido.", "items": {
             "type": "object", "properties": {
                 "nome": {"type": "string", "description": "Ex.: 'Margherita', 'refrigerante', 'tiramisù'."},
                 "quantidade": {"type": "integer"},
                 "tamanho": {"type": "string", "description": "Só para pizzas: media, grande ou gigante."},
                 "borda": {"type": "boolean", "description": "Borda recheada (só grande/gigante)."}},
             "required": ["nome", "quantidade"]}},
         "modo": {"type": "string", "enum": ["entrega", "retirada"]},
         "distancia_km": {"type": "number", "description": "Distância em km até o cliente. OBRIGATÓRIO quando modo = entrega: copie o número que o cliente disse."}},
         "required": ["itens", "modo"]}},
    {"name": "verificar_horario",
     "description": "Verifica se a pizzaria funciona em um dia da semana (e, opcionalmente, em uma hora).",
     "parameters": {"type": "object", "properties": {
         "dia_semana": {"type": "string", "description": "segunda, terça, quarta, quinta, sexta, sábado ou domingo."},
         "hora": {"type": "string", "description": "Formato 24h 'HH:MM' (opcional)."}},
         "required": ["dia_semana"]}},
]


def executar(nome: str, args: dict) -> dict:
    """Valida os argumentos e executa. Os erros voltam em português claro para o modelo tentar de novo."""
    if nome not in FERRAMENTAS:
        return {"erro": f"Ferramenta desconhecida: {nome}. Use: {', '.join(FERRAMENTAS)}."}
    schema = next(x for x in SCHEMAS if x["name"] == nome)["parameters"]
    faltando = [k for k in schema.get("required", []) if k not in args]
    if faltando:
        return {"erro": f"Faltou o argumento obrigatório: {', '.join(faltando)}. "
                        "Chame a ferramenta de novo com todos os argumentos obrigatórios."}
    extras = [k for k in args if k not in schema["properties"]]
    if extras:
        return {"erro": f"Argumento desconhecido: {', '.join(extras)}. Argumentos válidos: "
                        f"{', '.join(schema['properties'])}."}
    if nome == "calcular_pedido":
        itens = args["itens"]
        if not isinstance(itens, list) or any(not isinstance(i, dict) or "nome" not in i for i in itens):
            return {"erro": "'itens' deve ser uma lista de objetos, cada um com 'nome' e 'quantidade'. "
                            "Os campos 'modo' e 'distancia_km' ficam fora da lista de itens."}
    try:
        return FERRAMENTAS[nome](**args)
    except Exception as e:                       # o erro volta para o modelo tentar corrigir
        return {"erro": f"{type(e).__name__}: {e}"}
