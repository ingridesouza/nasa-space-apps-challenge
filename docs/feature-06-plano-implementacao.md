# Feature 06 · Plano de implementação: previsão que calcula quando não há dado

14/11/2026 · Base: `H2G2_NasaSpaceApps_DETON8.pdf` (F06), [`feature-06-previsao-clima.md`](feature-06-previsao-clima.md) (o que já existe) e a pesquisa de 14/11 (fontes no fim).

## Objetivo

Hoje a previsão calcula bem **no tempo** e **em Gale**: estação + correção pelo último sol, janela de EVA, chão, radiação e chance de inclinação. Quando não há dado, porém, ela **para**: devolve vazio ou "não sei".

O objetivo é que, sem medição, o sistema **calcule** a melhor estimativa possível, sempre dizendo **como calculou** e **quanto pode errar**. Nunca inventa: todo número vem de dado, física ou modelo testado contra o passado.

## A regra central: cascata "medido → previsto → calculado → sem base"

Para cada informação, o sistema tenta as fontes nesta ordem e para na primeira que responde:

| Degrau | Pergunta | Exemplo | Rótulo |
|---|---|---|---|
| 1. Medido | Há medição aqui (rover, habitat)? | o rover mediu 22° nesta parada | `medido` |
| 2. Previsto | O histórico deste lugar permite prever? | clima de Gale pela estação | `estimado · erro ±X` |
| 3. Calculado | Física ou modelo calcula? | pressão pela altitude; Mars-GRAM fora de Gale | `calculado · método · erro ±X` |
| 4. Sem base | Nada acima funciona | vento, tempestade solar | "sem base para calcular" |

**Regras:**
- O "não sei" só aparece no degrau 4.
- O rótulo é visível na tela. Não fica escondido em tooltip.
- Todo número do degrau 2 ou 3 precisa de um **teste contra o passado** que mostre o erro. Sem teste, não entra.
- **Mudança na regra do `CLAUDE.md`, a aprovar pelo time:** "sem dado real → `null`" passa a "sem dado medido → estimativa rotulada (método, confiança, erro); `null` só quando não há base para calcular".

## Raio-x: o que falta hoje

| # | Gravidade | O que acontece | Fase |
|---|---|---|---|
| 1 | 🔴 | O trabalho novo da previsão não está salvo no histórico do projeto | 0 |
| 2 | 🟠 | Sem dado, devolve vazio ou "não sei" (fora da área com relevo, sol sem ano anterior, areia, rocha longe dos alvos) | 1 |
| 3 | 🟠 | O assistente recebe só a previsão de hoje: não sabe o sol da EVA escolhido, a janela nem a dose da rota | 1 |
| 4 | 🟠 | Mesmo clima para qualquer ponto ou lugar de Marte | 2 e 4 |
| 5 | 🟠 | Não prevê "o sol seguinte" (amostra de 1 sol a cada 20), que é a promessa literal do PDF | 3 |
| 6 | 🟠 | Uma medição do habitat digitada errada desloca todas as previsões seguintes; o aviso aparece, mas ela continua como base | 1 |
| 7 | 🟠 | A chance de inclinação usa um indicador só, a faixa ≥15° tem só 5 paradas e a conta nunca foi testada fora da amostra | 5 |
| 8 | 🟡 | Dado novo de clima só aparece depois de reiniciar o sistema | 1 |
| 9 | 🟡 | A melhor janela de EVA olha só a temperatura, sem luz do Sol nem radiação | 2 |

## Fases

### Fase 0 · Salvar o que existe (antes de tudo)
- Commit do trabalho atual e PR para a `main`.
- **Aceite:** `make test` verde, PR aberto.

### Fase 1 · Cascata no assistente e na tela (pequena, maior impacto)
1. **Contexto do assistente:**
   - inclui o sol da EVA escolhido, a janela, a dose da rota e uma seção "ESTIMATIVAS (não medidas)", cada uma com método e erro;
   - regra nova no prompt: "sem medição, dê a melhor estimativa e diga que é estimativa; 'não sei' só quando não houver base".
