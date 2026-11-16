# Projeto 2 - La Tavola: Passo 2b (segunda versão do prompt, para a recusa)
# COLE NO MESMO NOTEBOOK, DEPOIS DA CÉLULA 12 (usa responder, gerar, montar_contexto, perguntas, etc.).
# ATENÇÃO: o prompt v1 já foi medido. Se você adotar o v2, descreva no README as DUAS versões
# e use os números do v2 só depois de rodar TODAS as 27 perguntas (RODAR = "todas").

# %% [célula 13] Prompt v2 e nova rodada
SYSTEM_V2 = ("Você é o assistente de atendimento da La Tavola, uma pizzaria italiana. "
             "Responda somente com informações que estejam escritas nos trechos fornecidos. "
             "Nunca use conhecimento próprio e nunca suponha. "
             "Se os trechos não trouxerem a informação pedida de forma explícita, responda exatamente: "
             "\"Não encontrei essa informação. Sugiro falar com o atendimento.\" "
             "Responda em português, de forma curta.")

# perguntas NOVAS sem resposta (não foram usadas para ajustar o prompt) - relate-as à parte no README
EXTRAS_SEM_RESPOSTA = ["Vocês têm Wi-Fi para os clientes?",
                       "Qual é o CNPJ da La Tavola?",
                       "Vocês organizam festa de casamento?"]

RODAR = "so_recusa"   # "so_recusa": 3 originais + 3 novas (~2 min) | "todas": as 27 + 3 novas (~11 min)

def responder_v2(pergunta):
    indices = recuperar(pergunta)
    contexto = montar_contexto(indices)
    msgs = [{"role": "system", "content": SYSTEM_V2},
            {"role": "user", "content": f"Trechos:\n{contexto}\n\nPergunta: {pergunta}"}]
    t0 = time.time()
    resposta = gerar(msgs)
    return {"resposta": resposta, "segundos": round(time.time() - t0, 1),
            "fontes": [trechos[i]["secao"] for i in indices]}

lote = [(q["id"], q["tipo"], q["pergunta"]) for q in perguntas
        if RODAR == "todas" or q["tipo"] == "sem_resposta"]
lote += [(f"extra{i+1}", "sem_resposta_nova", p) for i, p in enumerate(EXTRAS_SEM_RESPOSTA)]

saida_v2 = []
for id_, tipo, pergunta in lote:
    out = responder_v2(pergunta)
    out.update({"id": id_, "tipo": tipo, "pergunta": pergunta,
                "dica_recusa_automatica": parece_recusa(out["resposta"]), "avaliacao_manual": ""})
    saida_v2.append(out)
    print(f"#{id_} [{tipo}] {pergunta}\n   -> {out['resposta']}\n   {out['fontes']} | {out['segundos']}s\n")

(BASE / "eval" / "respostas_geracao_v2.json").write_text(
    json.dumps({"modelo_llm": MODELO_LLM, "prompt": SYSTEM_V2, "rodar": RODAR, "respostas": saida_v2},
               ensure_ascii=False, indent=2), encoding="utf-8")
print("salvo em eval/respostas_geracao_v2.json")
