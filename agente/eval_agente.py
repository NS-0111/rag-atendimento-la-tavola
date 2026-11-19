"""Avalia o agente em vários modelos e versões de prompt.

Uso (na raiz do repositório):
  python -m agente.eval_agente --provedores openai --prompts v1 v2 v3 v4
  python -m agente.eval_agente --casos eval/casos_agente_heldout.json ...   (conjunto novo)
Cada caso passa se: (1) chamou todas as ferramentas obrigatórias, (2) não chamou as proibidas,
(3) a resposta contém pelo menos um dos trechos de 'uma_destas'.
Métrica extra: 'recusa indevida' = % das perguntas respondíveis em que o agente disse "Não encontrei".
"""
import argparse
import json
import statistics
import unicodedata
from pathlib import Path

from agente.agente import rodar_agente
from agente.prompts import PROMPTS
from agente.providers import PROVEDORES

CASOS = Path(__file__).resolve().parent.parent / "eval" / "casos_agente.json"


def _n(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def avaliar_caso(caso: dict, r: dict) -> dict:
    usadas = {c["nome"] for c in r["chamadas"]}
    ferramentas_ok = set(caso["obrigatorias"]) <= usadas and not (set(caso["proibidas"]) & usadas)
    conteudo_ok = any(_n(t) in _n(r["resposta"]) for t in caso["uma_destas"])
    return {"ferramentas_ok": ferramentas_ok, "conteudo_ok": conteudo_ok, "passou": ferramentas_ok and conteudo_ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provedores", nargs="+", choices=PROVEDORES, default=["claude"])
    ap.add_argument("--prompts", nargs="+", choices=PROMPTS, default=list(PROMPTS))
    ap.add_argument("--casos", default=str(CASOS), help="arquivo JSON com os casos")
    a = ap.parse_args()
    arq = Path(a.casos)
    casos = json.loads(arq.read_text(encoding="utf-8"))
    tudo, tabela = [], []
    for prov in a.provedores:
        for pv in a.prompts:
            p = PROVEDORES[prov]()
            linhas = []
            for caso in casos:
                try:
                    r = rodar_agente(p, caso["pergunta"], pv)
                except Exception as e:                      # falha de API conta como erro, não derruba tudo
                    r = {"resposta": f"ERRO: {e}", "chamadas": [], "passos": 0, "latencia_s": 0}
                av = avaliar_caso(caso, r)
                linhas.append({"id": caso["id"], "tipo": caso["tipo"], **av,
                               "recusou": "nao encontrei" in _n(r["resposta"]),
                               "latencia_s": r["latencia_s"], "passos": r["passos"],
                               "tentativas": r.get("tentativas", 1), "resposta": r["resposta"],
                               "ferramentas": [c["nome"] for c in r["chamadas"]],
                               "chamadas": r["chamadas"]})       # nome, argumentos e resultado de cada chamada
            tudo.append({"provedor": prov, "modelo": p.modelo, "prompt": pv, "casos": linhas})
            n = len(linhas)
            respondiveis = [x for x in linhas if x["tipo"] != "sem_resposta"]
            tabela.append((prov, p.modelo, pv,
                           sum(x["ferramentas_ok"] for x in linhas) / n,
                           sum(x["conteudo_ok"] for x in linhas) / n,
                           sum(x["passou"] for x in linhas) / n,
                           sum(x["recusou"] for x in respondiveis) / len(respondiveis),
                           statistics.mean(x["latencia_s"] for x in linhas)))
    saida = arq.parent / f"resultados_{arq.stem.removeprefix('casos_')}.json"
    saida.write_text(json.dumps(tudo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"(detalhes em {saida})")
    print(f"{'provedor':<9}{'modelo':<22}{'prompt':<7}{'ferram.':>8}{'conteúdo':>10}{'passou':>8}{'recusa ind.':>13}{'lat. (s)':>10}")
    for prov, mod, pv, f, c, ok, rec, lat in tabela:
        print(f"{prov:<9}{mod:<22}{pv:<7}{f:>8.0%}{c:>10.0%}{ok:>8.0%}{rec:>13.0%}{lat:>10.2f}")


if __name__ == "__main__":
    main()
