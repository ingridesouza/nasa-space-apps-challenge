# Feature 08 · Cartão de resposta (substitui o modal da ficha científica)

15/11/2026 · Victoria

## Por quê

O foco do H2G2 deixou de ser planejar a rota (não é um "Waze de Marte") e passou a ser **apoiar a decisão do astronauta durante o trajeto**. A ficha científica fixa ocupava espaço e quase não era usada. O modal dela virou o **cartão de resposta**: quando o astronauta pergunta algo ao agente, a resposta chega estruturada (veredito, fatos com fonte, opções), não como um parágrafo.

## Princípio

**As regras montam o cartão; o modelo só escreve a linha de resposta.**

- Todo bloco vem de dado local (alertas, DTM, THEMIS, histórico do rover, REMS/RAD, previsão, rota). Nenhum número vem do modelo.
- O cartão é montado **antes** da chamada ao modelo. Se o Ollama cair, ele chega mesmo assim (503 com `detail.card`), só sem a linha de resposta.
- Nenhum alerta nunca vira "GO": sem regra disparada, o veredito é **NO ALERT** ("não significa seguro"). Sem dado, o veredito é **NO DATA**.

## Contrato (`/api/ask` → `card`; chaves antigas mantidas)

```json
{
  "intent": "terrain_here | resources | environment | science | route | distress | other",
  "title": "Terrain here",
  "verdict": {"level": "stop|caution|no_alert|unknown", "label": "STOP", "because": [{"text", "source"}], "note"},
  "facts": [{"label", "value", "source", "confidence", "hint"}],
  "options": [{"n", "type", "name", "status", "why", "suggested"}],
  "target": "saída de /science/card (só na intenção science)",
  "missing": ["o que faltou para responder"],
  "answer": "linha do modelo (sem o prefixo Danger:, que fica no veredito)"
}
```

`verdict` é `null` na intenção science: informação, não decisão.

## Intenções (palavra-chave, lista fechada, a primeira que casar vence)

| Intenção | Exemplo | Fatos | Veredito decidido por |
|---|---|---|---|
| `route` | "Which route should I take?" | rota aberta, pior trecho, estação de poeira | alertas da rota; as **opções** vêm da sugestão (`route_suggestions.py`) |
| `environment` | "Is the radiation high?" | temperatura, pressão, RAD, previsão do sol | `stale_data`, `dust_season` |
| `resources` | "How long until I turn back?" | base (distância e rumo), rota, janela de EVA, dose | `return_to_base` |
| `terrain_here` | "Can I climb here?" | inclinação no mapa, chance pelo histórico, medição do rover ≤ 100 m, inércia térmica | inclinação, histórico, sem histórico, risco previsto |
| `science` | "What is this rock?" | alvo, mineralogia/química, CRISM; "Science details ›" abre a ficha inteira | — |
| `distress` | "I fell" | posição, inclinação, base | procedimento fixo (regex `DISTRESS` do agente) |
| `other` | qualquer outra | inclinação + base | todos os alertas do ponto |

## Front

- `web/ui/answer-card.js`: renderiza o cartão em `#c-answer`. A ordem dos blocos é: linha de resposta → opções → motivos do veredito → fatos → sem dado. A paginação (F11) mantém as opções juntas na primeira página.
- Sem pergunta, o cartão mostra a ficha científica do destino da rota (comportamento antigo, `science-card.js` reaproveitado).
- Tocar numa opção seleciona a variante no card de rota. A decisão é sempre do astronauta.
- O bloco de voz `m-F` (altair) passou a apontar para `#c-answer`, com o nome "Answer card".
- O painel do assistente (`m-G`) continua com o histórico e o contador de espera.

## Fora desta entrega

- Cartão de **obstáculo** (evento, não pergunta): depende do contrato do replan, que está em outro escopo.
- Classificação de intenção pelo modelo.
- Gráficos no cartão, histórico de várias trocas, monitoramento proativo.