2. **Janela da estação alargada:** sem ano anterior em ±15° de Ls, tenta ±30° e ±45°, baixando a confiança a cada passo.
3. **Medição do habitat com peso:** medição fora do normal (mais de 3 vezes o erro típico) fica **pendente** até ser confirmada. Até lá, a base continua sendo o último dado normal, e a tela mostra "medição pendente de confirmação".
4. **Recarregar o clima** quando o arquivo mudar, sem reiniciar.
- **Aceite:**
  - "qual a melhor hora para a EVA?" responde com a janela e o rótulo "estimado";
  - pergunta sem base responde "sem base para calcular";
  - teste: medição de -60 °C não move a previsão até ser confirmada;
  - teste: sol sem ano anterior em ±15° recebe previsão com confiança "baixa".

### Fase 2 · Calcular por física, por ponto
1. **Pressão no ponto pela altitude:** escala de ~11 km, conferida pela física (H = RT/Mg ≈ 10,9 km). Na área, o relevo varia ~720 m, cerca de 6% (~50 Pa).
2. **Janela de EVA com o Sol:** nascer, pôr e altura do Sol pelo Mars24 (já meio pronto), para evitar janela no escuro.
- **Aceite:**
  - dois pontos com 300 m de diferença de altitude mostram pressões diferentes, com o método "altitude";
  - a janela nunca cai fora do horário de Sol.

### Fase 3 · "O sol seguinte" e ML (pesquisa → teste → decisão)
1. **Dado:**
   - baixar **sols seguidos** do REMS, pelo menos o último ano marciano (~670 sols) e, se o tempo deixar, a missão toda (~4.800);
   - usar o mesmo download parcial de hoje (~180 linhas por sol, ~5 s por sol), o que dá ~1 h por ano marciano;
   - guardar a curva por hora de cada sol.
2. **Linha de base:** o método atual (estação + anomalia) com horizonte de **1 sol**.
3. **Modelos a comparar**, só com numpy (sem pacote novo), treinando só com o passado:
   - regressão harmônica em Ls + tendência;
   - kNN em (Ls, ano);
   - rede pequena tipo de Cabo-García: entrada = curva do dia anterior + Ls; saída = curva do dia seguinte, hora a hora.
4. **Decisão pelo número:** um modelo só entra se ganhar do método atual no teste contra o passado com horizonte 1. Se nenhum ganhar, fica o atual, e o doc diz por quê.
- **Aceite:** tabela de erro por modelo (horizonte 1, 20 e 100 sols) no doc da F06, e o modelo escolhido rodando offline na CPU em menos de 1 s por previsão.

### Fase 4 · Calcular fora de Gale (Mars-GRAM, NASA)
1. Baixar e instalar o **GRAM Suite / Mars-GRAM** (NASA, liberação pública, interface em Python) no build.
2. **Validar em Gale:** comparar o Mars-GRAM com o REMS (temperatura e pressão por estação). Medir o erro e o viés.
3. **Usar como degrau 3:** fora de Gale, o número vem do Mars-GRAM corrigido pelo viés medido em Gale. Rótulo: "calculado · Mars-GRAM (NASA) · erro ±X".
- **Atenção:** a NASA descreve o Mars-GRAM como **atmosfera de referência, não previsão do tempo**. Ele dá o clima típico do lugar e da estação, não o do dia.
- **Aceite:** um ponto fora da janela devolve temperatura e pressão com o rótulo do Mars-GRAM e o erro medido em Gale. O sistema roda sem internet.

### Fase 5 · Chance de inclinação com ML validado
1. **Indicadores por ponto:**
   - inclinação;
   - rugosidade (desvio-padrão da inclinação em 3×3 e 5×5);
   - relevo local (elevação menos a média do entorno);
   - curvatura;
   - se houver o mapa recortado para Gale, **inércia térmica** do THEMIS, que a literatura liga a patinar.
2. **Modelo:** regressão logística em numpy (alvo: rover mediu ≥15°), validada **por áreas separadas**, para não vazar paradas vizinhas. Métricas: Brier e AUC.
3. **Troca só se ganhar** da tabela de faixas atual. A camada do mapa, a cor da rota e o alerta passam a usar a probabilidade com incerteza.
- **Aceite:** tabela comparando "faixas" × "logística" no doc. A faixa com poucas paradas nunca sobe um trecho a "perigo".

## Fora do escopo (sem base para calcular)

| Lacuna | Motivo |
|---|---|
| Vento | O sensor de vento do Curiosity está danificado |
| Tempestade solar | Pico de horas, sem aviso nos dados locais |
| Tempestade de poeira do dia | Sem dado local. Fica o alerta de temporada (Ls 180°–360°) |
| Areia por ponto | Não há rótulo de areia para treinar (o AI4Mars não cobre a época). No máximo um "indício" pelo relevo, com confiança baixa |
| Mineral de órbita (CRISM) | Nenhuma observação na área |

