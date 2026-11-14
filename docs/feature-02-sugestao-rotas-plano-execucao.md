# Feature 02 + 08 · Plano de execução da sugestão de rotas e análise de perigo

14/11/2026 · Hugo · base: [`feature-08-agente-local.md`](feature-08-agente-local.md), [`feature-08-voz-plano-execucao.md`](feature-08-voz-plano-execucao.md) e `api/route_planning.py`

## Objetivo

O agente **ajuda o astronauta a decidir; ele não decide no lugar dele.** Diante de um destino, o sistema mostra **todas** as rotas, inclusive as perigosas. Cada rota vem com prós, contras, fontes e uma sugestão de ordem com o porquê. Quem escolhe é o astronauta, sempre.

Durante a caminhada, o sistema compara o que foi previsto com o que está acontecendo. Se o O2 estiver acabando mais rápido que o previsto, ou se houver uma emergência, ele recalcula e oferece **opções de volta**, não uma ordem.

Tudo por voz e offline: o astronauta fala, o Whisper transcreve e ninguém digita.

```
"Guia, rota até Altadena"  ─▶ /api/route (todas as variantes)
   ─▶ perfil de margem de volta por rota (pior caso)
   ─▶ rótulo ✅ / ⚠️ / ⛔ + prós e contras por regra
   ─▶ mapa mostra todas · voz lê a sugestão e termina com "a escolha é sua"
   ─▶ "Guia, vou pela rota segura" ─▶ confirma ─▶ rota ativa

durante a rota:
"Guia, oxigênio 62 por cento" ─▶ checkpoint ─▶ recalcula com a taxa medida
   ─▶ margem caiu? ─▶ avisa + oferece 2 opções de volta
"Guia, emergência" / "Guia, voltar agora" ─▶ opções de volta a partir da posição atual
```

## Princípios (e por quê)

| Princípio | Como aparece | Por quê |
| --- | --- | --- |
| O humano decide | Nenhuma rota é escondida nem bloqueada. A rota ⛔ aparece com os trechos e as fontes | O agente é ferramenta de apoio. Ocultar uma opção já é decidir pelo astronauta |
| Toda rota é julgada **pela volta** | Em cada ponto: "se algo der errado aqui, consigo voltar?" | Uma emergência acontece no meio do caminho, não no destino |
| Pior caso, não média | O O2 vem em faixa (otimista–pessimista), e a sugestão usa o pessimista | Um cálculo de O2 pode errar. O erro tem que cair para o lado seguro |
| O número vem da regra, nunca do modelo | Rótulo, margem, prós e contras saem de `sugestao_rotas.py`; o Gemma só lê em voz alta | Mesmo princípio dos alertas da F08 |
| Sem dado, sem número | O2 não informado → "sem dado para saber se você volta", e não um valor suposto | CLAUDE.md: nunca inventar valor |
| Toda frase tem fonte | DTM HiRISE, histórico do rover, REMS/RAD, consumo Apollo, valor informado por voz | Contrato de todas as features |

## Fase 0 · Decisões do time antes de codar

| Decisão | Opções | Situação |
| --- | --- | --- |
| Folga mínima de O2 para ⚠️ e para ⛔ | p. ex. abaixo de 30 % → ⚠️, abaixo de 15 % → ⛔ | **Em aberto.** Precisa de fonte (procedimento NASA/Artemis) ou de ser declarada como "proposta H2G2" |
| O2 inicial do traje | Falado pelo astronauta no começo da EVA ("Guia, oxigênio cheio" / "oxigênio 100 por cento") | **Em aberto:** capacidade em litros do traje. Sem ela, a margem é dada só em % e em tempo |
| Reserva de emergência do traje (O2 secundário) | Entra com número e fonte, ou fica de fora | **Em aberto.** Não entra sem fonte |
| Variante `mais_direta` (permite trechos acima de 20°) | Sim: é a "opção perigosa" visível · Não: só rotas dentro do limite | **Em aberto.** Sem ela, a lista nunca tem uma rota ⛔ por inclinação |
| Trilha do Curiosity como "terreno conhecido" | Custo menor no A* da volta · só aviso | Sugestão: começar só como aviso |

## Fase 1 · O2 em faixa e consumo que cresce na subida (1h)

