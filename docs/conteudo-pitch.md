# H2G2: conteúdo-fonte do pitch

Fonte única de fatos para montar o pitch. Tudo aqui foi conferido no código e nos dados de `data/local/` em 15/11/2026. Se uma frase do pitch não está aqui, confira antes de dizer. A seção "O que não dizer" vale tanto quanto o resto.

Legenda de status: **Protótipo** roda no código hoje · **Extra** roda e vai além do pedido · **Proposta** é desenho, sem código · **Porta pronta** é a entrada de dados construída; o transporte ainda é proposta.

---

## 1. O desafio

**NASA Space Apps 2026 · Interplanetary Survival Guide: Martian Map.**

O site oficial bloqueia leitura automática. O enunciado abaixo foi reconstruído das notas do time e de repositórios que o citam (ver `docs/Plano_Produto_Completo.md`). **Conferir na página oficial antes de citar literalmente.**

- Pede um mapa em camadas de um local ou rota em Marte, que combine dados de várias missões.
- Esse mapa ajuda o astronauta em três frentes: rota e destinos, condições atuais e ciência ao longo do caminho.
- Exemplo dado: o boxwork estudado pelo Curiosity em 2025 no Monte Sharp.
- Crítica central: Mars Trek e os mapas geológicos USGS-NASA servem visões globais e regionais, não a escala de metros de uma caminhada.

Critérios: os 5 oficiais do Space Apps (Impacto, Criatividade, Validade, Relevância, Apresentação) e os 5 do mentor (Localização, Integração científica, Segurança operacional, Contexto científico, Dados abertos). Ver `docs/PITCH.md`.

## 2. O que propomos

**H2G2 (Human-to-Ground Guide):** guia de campo hiperlocal para uma caminhada segura em Marte, no boxwork do Monte Sharp, cratera Gale.

**Valor em uma frase:** mapa, rota, ciência e condições na escala da caminhada (~3×3 km), rodando sem a Terra, e cada número dizendo de onde veio.

