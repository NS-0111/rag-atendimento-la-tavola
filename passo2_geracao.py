# Projeto 2 - La Tavola: Passo 2 (gerar a resposta com o LLM)
# COLE ESTAS CÉLULAS NO MESMO NOTEBOOK, DEPOIS DA CÉLULA 8 do busca_e_avaliacao.py.
# Elas usam variáveis que as células 1 a 8 já criaram (BASE, trechos, perguntas,
# busca_hibrida, posicao_certa, normalizar). Se a sessão reiniciou, rode as
# células 1 a 6 de novo antes destas (a 7 e a 8 não são necessárias).

# %% [célula 9] Carregar o LLM na CPU (a primeira vez baixa o modelo)
import json, time, torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODELO_LLM = "Qwen/Qwen2.5-1.5B-Instruct"   # mais rápido e menos preciso: "Qwen/Qwen2.5-0.5B-Instruct"
K_TRECHOS = 3                               # quantos trechos vão para o prompt
MAX_TOKENS = 150                            # respostas curtas

tok = AutoTokenizer.from_pretrained(MODELO_LLM)
llm = AutoModelForCausalLM.from_pretrained(MODELO_LLM, dtype=torch.float32)  # em versões antigas: torch_dtype
llm.eval()
print("modelo carregado:", MODELO_LLM, "| threads de CPU:", torch.get_num_threads())

# %% [célula 10] Prompt e geração (decodificação gulosa: sem sorteio)
SYSTEM = ("Você é o assistente de atendimento da La Tavola, uma pizzaria italiana. "
          "Responda somente com base nos trechos fornecidos. Se a resposta não estiver "
          "nos trechos, diga que não encontrou a informação e sugira falar com o "
          "atendimento. Responda em português, de forma curta.")

def recuperar(pergunta, k=K_TRECHOS):
    """Busca híbrida (BM25 + embeddings): devolve os índices dos k melhores trechos."""
    return busca_hibrida(pergunta)[:k]

def montar_contexto(indices):
    return "\n\n".join(f"[{trechos[i]['arquivo']} - {trechos[i]['secao']}]\n{trechos[i]['texto']}"
                       for i in indices)

def montar_mensagens(pergunta, indices):
    contexto = montar_contexto(indices)
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Trechos:\n{contexto}\n\nPergunta: {pergunta}"}]

def gerar(mensagens, max_new_tokens=MAX_TOKENS):
    texto = tok.apply_chat_template(mensagens, tokenize=False, add_generation_prompt=True)
    entrada = tok([texto], return_tensors="pt")
    with torch.no_grad():
        saida = llm.generate(**entrada, max_new_tokens=max_new_tokens, do_sample=False,
                             temperature=None, top_p=None, top_k=None)
    novos = saida[0][entrada["input_ids"].shape[1]:]
    return tok.decode(novos, skip_special_tokens=True).strip()

def responder(pergunta):
    """Faz o que a API vai fazer no Passo 3: busca, gera e devolve resposta + fontes."""
    indices = recuperar(pergunta)
    t0 = time.time()
    resposta = gerar(montar_mensagens(pergunta, indices))
    return {"resposta": resposta,
            "fontes": [{"arquivo": trechos[i]["arquivo"], "secao": trechos[i]["secao"]} for i in indices],
            "segundos": round(time.time() - t0, 1)}

# teste rápido (a primeira geração é a mais lenta)
print(responder("Qual o prazo do reembolso?"))

# %% [célula 11] Rodar as 27 perguntas e salvar (leva alguns minutos na CPU)
def parece_recusa(resposta):
    """Só uma DICA automática; a conferência que vale é a manual."""
    r = normalizar(resposta)
    return "nao encontr" in r

resultados_geracao = []
for q in perguntas:
    out = responder(q["pergunta"])
    if q["tipo"] == "sem_resposta":
        certa_no_topo = None          # não há seção certa
    else:
        certas = {(e["arquivo"], e["secao"]) for e in q["esperadas"]}
        certa_no_topo = any((f["arquivo"], f["secao"]) in certas for f in out["fontes"])
    registro = {"id": q["id"], "tipo": q["tipo"], "pergunta": q["pergunta"], **out,
                "secao_certa_nos_3_trechos": certa_no_topo,
                "dica_recusa_automatica": parece_recusa(out["resposta"]),
                "avaliacao_manual": ""}   # você preenche: correta / parcial / errada
    resultados_geracao.append(registro)
    print(f"#{q['id']} [{q['tipo']}] {q['pergunta']}\n   -> {out['resposta']}\n"
          f"   fontes: {[f['secao'] for f in out['fontes']]} | {out['segundos']}s | "
          f"seção certa nos 3 trechos: {certa_no_topo}\n")

(BASE / "eval" / "respostas_geracao.json").write_text(
    json.dumps({"modelo_llm": MODELO_LLM, "k_trechos": K_TRECHOS, "max_tokens": MAX_TOKENS,
                "busca": "híbrida (BM25 + embeddings, RRF)", "respostas": resultados_geracao},
               ensure_ascii=False, indent=2), encoding="utf-8")
print("salvo em eval/respostas_geracao.json")

# %% [célula 12] Resumo
com = [r for r in resultados_geracao if r["tipo"] != "sem_resposta"]
sem = [r for r in resultados_geracao if r["tipo"] == "sem_resposta"]
tempos = [r["segundos"] for r in resultados_geracao]
print(f"seção certa nos 3 trechos: {sum(r['secao_certa_nos_3_trechos'] for r in com)} de {len(com)}")
print(f"sem resposta (dica automática de recusa): {sum(r['dica_recusa_automatica'] for r in sem)} de {len(sem)}")
print(f"tempo por resposta: média {sum(tempos)/len(tempos):.1f}s, máximo {max(tempos):.1f}s (CPU do Kaggle; anote isso no README)")
