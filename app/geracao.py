"""Geração da resposta com um LLM pequeno na CPU. Isolada: dá para trocar por uma API depois."""
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODELO_LLM = os.getenv("MODELO_LLM", "Qwen/Qwen2.5-1.5B-Instruct")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "150"))

SYSTEM = ("Você é o assistente de atendimento da La Tavola, uma pizzaria italiana. "
          "Responda somente com informações que estejam escritas nos trechos fornecidos. "
          "Nunca use conhecimento próprio e nunca suponha. "
          "Se os trechos não trouxerem a informação pedida de forma explícita, responda exatamente: "
          "\"Não encontrei essa informação. Sugiro falar com o atendimento.\" "
          "Responda em português, de forma curta.")


def montar_mensagens(pergunta: str, trechos: list[dict]) -> list[dict]:
    contexto = "\n\n".join(f"[{t['arquivo']} - {t['secao']}]\n{t['texto']}" for t in trechos)
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Trechos:\n{contexto}\n\nPergunta: {pergunta}"}]


class Gerador:
    def __init__(self, modelo: str = MODELO_LLM):
        self.tok = AutoTokenizer.from_pretrained(modelo)
        self.llm = AutoModelForCausalLM.from_pretrained(modelo, dtype=torch.float32)  # versões antigas: torch_dtype
        self.llm.eval()

    def gerar(self, pergunta: str, trechos: list[dict]) -> str:
        texto = self.tok.apply_chat_template(montar_mensagens(pergunta, trechos),
                                             tokenize=False, add_generation_prompt=True)
        entrada = self.tok([texto], return_tensors="pt")
        with torch.no_grad():
            saida = self.llm.generate(**entrada, max_new_tokens=MAX_TOKENS, do_sample=False,
                                      temperature=None, top_p=None, top_k=None)
        novos = saida[0][entrada["input_ids"].shape[1]:]
        return self.tok.decode(novos, skip_special_tokens=True).strip()
