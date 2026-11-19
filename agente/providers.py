"""Adaptadores: mesma interface para Claude, GPT e Gemini.

Cada adaptador guarda o histórico no formato nativo da sua API. O loop em agente.py só usa:
  iniciar(sistema, pergunta) -> passo() -> (texto, chamadas) -> enviar_resultados(chamadas, resultados)
Uma chamada é um dict {"id", "nome", "args"}.
Nomes de modelo vêm de variáveis de ambiente (MODELO_CLAUDE, MODELO_OPENAI, MODELO_GEMINI):
confira os nomes atuais na documentação de cada provedor.
"""
import json
import os

from agente.tools import SCHEMAS


class Provedor:
    nome = "base"
    def iniciar(self, sistema: str, pergunta: str): raise NotImplementedError
    def passo(self) -> tuple[str, list[dict]]: raise NotImplementedError
    def enviar_resultados(self, chamadas: list[dict], resultados: list[dict]): raise NotImplementedError


class Claude(Provedor):
    nome = "claude"

    def __init__(self, modelo: str | None = None):
        import anthropic
        self.cli = anthropic.Anthropic()                       # lê ANTHROPIC_API_KEY
        self.modelo = modelo or os.getenv("MODELO_CLAUDE", "claude-haiku-5-5")
        self.tools = [{"name": s["name"], "description": s["description"], "input_schema": s["parameters"]}
                      for s in SCHEMAS]

    def iniciar(self, sistema, pergunta):
        self.sistema, self.msgs = sistema, [{"role": "user", "content": pergunta}]

    def passo(self):
        r = self.cli.messages.create(model=self.modelo, max_tokens=800, system=self.sistema,
                                     tools=self.tools, messages=self.msgs)
        self.msgs.append({"role": "assistant", "content": r.content})
        texto = "".join(b.text for b in r.content if b.type == "text")
        chamadas = [{"id": b.id, "nome": b.name, "args": b.input} for b in r.content if b.type == "tool_use"]
        return texto, chamadas

    def enviar_resultados(self, chamadas, resultados):
        self.msgs.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": c["id"], "content": json.dumps(r, ensure_ascii=False)}
            for c, r in zip(chamadas, resultados)]})


class OpenAI(Provedor):
    nome = "openai"

    def __init__(self, modelo: str | None = None):
        from openai import OpenAI as Cliente
        self.cli = Cliente()                                   # lê OPENAI_API_KEY
        self.modelo = modelo or os.getenv("MODELO_OPENAI", "gpt-4o-mini")
        self.tools = [{"type": "function", "function": s} for s in SCHEMAS]

    def iniciar(self, sistema, pergunta):
        self.msgs = [{"role": "system", "content": sistema}, {"role": "user", "content": pergunta}]

    def passo(self):
        m = self.cli.chat.completions.create(model=self.modelo, tools=self.tools, messages=self.msgs,
                                             temperature=0, seed=0).choices[0].message
        self.msgs.append(m.model_dump(exclude_none=True))
        chamadas = [{"id": c.id, "nome": c.function.name, "args": json.loads(c.function.arguments or "{}")}
                    for c in (m.tool_calls or [])]
        return m.content or "", chamadas

    def enviar_resultados(self, chamadas, resultados):
        for c, r in zip(chamadas, resultados):
            self.msgs.append({"role": "tool", "tool_call_id": c["id"],
                              "content": json.dumps(r, ensure_ascii=False)})


class Gemini(Provedor):
    nome = "gemini"

    def __init__(self, modelo: str | None = None):
        from google import genai
        from google.genai import types
        self.t = types
        self.cli = genai.Client()                              # lê GEMINI_API_KEY / GOOGLE_API_KEY
        self.modelo = modelo or os.getenv("MODELO_GEMINI", "gemini-2.0-flash")
        self.tools = [types.Tool(function_declarations=[types.FunctionDeclaration(**s) for s in SCHEMAS])]

    def iniciar(self, sistema, pergunta):
        t = self.t
        self.cfg = t.GenerateContentConfig(
            system_instruction=sistema, tools=self.tools, temperature=0.0,
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True))
        self.msgs = [t.Content(role="user", parts=[t.Part.from_text(text=pergunta)])]

    def passo(self):
        r = self.cli.models.generate_content(model=self.modelo, contents=self.msgs, config=self.cfg)
        self.msgs.append(r.candidates[0].content)
        chamadas = [{"id": c.name, "nome": c.name, "args": dict(c.args or {})} for c in (r.function_calls or [])]
        return r.text or "", chamadas

    def enviar_resultados(self, chamadas, resultados):
        t = self.t
        self.msgs.append(t.Content(role="user", parts=[
            t.Part.from_function_response(name=c["nome"], response={"resultado": r})
            for c, r in zip(chamadas, resultados)]))


class Roteirizado(Provedor):
    """Modelo falso para testar o loop sem API: executa um roteiro [(texto, chamadas), ...]."""
    nome = "roteirizado"

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)

    def iniciar(self, sistema, pergunta): self.recebidos = []
    def passo(self): return self.roteiro.pop(0)
    def enviar_resultados(self, chamadas, resultados): self.recebidos.append(resultados)


PROVEDORES = {"claude": Claude, "openai": OpenAI, "gemini": Gemini}