**`api/route_planning.py`**
- Hoje `TAXA_O2_L_POR_MIN = 0.84` é fixo. Passa a crescer com a inclinação do trecho, com a fórmula declarada e a fonte no comentário.
- `_monta_rota` ganha `o2_estimado_l_faixa: {otimista, pessimista}`. A chave `o2_estimado_l` continua, com o mesmo valor de hoje (o contrato não muda).
- O pessimista usa uma velocidade menor e um consumo maior. Os dois fatores ficam em constantes no topo do arquivo, com a fonte.

**Teste:** rota plana → faixa estreita; rota com 15° → pessimista maior que otimista; `o2_estimado_l` igual ao de antes.

## Fase 2 · Mapa de custo de volta (1h30)

**`api/route_planning.py`, função nova `custo_ate_base()`**
- Um Dijkstra **a partir da base** no mesmo grid e com as mesmas regras de custo do A*. Devolve, por pixel, `tempo_volta_s` e `o2_volta_l` (pessimista).
- Calculado uma vez e guardado em cache (`functools.lru_cache`), porque o DTM e a base não mudam.
- Se ficar lento em Python puro: recortar o grid ao raio de 2.000 m da base, que já é o limite da regra `volta_base`.
- Pixel sem caminho até a base → `None` ("sem volta calculável daqui"), nunca infinito disfarçado de número.

**Fase 0 da fase:** medir o tempo do Dijkstra no grid real antes de seguir.

## Fase 3 · Perfil de margem por rota (1h)

Para cada rota e cada ponto `i`:

```
margem_i = O2_disponível − (O2_gasto_até_i + O2_volta_de_i)      (pior caso)
```

Campos novos em cada item de `rotas` no `/api/route` (só acréscimo):

| Chave | O que é |
| --- | --- |
| `margem_minima` | `{pct, litros, distancia_m}`: o pior ponto da rota. `null` sem O2 informado |
| `ponto_nao_retorno` | `{lat, lon, distancia_m}`: a partir dali, seguir custa menos que voltar. `null` se não houver |
| `pior_trecho_emergencia` | onde a volta é mais longa ou mais íngreme |
| `volta_minutos_max` | o maior tempo de volta ao longo da rota |

Sem O2 informado, `margem_minima` é `null`, mas `volta_minutos_max` e o ponto de não retorno em tempo continuam valendo.

**Entrada:** `/api/route` ganha `o2_disponivel_pct` opcional. Ele vem do estado da EVA (fase 5); a API não guarda sessão.

## Fase 4 · Sugestão com o porquê (1h30)

**Módulo novo `api/sugestao_rotas.py`**, com uma função pública `sugerir(rotas, contexto)`.
- **Rótulo por rota:** ⛔ se houver trecho acima de 20°, margem abaixo do limite ⛔ ou um alerta `perigo` na rota; ⚠️ se houver trechos de atenção, margem abaixo do limite ⚠️, um trecho fora da janela de EVA (F06 `janela_eva`) ou temporada de poeira; senão ✅.
- **Prós e contras:** frases prontas para tela e voz, cada uma com `fonte`. Exemplos:
  - "No pior ponto, você volta com 35 % de folga (consumo Apollo, pior caso)."
  - "9 min mais curta que a segura, mas passa por 3 trechos acima de 15° (DTM HiRISE)."
  - "Passa pelo alvo Altadena (ChemCam, sol …)."
- **Ordem sugerida:** primeiro a maior margem mínima no pior caso, depois o menor número de trechos de atenção, depois o menor tempo, e por fim ciência. O motivo de cada posição vai em `motivo`.
- **Campo novo `sugestao` no `/api/route`:** `{ordem: [tipo…], motivo, aviso: "a decisão é sua"}`. As rotas continuam todas em `rotas`.

**`api/agente.py`**: `contexto_em_texto` ganha um bloco ROTAS com o resumo de cada uma (rótulo, prós, contras). A instrução do modelo ganha uma linha: "Sugira, explique e termine dizendo que a escolha é do astronauta. Nunca diga que uma rota é proibida nem esconda uma opção."

**Front (`web/ui/rota.js`)**: desenha todas as rotas, com a ⛔ tracejada em vermelho. Mostra o ponto de não retorno no mapa e um cartão por rota com prós e contras. O botão "escolher" aparece em todas, inclusive na ⛔.

## Fase 5 · Durante a rota: checkpoints por voz (1h30)

**Intenções novas em `interpretar()` (`api/voz.py`, regras primeiro, como na F08):**