## Riscos

- **Estimativa lida como certeza:** o rótulo precisa ficar visível. No modo traje, junto do número.
- **Dados pequenos demais para ML:** com 231 sols espaçados, nenhuma rede aprende o que a média da estação não pega. Por isso a Fase 3 começa pelo dado.
- **Mars-GRAM pesado ou incompatível:** se não instalar no Python do projeto ou passar de alguns GB, a Fase 4 fica para o pitch, citando o MCD (LMD/ESA/CNES) como alternativa.
- **Regra do `CLAUDE.md`:** a mudança precisa do aceite do time antes da Fase 1.

## Para o time técnico (onde mexer)

| Fase | Arquivos |
|---|---|
| 1 | `api/agente.py` (contexto e prompt), `api/main.py` (`/api/ask` envia o sol, a janela e a dose), `api/previsao.py` (janela alargada, medição pendente, recarga do clima), `web/ui/previsao.js` (rótulo "pendente"), `api/test_previsao.py` |
| 2 | `api/previsao.py` (pressão por altitude), `api/tempo_marte.py` (nascer e pôr do Sol), `api/main.py` (`/api/point` e `/api/previsao` com lat/lon), `web/ui/ponto.js` |
| 3 | `data-pipeline/scripts/cache_climatologia.py` (modo "sols seguidos"), novo `api/modelo_clima.py` só se um modelo vencer, `docs/feature-06-previsao-clima.md` (tabela) |
| 4 | novo `data-pipeline/scripts/fetch_mars_gram.py`, novo `api/mars_gram.py`, `Makefile` (build) |
| 5 | `api/previsao.py` (indicadores e logística), `api/tile_server.py` (camada), `api/test_previsao.py` |

## Fontes da pesquisa (14/11/2026)

- **de Cabo-García et al.**, *Prediction of Mars meteorological variables using artificial neural networks*:
  - Treinou com REMS 2013–2018 (1.637 sols seguidos) e prevê o sol seguinte hora a hora, com 0,5–1% de erro nas variações diurnas.
  - [EGU 2019](https://ui.adsabs.harvard.edu/abs/2019EGUGA..2111304D/abstract) · [slides INTA](https://www.inta.es/export/sites/default/.galleries/cpess6-Descarga/de-Cabo-Garcia-A_MARSchine-Learning-Prediction-of-Mars-meteorological-variables-using-artificial-neural-networks.pdf)
- **LSTM e CNN-LSTM para clima de Marte (REMS):** estudos acadêmicos, com séries diárias contínuas.
  - [IEEE](https://ieeexplore.ieee.org/abstract/document/10002657) · [arXiv 2309.01424](https://web3.arxiv.org/pdf/2309.01424) · [Berkeley](https://www.ischool.berkeley.edu/research/publications/2021/mars-weather-data-analysis-using-machine-learning-techniques)
- **Mars-GRAM / GRAM Suite (NASA):** liberação pública, com interface em Python. É atmosfera de referência, não previsão do tempo.
  - [catálogo de software da NASA](https://software.nasa.gov/software/MFS-33888-1) · [guia do usuário](https://ntrs.nasa.gov/api/citations/20210023957/downloads/Mars-GRAM%20User%20Guide.pdf)
- **Mars Climate Database v6.1 (LMD, com apoio de ESA e CNES):** acesso por pedido.
  - [EPSC 2024](https://meetingorganizer.copernicus.org/EPSC2024/EPSC2024-516.html) · [validação](https://www-mars.lmd.jussieu.fr/mars/info_web/validation_doc_v6.1.pdf)
- **Patinar e traversabilidade:** inércia térmica + relevo melhoram a previsão com dado do Curiosity.
  - [WVU](https://yugu.faculty.wvu.edu/files/d/6ec90de4-d996-405b-b2e7-61b5ec354ad6/spirit_slip_analysis_istvstemplate__copy___to_be_submitted_.pdf) · [CMU](https://ri.cmu.edu/event/traversability-prediction-for-planetary-rovers-in-granular-terrain) · [SlipNet](https://arxiv.org/pdf/2409.02273) · [rastreabilidade probabilística](https://arxiv.org/pdf/2409.00641v1)