**Por que Gale e não Jezero**
- O boxwork é o exemplo do próprio enunciado.
- O Curiosity mede clima (REMS) e radiação (RAD) no mesmo lugar. Nenhum outro ponto da superfície tem radiação medida.
- A ciência é recente: cristas com argila, carbonato nas depressões e nódulos de água subterrânea ([NASA, 2026](https://www.nasa.gov/missions/mars-science-laboratory/curiosity-rover/NASAs-curiosity-rover-sees-martian-spiderwebs-up-close/)).
- Existe um risco real e citável: os operadores relatam que as rodas patinam na areia das depressões.
- Jezero virou lugar-comum entre os concorrentes: mais de 12 repositórios públicos de 2026 neste desafio.

**Três princípios, que são o diferencial**
1. **Offline de verdade.** A internet só é usada no build. Em execução, tudo sai de arquivos locais: mapas, fotos, medições, modelo de voz e LLM.
2. **Nunca inventa.** Sem dado, o sistema responde "sem dado" e diz o que faltou. Mock só existe atrás de flag explícita.
3. **Fonte e confiança em cada linha.** Instrumento, arquivo PDS e confiança acompanham cada fato mostrado ou falado.

---

## 3. Features

### 01 · Mapa hiperlocal em camadas · Protótipo
- **O que faz:** cobre ~3×3 km do boxwork, centrado na posição real do rover na campanha (sóis ~4500–4684). As camadas ligam e desligam.
- **Camadas reais:**

  | Camada | Fonte | Detalhe |
  |---|---|---|
  | HiRISE | mosaico do trajeto do Curiosity (Mars Trek) | servido a ~0,6 m/px |
  | CTX | mosaico de Gale (Mars Trek) | ~10 m/px |
  | Relevo sombreado | DTM HiRISE de Gale | — |
  | Inércia térmica | THEMIS (USGS) | 100 m, valor quantitativo |
  | Risco de inclinação | DTM calibrado pelo rover | ver 03 |
  | Sol e sombra | cálculo próprio | ver 04 |
  | Atmosfera ao longo do trajeto | REMS + RAD | por parada |

- **Nomes oficiais:** 13 nomes IAU/USGS da região.

### 02 · Rota A* com risco explicado · Protótipo
- **Rotas:** A* sobre o relevo real, com três variantes (mais segura, mais rápida, mais ciência). Aceita paradas intermediárias.
- **Inclinação:** cautela a partir de 15° e perigo acima de 20°, o limite de caminhada do Artemis.
- **Radiação:** a dose de RAD do sol medido é somada pela duração da caminhada.
- **O₂ estimado por trecho, numa faixa otimista–pessimista:**
  - taxa base de 350 W (≈1 L/min), do estudo NASA ICES-2026-158 sobre o PLSS de Marte;
  - aumento com a inclinação pela equação de Pandolf, na forma usada pela NASA/JSC (Kim et al., IEEE EMBC 2024);
  - comparado com a capacidade do traje que o usuário informa.
- **Previsão da rota:** chance de o chão real passar de 15° em cada trecho, clima previsto no sol da EVA, melhor janela do dia e dose prevista.
- **Replanejamento:** o astronauta relata o problema (rocha, inclinação, cansaço, poeira, O₂). O sistema gera opções pelo mesmo A* e ele escolhe.
- **Decisão por regra:** o rótulo de risco e a ordem das opções vêm de regra fixa, nunca do LLM. Nenhuma rota é escondida.

### 03 · Risco calibrado pelo rover · Extra
- **O problema:** o relevo de órbita (~6 m/px na grade da rota) suaviza cristas de 1–2 m e subestima a inclinação.
- **O que fizemos:** cruzamos o mapa com a inclinação que o Curiosity mediu em 293 paradas.

  | Faixa do mapa | Paradas com ≥15° medidos |
  |---|---|
  | 10–15° | 27% |
  | ≥15° | 80% (n = 5) |

- **Uso:** o número vira "chance de o chão passar de 15°" em cada ponto e trecho.
- **Como dizer:** é frequência histórica, não previsão. Há viés de seleção, porque o rover só para onde é seguro. Ver `docs/feature-06-previsao-clima.md`.

### 04 · Sol e sombra hora a hora · Extra
- **O que faz:** calcula a irradiância solar direta sobre cada pixel, para qualquer sol e hora local.
- **Como:**
  - posição do Sol pelo algoritmo Mars24 (Allison & McEwen 2000), implementado no projeto;
  - incidência pela inclinação e orientação do DTM HiRISE (1 m nativo, calculado a 2 m);
  - sombra próxima traçando raios sobre o mesmo DTM;
  - sombra distante pelo horizonte MOLA, que inclui o Monte Sharp, fora do recorte.
- **Limite declarado:** é limite superior. Não inclui poeira nem luz difusa, e cristas menores que ~2–3 m não aparecem.

### 05 · Fotos e panoramas no ponto · Protótipo
- **Acervo:** 211 fotos Navcam e 73 panoramas 360° (72 Navcam, 1 Mastcam), guardados localmente.
- **Posicionamento:** cada um é posicionado pela parada do rover (MMGIS). A interface diz "tirada a X m daqui", porque a posição é de onde a foto foi tirada, não do que ela mostra.

### 06 · Ficha científica / cartão de resposta · Protótipo
- **Alvos:** 10 alvos do boxwork com 60 medições reais do PDS (33 ChemCam, 23 APXS, 4 CheMin).
- **Contexto orbital:** CRISM (FRT000058A3, 18 m/px) amostrado no alvo, quando o alvo cai no recorte.
- **Também traz:** foto Mastcam, nome oficial e confiança em cada linha.
- **Cartão de resposta:** a ficha virou o cartão que o agente mostra, com veredito por regra, 2 a 4 fatos com fonte, opções de rota e o que falta no sistema. Nenhum número do cartão vem do modelo; o cartão existe mesmo com o LLM fora.

### 07 · Condições e previsão offline · Protótipo
- **Condições medidas pelo Curiosity:**
  - REMS: temperatura do ar e do solo, pressão, UV, umidade;
  - RAD: dose;
  - hora solar pelo Mars24.
- **Previsão:** climatologia por estação (Ls ±15°), montada com 231 sóis REMS de toda a missão (sóis 100–4840), corrigida pela anomalia do último sol medido. Método mínimo inspirado em de Cabo-García et al. (2019).
- **Erro medido em backtest**, prevendo sóis já medidos, 20 sóis à frente, n = 201:

  | Variável | Erro médio |
  |---|---|
  | Temperatura mínima | 1,9 °C |
  | Temperatura máxima | 3,7 °C |
  | Pressão | 11,2 Pa |

- **Também entrega:** a melhor janela do dia para a duração da EVA.
- **Aviso de anomalia:** se a medição se afasta mais de 3× do erro típico, o sistema avisa que o dia está fora do normal da estação.

### 08 · Marvin, assistente de voz offline · Protótipo
- **Ativação:** "Hey Marvin", ou segurando a tecla espaço.
- **Voz:** Whisper large-v3 local. Um modelo pequeno confirma "sim/não".
- **Comandos de visor:** 11 blocos com nomes de estrela (Atlas, Vega…).
- **LLM:** gemma4:e2b local via Ollama.
- **Regras fixas, sem LLM:**
  - alertas e pedidos de socorro (queda, vazamento, gás tóxico): resposta imediata;
  - fontes citadas: saem da lista que o sistema monta, não do texto do modelo.

### 09 · Visor no capacete · Proposta
- Equipamento proposto: HUD com minimapa, rota, alertas e ficha, com a voz como entrada principal porque luvas impedem toque.
- Mostramos um modelo 3D do capacete e uma caminhada simulada na landing.
- Referência: NASA SUITS usa HoloLens 2 e Magic Leap.
- **Hardware fora do escopo.**

### 10 · Sincronização Terra–Marte · Porta pronta
- **O que já existe:**
  - o sistema roda 100% sem a Terra;
  - avisa quantos sóis os dados de condições têm;
  - avisa a temporada de tempestades de poeira (Ls 180°–360°);
  - medição nova entra por `POST /api/measurement` e a previsão se recalcula na hora, offline.
- **Proposta:** quando houver janela de contato, um pacote de diferença com dados novos entraria pela mesma porta, por prioridade: alertas, depois clima, depois imagens. **O transporte não está implementado.**

---

## 4. Números que podemos dizer

| Número | O quê | Onde conferir |
|---|---|---|
| ~3×3 km | área do mapa | `data-pipeline/config/layers.yaml` |
| 293 | paradas do Curiosity que calibram o risco | `docs/feature-06-previsao-clima.md` |
| 1,9 °C | erro médio da previsão da mínima, 20 sóis à frente | idem |
| 231 | sóis REMS na climatologia | `data/local/conditions/climatology.json` |
| 211 / 73 | fotos / panoramas 360° locais | `data/local/h2g2.sqlite` |
| 10 / 60 | alvos / medições PDS (APXS, ChemCam, CheMin) | idem |
| 20° | limite de inclinação (Artemis) | `api/route_planning.py` |
| 350 W ≈ 1 L/min | taxa metabólica de base para o O₂ | `api/route_planning.py` (NASA ICES-2026-158) |
| 0,64 mSv/dia | dose média na superfície medida pelo RAD | Hassler et al. 2014 (literatura, não nosso dado) |

## 5. O que NÃO dizer

| Não dizer | Dizer |
|---|---|
| "Relevo de 1 m" na rota | Fonte de 1 m; rota e risco em grade de ~6 m; sol e sombra a 2 m |
| "HiRISE colorido" | mosaico HiRISE (o tom do mapa é cosmético) |
| AI4Mars, areia por pixel | não cobre a época; areia entra como aviso fixo |
| Camada de mineralogia no mapa | CRISM só na ficha, quando o alvo cai no recorte |
| Poeira prevista, opacidade τ, vento | não temos; vento: sensor do rover danificado |
| "Previsão de 0,5–1% de erro" | esse número é do artigo citado; o nosso é o backtest acima |
| "Prevê o terreno" | frequência histórica de subestimação do mapa |
| Telemetria ou nível de O₂ do traje | O₂ é estimativa da rota; a capacidade é digitada |
| Sincronização funcionando | porta de entrada pronta; transporte é proposta |
| Capacete ou AR funcionando | proposta com modelo 3D |
| Dados de hoje | último sol REMS/RAD no pacote: 4840; o sistema avisa a idade |

## 6. Fontes de dados usadas

Todas são baixadas no build e servidas offline.

| Dado | Fonte |
|---|---|
| HiRISE, CTX, DTM HiRISE, MOLA | Mars Trek (JPL) |
| Mosaico HiRISE do trajeto (base da F03) | USGS Astrogeology |
| Inércia térmica | THEMIS, mosaico quantitativo USGS |
| Mineralogia | CRISM MTRDR FRT000058A3 (PDS Geosciences) |
| Química e minerais | APXS, ChemCam, CheMin (PDS Geosciences) |
| Clima | REMS (PDS Atmospheres, NMSU) |
| Radiação | RAD (PDS PPI, UCLA) |
| Trajeto e paradas | MMGIS do Curiosity |
| Fotos | API de imagens brutas do MSL |
| Panoramas | science.nasa.gov |
| Nomes | nomenclatura IAU/USGS |
| Hora e posição do Sol | algoritmo Mars24 (NASA GISS) |