| Fala | Intenção | Confirmação |
| --- | --- | --- |
| "Guia, oxigênio 62 por cento" / "oxigênio cheio" | `informar_o2` com `{pct}` | "Entendi: oxigênio 62 %. Confirma?" O número nunca entra sem o "sim" |
| "Guia, vou pela rota segura" | `escolher_rota` com `{tipo}` | sim |
| "Guia, como está minha margem?" | `status_rota` | não precisa |
| "Guia, voltar agora" / "Guia, emergência" | `voltar` | **não espera confirmação para mostrar as opções**, só para ativar uma delas |

**Estado da EVA no front** (o mesmo padrão de `setSolEva`): rota ativa, posição atual (ponto marcado ou parada mais próxima, já que não há GPS), último O2 informado e quando.

**Checkpoint:** com dois valores de O2 informados, calcula a **taxa real** (L/min ou %/min). Se ela passar do pessimista, refaz a margem com a taxa medida e avisa por regra:
> "Você está gastando 30 % mais que o previsto. Nesse ritmo, o ponto de não retorno fica a 150 m daqui."

**Sem O2 informado há mais de N minutos:** o agente pergunta por voz ("Guia aqui: qual seu oxigênio agora?"). N fica a definir.

## Fase 6 · Emergência: "voltar agora" (1h)

- Usa o mapa de custo de volta da fase 2: a resposta é imediata.
- Oferece **duas** voltas a partir da posição atual: a **mais curta** e a **mais suave** (sem trechos de atenção). Cada uma com tempo, O2 pessimista, inclinação máxima e fonte.
- A fala começa pelo que é urgente: "Volta mais curta: 18 min, passa por 15°. Volta mais suave: 25 min, sem trechos de atenção. Qual?"
- Se só uma volta couber no O2 informado, isso é dito: "Só a mais curta cabe no seu oxigênio no pior caso." A outra continua sendo mostrada.
- Atraso com a Terra (4 a 24 min): tudo roda local. A Terra recebe o registro depois (F09).

## Testes

- `api/test_sugestao_rotas.py` (com `assert`, como os outros):
  - rota com trecho acima de 20° → ⛔ e **continua na lista**;
  - sem O2 informado → `margem_minima: null` e a frase "sem dado para saber se você volta";
  - margem pessimista menor que a otimista;
  - ordem: a de maior margem vem primeiro, e o motivo cita a margem;
  - `sugestao.aviso` sempre presente;
  - chaves antigas do `/api/route` (`o2_estimado_l`, `tempo_estimado_min`, …) iguais às de antes.
- `api/test_voz.py`: "oxigênio 62 por cento" → `informar_o2` com 62; "oxigênio cheio" → 100; "voltar agora" → `voltar`.
- Checkpoint: dois valores de O2 com uma taxa acima do pessimista → aviso emitido e margem recalculada.
- **Aceitação (Wi-Fi desligado):** "Guia, rota até Altadena" → todas as rotas no mapa com rótulos → a sugestão é lida e termina com "a escolha é sua" → "Guia, vou pela rota rápida" → "sim" → "Guia, oxigênio 40 por cento" → aviso de margem → "Guia, voltar agora" → duas opções de volta.

## Ordem de entrega

1 → 2 → 3 → 4 já entregam a sugestão completa (pode ser testada clicando, antes da voz). Depois, 5 e 6 entregam o "durante a rota" e a emergência por voz, em cima do Whisper da F08.

## Riscos

| Risco | Plano B |
| --- | --- |
| Dijkstra em Python lento no grid inteiro | Recortar ao raio de 2 km da base. Se ainda estiver lento, usar `scipy.sparse.csgraph.dijkstra`, se o SciPy já estiver instalado |
| Whisper ouve "52" em vez de "62" | Confirmação obrigatória do número e repetição em voz alta antes de usar |
| Modelo de consumo de O2 muito simples | Faixa com pior caso, a taxa real substitui a estimada a partir do segundo checkpoint, e a fonte é dita sempre |
| Sem GPS: a posição atual é aproximada | Ponto marcado no mapa ou "estou na parada do sol …" por voz; a incerteza é dita na resposta |
| Rotas demais confundem na voz | A voz lê só a sugerida e uma alternativa; o mapa mostra todas |
| Limites de folga sem fonte oficial | Declarados como "proposta H2G2" na fonte da frase, até haver referência |
