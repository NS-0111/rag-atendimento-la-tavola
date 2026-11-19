# Agente de atendimento da La Tavola (tool calling + avaliação multi-modelo)

Evolução do assistente RAG: em vez de sempre buscar e responder, o modelo **decide** qual ferramenta usar.

| Ferramenta | O que faz |
|---|---|
| `buscar_informacoes` | usa a busca híbrida do RAG (`app/busca.py`) |
| `calcular_pedido` | subtotal, taxa de entrega, mínimo e desconto de retirada, seguindo o FAQ |
| `verificar_horario` | diz se a pizzaria funciona em um dia/hora |

## Estrutura
- `tools.py`: funções + schemas neutros das ferramentas
- `prompts.py`: prompts v1 (simples) e v2 (estruturado com tags XML)
- `providers.py`: adaptadores Claude / OpenAI / Gemini com a mesma interface
- `agente.py`: loop do agente (`python -m agente.agente "pergunta" --provedor claude`)
- `eval_agente.py`: roda `eval/casos_agente.json` em cada modelo e prompt e imprime a tabela

## Como rodar
```bash
pip install -r agente/requirements.txt            # só os provedores que for usar
export ANTHROPIC_API_KEY=...                       # e/ou OPENAI_API_KEY, GEMINI_API_KEY
python -m agente.agente "Quanto fica 1 Margherita grande com borda, entrega a 4 km?"
python -m agente.eval_agente --provedores claude openai gemini --prompts v1 v2
```
Testes sem API: `pytest tests/test_agente.py`.

## Resultados
(preencher com a tabela gerada por `eval_agente.py`)
