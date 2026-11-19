"""Loop do agente: o modelo pede ferramentas, a gente executa e devolve, até ele responder."""
import time

from agente.prompts import PROMPTS
from agente.providers import Provedor
from agente.tools import executar

MAX_PASSOS = 5


def _uma_execucao(provedor: Provedor, pergunta: str, prompt: str) -> dict:
    provedor.iniciar(PROMPTS[prompt], pergunta)
    chamadas_feitas, texto = [], ""
    for passo in range(1, MAX_PASSOS + 1):
        texto, chamadas = provedor.passo()
        if not chamadas:
            break
        resultados = [executar(c["nome"], c["args"]) for c in chamadas]
        chamadas_feitas += [{"nome": c["nome"], "args": c["args"], "resultado": r}
                            for c, r in zip(chamadas, resultados)]
        provedor.enviar_resultados(chamadas, resultados)
    else:
        texto = texto or "(limite de passos atingido)"
    return {"resposta": texto.strip(), "chamadas": chamadas_feitas, "passos": passo}


def rodar_agente(provedor: Provedor, pergunta: str, prompt: str = "v2") -> dict:
    inicio = time.perf_counter()
    r = _uma_execucao(provedor, pergunta, prompt)
    r["tentativas"] = 1
    if not r["resposta"] and not r["chamadas"]:      # modelo pequeno às vezes devolve mensagem vazia
        r = _uma_execucao(provedor, pergunta, prompt)
        r["tentativas"] = 2
    r["latencia_s"] = round(time.perf_counter() - inicio, 2)
    return r


if __name__ == "__main__":
    import argparse
    from agente.providers import PROVEDORES
    ap = argparse.ArgumentParser(description="Conversa com o agente da La Tavola")
    ap.add_argument("pergunta")
    ap.add_argument("--provedor", choices=PROVEDORES, default="claude")
    ap.add_argument("--prompt", choices=PROMPTS, default="v2")
    a = ap.parse_args()
    r = rodar_agente(PROVEDORES[a.provedor](), a.pergunta, a.prompt)
    for c in r["chamadas"]:
        print(f"[ferramenta] {c['nome']}({c['args']})")
    print(r["resposta"], f"\n({r['passos']} passos, {r['latencia_s']} s)")
