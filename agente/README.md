# Agente de atendimento da La Tavola (tool calling + avaliação multi-modelo)

Evolução do assistente RAG: em vez de sempre buscar e responder, o modelo **decide** qual ferramenta usar.

| Ferramenta | O que faz |
|---|---|
| `buscar_informacoes` | usa a busca híbrida do RAG (`app/busca.py`) |
| `calcular_pedido` | subtotal, taxa de entrega, mínimo e desconto de retirada, seguindo o FAQ |
| `verificar_horario` | diz se a pizzaria funciona em um dia/hora |

## Estrutura
- `tools.py`: funções + schemas neutros das ferramentas
- `prompts.py`: quatro versões de prompt de sistema (v1 a v4, descritas abaixo)
- `providers.py`: adaptadores Claude / OpenAI / Gemini com a mesma interface
- `agente.py`: loop do agente (`python -m agente.agente "pergunta" --provedor claude`)
- `eval_agente.py`: roda `eval/casos_agente.json` em cada modelo e prompt e imprime a tabela

## Como rodar
```bash
python -m venv .venv && source .venv/bin/activate
pip install openai            # ou anthropic / google-genai, conforme o provedor
```

**Sem API paga (Ollama, modelo local):** o adaptador `openai` funciona com qualquer servidor compatível.
```bash
ollama pull qwen2.5:3b
export OPENAI_BASE_URL="http://localhost:11434/v1" OPENAI_API_KEY="ollama" MODELO_OPENAI="qwen2.5:3b"
python -m agente.agente "Quanto fica 1 Margherita grande com borda, entrega a 4 km?" --provedor openai --prompt v4
```

**Avaliação** (use `--provedores claude openai gemini` para comparar modelos):
```bash
python -m agente.eval_agente --provedores openai --prompts v1 v2 v3 v4
python -m agente.eval_agente --provedores openai --prompts v1 v2 v3 v4 --casos eval/casos_agente_heldout.json
```
Testes sem API: `pytest tests/test_agente.py`.

## Prompts comparados
| Versão | Descrição |
|---|---|
| v1 | simples: papel, uso de ferramentas e idioma |
| v2 | estruturado (tags XML), regras explícitas e frase fixa de recusa |
| v3 | v2 com a recusa limitada a perguntas factuais e regra para refazer a chamada após erro |
| v4 | recusa só depois de buscar, mais 3 exemplos (de temas fora dos casos de teste) |

## Resultados

Modelo: Qwen2.5-3B-Instruct (`qwen2.5:3b`, Ollama), temperatura 0, seed 0. Cada conjunto tem 10 casos.
O **conjunto original** foi usado durante o desenvolvimento (prompts e ferramentas foram ajustados olhando suas falhas).
O **conjunto reservado** (`casos_agente_heldout.json`) foi escrito depois, e nenhum prompt foi alterado a partir dele.

**Conjunto original**

| Prompt | Ferramenta certa | Conteúdo certo | Passou | Recusa indevida |
|---|---|---|---|---|
| v1 | 80% | 70% | 70% | 0% |
| v2 | 60% | 40% | 30% | 67% |
| v3 | 60% | 70% | 60% | 22% |
| v4 | 70% | 60% | 50% | 22% |

**Conjunto reservado**

| Prompt | Ferramenta certa | Conteúdo certo | Passou | Recusa indevida |
|---|---|---|---|---|
| v1 | 90% | 80% | 80% | 0% |
| v2 | 40% | 50% | 40% | 33% |
| v3 | 70% | 70% | 60% | 11% |
| v4 | 80% | 90% | 80% | 11% |

**Total (20 casos), "passou":** v1 75%, v2 35%, v3 60%, v4 65%.
"Recusa indevida" = % das perguntas com resposta nos documentos em que o agente disse "Não encontrei".
Critérios de cada caso: ferramentas obrigatórias chamadas, ferramentas proibidas não chamadas e trecho esperado na resposta.

### O que os dados sustentam
- **O v2 foi o pior nos dois conjuntos** (35% no total) e recusou 6 de 9 perguntas respondíveis no conjunto original. Mais regras no prompt não ajudaram o modelo pequeno.
- **v3 e v4 reduziram a recusa excessiva** para 1 ou 2 de 9 perguntas por conjunto.
- **v1 e v4 empataram no conjunto reservado (80%)**, e o v1 ficou à frente no original. Com 10 casos por conjunto, 10 pontos percentuais equivalem a um caso, então não dá para afirmar qual dos dois é melhor.
- **O prompt mais simples foi competitivo** em acertos, mas nunca recusa (0%). Durante o desenvolvimento ele inventou uma resposta sobre estacionamento, que não existe nos documentos.
- **Os resultados são estáveis:** o v1 e o v2 repetiram 70% e 30% entre rodadas com a ferramenta alterada (temperatura 0).

### Tipos de falha observados durante o desenvolvimento
1. **Argumentos errados:** omitir `itens` (obrigatório), colocar `distancia_km` dentro da lista de itens ou trocar o tamanho de uma pizza (grande por gigante).
2. **Ferramenta errada:** usar `calcular_pedido` para uma pergunta sobre a área de entrega.
3. **Recusa-padrão:** repetir a frase "Não encontrei essa informação" sem buscar, e até depois de erro de ferramenta.
4. **Alucinação sem ferramenta** (no prompt v1).

Mensagens de erro da ferramenta em português claro (em vez de `TypeError`) passaram a permitir a correção pelo modelo.

### Limitações
- Poucos casos (20) e um único modelo pequeno; sem intervalo de confiança.
- Os casos foram escritos com auxílio de um assistente de IA, o mesmo processo que ajudou a desenhar os prompts, o que pode favorecê-los.
- A latência do v1 está inflada, porque ele roda primeiro e carrega o modelo na memória.
- A ferramenta de cálculo não cobre Funghi, Legumes Grelhados, Salada Caprese, bruschetta sem queijo, pizza doce, vinho e meio a meio.

### Próximos passos
- Rodar a mesma avaliação com um modelo maior (Claude, GPT ou Gemini) para comparar modelos.
- Ampliar os casos e cobrir os itens que faltam na ferramenta.
- Testar a hipótese (não verificada) de que citar a frase de recusa literal no prompt induz o modelo a copiá-la.
