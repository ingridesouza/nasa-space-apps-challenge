# O que o H2G2 realmente faz hoje — e checklist pro hackathon

15/11/2026 · Ingride (com apoio do Claude) · **Baseado no código que está rodando, não nos planos (.md).** Todo item abaixo foi conferido em `api/` e `web/` nesta data — quando um plano antigo (`docs/raio-x-implementacao.md`, de 14/11) dizia uma coisa que o código já não confirma mais (ex.: "o assistente não é de voz"), isso está marcado aqui como corrigido.

Objetivo deste documento: um lugar só, simples, que diz **o que existe de verdade**, **de onde vem cada dado**, **como é calculado** (quando é cálculo) e **o que ainda falta** — pra fechar as pontas soltas antes da apresentação.

---

## 1. Objetivo do projeto, em uma frase

**Ajudar um astronauta a decidir com segurança para onde ir e o que fazer durante uma caminhada em Marte (cratera Gale), usando só dado real da NASA, 100% offline — o sistema nunca decide por ele, só informa.**

Isso é o critério que atravessa tudo: nenhuma rota é escondida, nenhum valor é inventado, tudo tem fonte.

---

## 2. O que o sistema faz hoje, feature por feature

### Feature 01 — Mapa em camadas

**O que aparece:** um mapa de ~3×3 km do boxwork (Monte Sharp), com camadas que ligam/desligam: imagem de detalhe (HiRISE, 25 cm), imagem de contexto (CTX, ~6 m), relevo (hillshade), inclinação do terreno, inércia térmica (THEMIS), sol/sombra por hora, atmosfera (um ponto por sol medido).

**De onde vem:** tudo baixado uma vez do Mars Trek/USGS/PDS e salvo local (`data/local/`). Nenhuma chamada de rede acontece quando o mapa está aberto.

**Código:** `api/main.py` (`/layers`, `/tiles/...`, `/api/insolation`), `api/thermal.py`, `api/atmosphere.py`, `api/mosaics.py`.

---

### Feature 02 — Rota inteligente + indicadores de risco

**O que aparece:** ao marcar um destino, o sistema devolve até 3 rotas (mais segura, mais rápida, mais ciência), cada uma com: distância, tempo, O2 estimado, gráfico de elevação, trechos coloridos por risco (verde/amarelo/vermelho), margem mínima de oxigênio, e um **ponto de não retorno** no mapa (a partir dali, voltar já não compensa).

**Como é calculado (de verdade, não é só "soma distância"):**
- O caminho em si vem de um algoritmo real de busca (**A\***) sobre o relevo real (DTM HiRISE), penalizando trechos íngremes — `api/route_planning.py:233`.
- O consumo de O2 cresce com a inclinação pela **equação de Pandolf** (Pandolf, Givoni & Goldman, 1977 — citada via um artigo recente do JSC/NASA sobre caminhada em Marte), não por um fator inventado — `api/route_planning.py:86-142`.
- Existe uma **faixa otimista/pessimista** de O2, e a decisão de segurança sempre usa o pior caso.
- Existe um segundo algoritmo (**Dijkstra**) que calcula, pra cada pixel do mapa, "se eu precisar voltar à base a partir daqui, quanto tempo e O2 isso custa" — `api/route_planning.py:292`. É esse cálculo que gera a margem mínima e o ponto de não retorno.
- O rótulo final de cada rota (✅ ok / ⚠️ atenção / ⛔ perigo) e os prós/contras **não vêm de IA** — vêm de uma regra fixa em `api/route_suggestions.py`, pra nunca errar matemática nem esconder perigo.

**De onde vem o dado:** relevo real (USGS/Mars Trek), histórico de inclinação medido pelo próprio rover Curiosity (MMGIS), radiação real (RAD/PDS).

**O que ainda é declarado (não é dado oficial, mas está documentado como tal):** o limite de 30%/15% de margem de O2 pra virar ⚠️/⛔ é uma proposta do time, sem fonte NASA oficial — isso está escrito no próprio código (`route_suggestions.py:21-27`).

---

### Feature 03 + 04 — Fotos/panorama e ficha científica do ponto

**O que aparece:** ao clicar num ponto do mapa, aparecem fotos reais do Curiosity tiradas perto dali (com distância e direção), um panorama 360° quando existe, e uma "ficha científica" com o que foi medido de verdade naquele lugar (química por APXS/ChemCam, mineralogia por CheMin, mineral visto de órbita por CRISM).

**De onde vem:** API pública de imagens do MSL, PDS Geosciences (APXS/ChemCam/CheMin), PDS (CRISM). Tudo baixado e empacotado uma vez (`data-pipeline/f03/etl/build.py`), servido local.

**Código:** `api/panorama.py`, `api/science_card.py`.

**Status:** confirmado funcionando nesta sessão (bug de chave em português no pacote CRISM foi corrigido e testado — ver histórico de commits).

---

### Feature 05 — Painel de condições (clima, radiação, poeira, evento solar)

**O que aparece:** temperatura, pressão, vento (REMS), dose de radiação (RAD), estação de poeira, e um **alerta de evento de partícula solar** quando a dose medida sobe muito acima do normal.

**Como é calculado:** o alerta de evento solar compara a dose de pico medida de verdade (não a média do dia, que dilui o pico) contra um valor de referência, também real — `api/solar_events.py`. Existe um evento real catalogado (sol 242, abril de 2013), buscado diretamente do arquivo oficial da NASA (PDS-PPI), não copiado de um resumo.

**Código:** `api/alerts.py` (`sol_time_and_alerts`), `api/solar_events.py`.

---

### Feature 06 — Previsão climática offline

**O que aparece:** previsão de temperatura, pressão e dose de radiação para qualquer sol, mesmo sem nova medição chegar.

**Como é calculado:** climatologia por estação do ano marciana + o quanto o último dado real medido desviou dessa média (método citado de um artigo acadêmico real, de Cabo-García et al. 2019) — `api/forecast.py:1-33`. O erro foi medido contra dado real (backtest), e está documentado no próprio código: a dose de radiação, por exemplo, segue melhor repetindo o último valor medido do que usando a climatologia, porque quem manda nela é o ciclo solar de 11 anos, não a estação marciana — isso já foi testado e está declarado.

---

### Feature 08 — Assistente por voz + perguntas livres

**O que aparece:** o astronauta pode falar ("Hey Marvin...") e o sistema transcreve localmente (sem internet), interpreta o comando, e responde (em texto e, quando ativado, em voz).

**De onde vem a transcrição:** modelo **faster-whisper**, rodando local na máquina — `api/voice.py`. Confirmado no código: existe microfone real, existe modelo de voz real rodando local. (Um relatório anterior, de 14/11, dizia "não é de voz ainda" — isso está desatualizado, foi implementado depois.)

**Perguntas livres ("Hey Marvin, posso subir aqui?"):** respondidas por um modelo de linguagem pequeno (Gemma, rodando local via Ollama), mas **só com o dado que o próprio sistema já calculou** — nunca inventa fonte nem decide pelo astronauta. Isso está escrito como instrução fixa do modelo: *"Never invent a number, name or position... the astronaut decides"* — `api/agent.py:24-33`.

**Comandos de voz hoje (confirmados em `web/commands.json`):** abrir/fechar painéis, trocar camada, ajustar zoom, trocar tipo de rota, marcar destino **pelo centro do mapa ou por coordenada exata**, informar o nível de O2 do traje, registrar medição do habitat.

**O que a voz ainda NÃO faz:** escolher um destino a partir de uma descrição livre ("quero achar um mineral tal") — isso é uma ideia discutida depois da proposta original, não implementada, e documentada como decisão em aberto (`docs/plano-real-objetivo-rota-voz.md`).

---

### Replanejamento no meio da caminhada

**O que aparece:** o astronauta relata um problema ("tem uma rocha aqui", "está vindo poeira", "evento solar"), o sistema classifica o tipo de problema e recalcula opções a partir do ponto atual — nunca uma ordem única, sempre opções.

**Código:** `api/replan.py` — categorias reais: radiação, poeira, oxigênio baixo, cansaço, obstáculo físico, terreno mais íngreme que o previsto.

---

## 3. O que NÃO existe no código (por decisão, não por esquecimento)

| Ideia | Status real | Por quê |
|---|---|---|
| Modo "visor do traje" (HUD) com minimapa e trilha de volta | Não encontrado no front (`web/index.html`/`app.js`) | Era classificado como "diferencial" (P1), não obrigatório |
| Sincronização Terra–Marte (botão "sincronizar") | Não encontrado | Classificado como "pitch" (P2) na proposta original |
| Perigos colaborativos (tipo Waze) | Não encontrado | Classificado como "conceito de pitch" (P2), fora do protótipo desde a proposta |
| Objetivo científico em texto livre decidindo o destino | Não encontrado | Ideia discutida depois da entrega oficial, sem decisão do time ainda |

Nenhum desses quatro itens está na proposta oficial como obrigatório — então não faltar eles não é "fugir do que foi prometido".

---

## 4. Checklist pro hackathon

| # | Feature (nome oficial da proposta) | Está no código? | Prova (arquivo) |
|---|---|---|---|
| 01 | Mapa hiperlocal em camadas | ✅ Sim | `api/main.py`, `web/layers.js` |
| 02 | Rota inteligente + indicadores de risco | ✅ Sim, com margem de O2, ponto de não retorno e rótulo ✅/⚠️/⛔ | `api/route_planning.py`, `api/route_suggestions.py` |
| 03 | Fotos reais próximas ao ponto | ✅ Sim | `api/panorama.py` |
| 04 | Ficha científica do ponto | ✅ Sim (testado nesta sessão) | `api/science_card.py` |
| 05 | Painel de condições (clima/radiação/poeira) | ✅ Sim, incluindo alerta de evento solar real | `api/alerts.py`, `api/solar_events.py` |
| 06 | Previsão climática offline | ✅ Sim, com erro medido por backtest | `api/forecast.py` |
| 07 | Visor no traje (HUD) | ❌ Não implementado | — (era "diferencial", não obrigatório) |
| 08 | Assistente de voz offline | ✅ Sim — voz real (faster-whisper) + modelo local (Gemma/Ollama) + replanejamento por fala | `api/voice.py`, `api/agent.py`, `api/replan.py` |
| 09 | Sincronização Terra–Marte | ❌ Não implementado | — (era "pitch", P2) |
| 10 | Perigos colaborativos | ❌ Não implementado | — (era "conceito de pitch", P2) |

**Itens pendentes antes da apresentação, verificados ainda hoje:**
- Testar o alerta de evento solar no navegador (sol 242 no stepper da EVA) — combinado, ainda sem confirmação de tela.
- `docs/raio-x-implementacao.md` tem vários achados de 14/11 que precisam ser reconferidos no código atual (ex.: item 2, "rota ignora histórico íngreme do rover" — não confirmado nem desmentido nesta leitura, requer checar se `route_planning.py` cruza com `alerts.py`/histórico do rover na escolha do caminho, não só na exibição).
- Teste completo com Wi-Fi desligado (critério de aceitação do próprio `CLAUDE.md`) ainda não foi feito ponta a ponta.
