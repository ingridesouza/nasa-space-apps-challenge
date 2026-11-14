# Próximos passos — feature 01 (mapa hiperlocal do boxwork)

## Status das 12 fontes (tabela da feature 01, seção 1)

| # | Fonte | Status | `product_id` / fonte |
|---|---|---|---|
| 1 | Óptica detalhe — HiRISE 25cm | ✅ confirmado | `curiosity_hirise_mosaic` (WMTS) |
| 2 | Óptica contexto — CTX ~6m | ✅ confirmado | `Gale_CTX_BlockAdj_dd` (WMTS) |
| 3 | Topografia regional — MOLA | ✅ confirmado | `mola128_mola64_merge_90Nto90S_SimpleC_clon0` (ArcGIS) |
| 4 | Térmica — THEMIS | ✅ confirmado (só visual) | `THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018` (WMTS) |
| 5 | Mineralogia — CRISM | ⚠️ bloqueado | só 3 observações em toda Gale, nenhuma no bbox (ver abaixo) |
| 6 | Topografia local 1m — DTM HiRISE | ✅ confirmado | `Gale_DEM_SMG_1m` (ArcGIS) + hillshade visual |

### Correção (2026-11-14): relevo e térmica praticamente invisíveis no mapa

Reportado pelo usuário: mesmo com as camadas "Relevo" e "Térmica" ligadas
e no zoom certo, nenhuma diferença visual aparecia. Investigado e
confirmado que **não era bug de dado, registro, nome de camada nem
cache** — os dois problemas eram de apresentação visual:

- **Relevo (hillshade):** o boxwork é relativamente plano, então o
  sombreamento calculado ficava espremido numa faixa estreita de cinza
  (baixíssimo contraste). Corrigido em `api/mosaics.py`
  (`build_hillshade_array`): alongamento de contraste por percentil
  (2-98) antes de converter pra 8-bit — mesmos valores reais de
  sombreamento, só usando a faixa de exibição toda.
- **Térmica (THEMIS):** o mosaico baixado é cinza puro (sem banda de
  cor), então ficava indistinguível da imagem óptica por baixo.
  Corrigido com uma paleta sequencial (`aplicar_paleta_termica` em
  `api/mosaics.py`, aplicada em `api/tile_server.py` e no endpoint de
  miniatura `/mosaics/{layer}.png` em `api/main.py`) — traduz o mesmo
  brilho real em cor (preto/roxo → vermelho/laranja → amarelo claro).
  **Importante:** é só uma tradução visual do brilho relativo, não
  calibra temperatura real em °C (não baixamos esse metadado
  radiométrico) — por isso o nome evita a palavra "temperatura".

Nenhum dado foi inventado nem baixado de novo; as duas correções só
mudam como o mesmo pixel real já existente é desenhado na tela.
| 7 | Clima — REMS | ✅ confirmado | PDS Atmospheres Node, produto RNV por sol |
| 8 | Radiação — RAD | ✅ confirmado | PDS-PPI (UCLA), dose do detector E |
| 9 | Fotos do rover — MSL | ✅ confirmado | 200 fotos reais, posição via MMGIS |
| 10 | Classe de terreno — AI4Mars | ❌ indisponível (dataset não cobre a época) | testado até sol 2579 (2019) |
| 11 | Posição/trajeto — MMGIS | ✅ confirmado | `MSL_waypoints.json` oficial, 1388 pontos (sol 3-5070) |
| 12 | Nomenclatura — USGS/IAU | ✅ confirmado | webmap USGS no ArcGIS, 13 feições em Gale |

**9 de 12 resolvidas.** Só CRISM (sem cobertura real) e AI4Mars
(dataset antigo demais) ficam de fora — não por falta de esforço, são
limitações reais do dado existente.

---

## ⚠️ Correção importante (2026-11-13): o bbox mudou

O bbox de teste usado até aqui (`137.40-137.48, -4.61~-4.57`) era um
chute perto do **local de pouso** do Curiosity (sol 3). Com o MMGIS
real (ver item 11), descobrimos que a posição do rover durante a
campanha de boxwork (sol ~4500-4684) é **13,3 km de distância** dali.

**Bbox real agora em uso** (3x3km, centrado na posição real do rover
durante o boxwork):
```
min_lon: 137.3586   min_lat: -4.8263
max_lon: 137.4094   max_lat: -4.7757
```
Já propagado em `data-pipeline/config/layers.yaml`,
`db/populate_raster_registry.py` e `frontend/src/map/style.ts`. Todas
as camadas visuais (CTX/HiRISE/DTM/MOLA/THEMIS/hillshade) e os 3 alvos
científicos foram re-baixados/recalculados pro bbox novo.

---

## MMGIS (item 11) resolvido ✅ — e destravou o item 9 junto

Achado via DevTools em `https://science.nasa.gov/mission/msl-curiosity/location-map/`
(filtro `json` no Network): o endpoint oficial e público é

```
https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json
```

GeoJSON sem autenticação, 1388 pontos, do sol 3 até o sol 5070 (atual
na época da consulta). Cada ponto tem `sol`, `site`, `drive`,
`lat`/`lon` reais, `elev_geoid`. Baixado e cacheado por
`data-pipeline/scripts/fetch_rover_waypoints.py` em
`data/local/rover_waypoints.json`.

**Isso resolveu o item 9 (fotos do rover) de graça**: a API de fotos
(`mars.nasa.gov/api/v1/raw_image_items/`) dá o `sol` de cada foto, só
não dava posição. Agora cruzamos com o waypoint de sol mais próximo
pra pegar lat/lon real. `db/seed_rover_images.py` populou **200 fotos
reais** dos sóis 4560-4609 (início da campanha de boxwork), cada uma
com a posição real do rover naquele sol — `nearby_photos` no
`/api/point` agora devolve distância/direção de verdade, não mais
lista vazia.

**Limitação honesta:** a posição é "onde o rover estava no fim do sol
de deslocamento", não o ponto exato de onde cada foto foi tirada
dentro daquele sol — mas é posição real e verificável, granular o
suficiente pra a busca por raio fazer sentido.

---

## Nomenclatura (item 12) resolvido ✅

Achado via busca pública na API do ArcGIS Online
(`arcgis.com/sharing/rest/search`) — webmap "Mars High-Resolution
Mosaic Viewer" da USGS (owner `thare@usgs.gov_USGS`) com 5 camadas de
nomenclatura IAU embutidas como `featureCollection` no próprio JSON do
item.

`data-pipeline/scripts/fetch_nomenclature.py` baixa e filtra pra região
de Gale: 13 feições reais, incluindo **Aeolis Mons** (nome oficial do
"Monte Sharp"), **Aeolis Palus**, **Gediz Vallis** e a cratera
**Yellowknife**. Exposto via `GET /api/nomenclature`; o frontend mostra
a feição mais próxima do clique com link pro Gazetteer oficial.

**Mesma técnica (busca pública no ArcGIS) também achou o mapa geológico
global da USGS** (Tanaka et al. 2014) com camada consultável por
coordenada — contexto geológico real mas em escala global (1:20M), não
substitui dado hiperlocal.

---

## Bloqueador real restante: CRISM (mineralogia, item 5)

CRISM **não tem um raster pronto de mineral por pixel** no Mars Trek —
é um índice de observações pontuais
(`mars_mro_crism_mtrdr_c0a_humex_frt_sites`, `ArcGISFeature`). Só **3
observações** em toda a Cratera Gale, nenhuma cobrindo o bbox atual.

- [x] Reconsultado com o bbox real corrigido
      (`137.3586,-4.8263,137.4094,-4.7757`) em 2026-11-13: query direta
      no `MapServer/0` retornou `"features": []` — zero observações
      CRISM nessa área, confirmado. Bloqueio real, não é falta de
      tentar.
- [x] Sem cobertura: `medicao_curiosity` (já populado nos 3 alvos
      científicos) é a fonte de mineralogia usada; `mineral_crism`
      fica `None` em `/api/point` (nunca inventado).

## Bloqueador real: AI4Mars (item 10) — indisponível, não pendente

Dataset publicado em 2021, cobre só até ~sol 2579 (nov/2019) — quase
2000 sóis antes da campanha de boxwork (sol 4564+, 2025). Não existe
(e não pode existir) classificação AI4Mars pra essa região. Item
encerrado como indisponível.

---

## REMS (clima, item 7) ✅ e RAD (radiação, item 8) ✅

`adapters/pds_rems.py` e `adapters/pds_rad.py` baixam dado real por
sol (PDS Atmospheres Node / PDS-PPI UCLA). Testado com sol 4650:
pressão ~709 Pa, temp -69.5°C a -8.1°C, dose ~157 µGy/dia — plausível
pra Marte. Cacheado localmente por `cache_conditions.py`, sem chamada
de rede em tempo de request (requisito de rodar offline).

**Nota:** o sol de referência (4650) usado no cache é dentro do bbox
real do boxwork — não precisa re-cachear.

---

## Banco local + API ✅

`data-pipeline/db/schema.sql`: `rover_images`, `science_targets`,
`raster_registry` + R-Tree nativo do SQLite (sem SpatiaLite/GDAL).

`api/main.py`: `GET /api/point`, `/layers`, `/mosaics/{layer}.png`,
`/api/conditions`, `/api/nomenclature`. Veredito de segurança (slope
vs. limite de 20° da Artemis) em `raster_sampling.classify_slope`.

---

## Frontend ✅

*(Nota 2026-11-14: esta seção descreve o front original em React —
substituído de ponta a ponta pelo HTML/JS puro em `web/`, ver README e
`docs/migracao-front-html-puro.md`. Mantida como registro histórico de
quando cada peça foi construída, não como descrição do front atual.)*

`frontend/` (React + Vite + TS + MapLibre GL), tema HUD. Mapa com
CTX/HiRISE/Relevo/THEMIS (toggle+opacidade cada), clique no ponto →
briefing de segurança + fotos próximas reais + ficha científica + nome
oficial da feição mais próxima. `ConditionsPanel` com REMS/RAD do sol
de referência.

**Nota técnica:** tiles do Mars Trek não são Web Mercator, então viram
mosaico único (`api/mosaics.py`) servido como `ImageSource`, não
`tiles` XYZ padrão do MapLibre. "Zoom contínuo" é por overzoom de uma
amostra por camada, não pirâmide completa.

---

## Pendências gerais

- [x] Reconsultar CRISM com o bbox real — feito em 2026-11-13, zero
      cobertura confirmado (ver seção acima).
- [x] Confirmar tudo contra a aba Resources assim que abrir — **já
      verificado em 2026-11-12**: Mars Trek (nossa base) bate com o
      oficial; galeria de fotos oficial aponta pra Jezero/Perseverance,
      mantivemos Gale com a API da Curiosity (já validada).
- [ ] Estruturar os 8-10 alvos científicos completos da ficha "pokédex"
      é trabalho da feature 4 (Victoria) — já temos 3 reais prontos
      pra ela reaproveitar. **Gap real, acknowledged** (não é bug, é
      escopo de outra feature).
- [ ] `docs/PITCH.md` tem o argumento central (Gale vs. Jezero: só Gale
      tem clima+radiação co-localizados) pronto pra quem for montar a
      apresentação.

## Auditoria "certeza absoluta" contra a spec original (2026-11-13)

Antes de começar a feature 02 (rota/A*) em cima do `GET /api/point`
desta feature, foi feita uma auditoria linha a linha contra
`feature-01-mapa-hiperlocal-boxwork.md`, verificando o sistema rodando
de verdade (não só o código/memória). Dois desvios reais do contrato
documentado foram encontrados e **corrigidos**:

1. **`raster_values` não batia com a spec.** Vinha aninhado por
   camada (`{"dtm_hirise_1m": {...}, "mola_topografia_regional":
   {...}}`) em vez do formato plano documentado
   (`elevacao_m`/`slope_deg`/`classe_ai4mars`/`mineral_crism` como
   chaves de topo). Corrigido em `api/raster_sampling.py`
   (`sample_all_rasters`): agora devolve exatamente as chaves da
   spec, escolhendo a camada mais precisa disponível (DTM HiRISE 1m
   antes do MOLA regional, mais grosseiro) como fonte de
   `elevacao_m`/`slope_deg`. `classe_ai4mars` e `mineral_crism` ficam
   `None` (não inventados — ver blocos AI4Mars/CRISM acima). Mantido
   um campo extra `fontes` (fora da spec original, mas aditivo) com o
   detalhe por camada, usado pelo painel "outras fontes de elevação"
   do frontend. **Testado ao vivo**: reiniciei a API e confirmei via
   `curl /api/point?lat=-4.80689&lon=137.37984` que o shape bate
   exatamente com a spec. *(Nota 2026-11-14: isto foi feito antes da
   migração pro front HTML/JS puro — na época o front ainda era
   `frontend/src/api/types.ts` e `PointInfoPanel.tsx` em React/TS,
   removido desde então; ver `docs/migracao-front-html-puro.md`. O
   equivalente atual do consumo desse contrato é `web/ui/paineis.js`.)*
2. **Grid de fotos faltando.** `NearbyPhotosSection.tsx` renderizava
   só uma lista de texto (distância/direção/sol/câmera), nunca a
   imagem — a spec (seção 4) pede explicitamente "grid/lightbox de
   fotos estáticas, ordenadas por distância e direção". Corrigido:
   grid 2 colunas com `<img>` real (usa `p.url` que a API já
   devolvia) + lightbox em clique.

**Conferido e OK, sem mudança necessária:**
- `nearby_photos` e `science_target`: shape já batia com a spec.
- Contagens reais via SQLite: `rover_images` = 200 (bate com "~200
  imagens" da spec), `raster_registry` = 6 camadas.
- "Geofísica" marcada como `fora_de_escopo` no
  `frontend/src/map/layers.ts`, visível na UI — spec pede
  comunicar a exclusão, não esconder.
- `science_target.classe_terreno` é renome intencional da coluna
  `classe_ai4mars` do banco pra bater com o nome exato da chave JSON
  da spec — não é bug.
- Zoom contínuo via `ImageSource` sempre renderizado (não
  minzoom/maxzoom-gated como a spec sugere) — simplificação já
  documentada, não é uma surpresa nova.

**Gap real, não é bug, é escopo de outra feature:** só 3 de 8-10 alvos
científicos (ficha "pokédex" completa é trabalho da feature 4/Victoria).

## Auditoria de "roda offline de verdade?" (2026-11-14)

Checado linha a linha depois da pergunta direta "será que tudo que
construímos vai rodar offline sem ser pesado" -- é um requisito que,
se falhar, invalida a demo inteira no evento.

**Confirmado OK:**
- Zero chamada de rede em tempo de execução em `api/*.py` (checado via
  grep por `requests.get`/`urlopen`/`httpx` -- só existe em scripts de
  fetch do `data-pipeline/`, nunca chamado pela API rodando).
- `data/local/` (todo o dado real cacheado -- tiles, DTM/MOLA, condições,
  nomenclatura, waypoints, fotos) = **~130MB no total**. Leve, não é
  motivo de preocupação de peso/espaço.
- React/MapLibre/frontend inteiro vira bundle estático no build do
  Vite -- não busca nada de rede em tempo de execução. Único
  pré-requisito é `npm install` ter rodado uma vez, com internet, antes
  do evento (igual `pip install -r requirements.txt` do lado
  Python) -- não é particularidade de React, é de qualquer projeto
  Node/Python com dependências.

**Bug real encontrado e corrigido:** `rover_images.local_path`
guardava a URL remota de `mars.nasa.gov` direto (apesar do nome da
coluna), não um arquivo local -- sem internet, as ~200 fotos (grid,
lightbox, pins do rastro do rover) quebrariam todas, virando ícone de
imagem quebrada. Corrigido com `data-pipeline/scripts/download_rover_photos.py`
(baixa de verdade pro disco, 39MB) + `api/main.py` servindo via
`StaticFiles` em `/rover-photos/...`. Reflete em todo lugar que usa
foto (`nearby_photos`, `all_photos` em `api/vector_queries.py`, agora
com parâmetro `base_url` pra montar a URL local em vez de devolver a
remota).

**Gap conhecido, não crítico:** as fontes (Chakra Petch, IBM Plex Sans,
JetBrains Mono) carregam via CDN do Google em `frontend/index.html`.
Sem internet, degrada pra fonte padrão do sistema -- não quebra nada,
só perde a tipografia escolhida. Auto-hospedar resolveria por completo;
não fiz ainda por não ser bloqueante pra demo.

## Feature 02 (rota) — status das fontes do cálculo de O₂/tempo

Mesmo padrão de tabela da feature 01, mas pros valores humanos usados
em `api/route_planning.py` (tempo de caminhada → consumo de O₂ →
comparação com capacidade do traje). Diferente das 12 fontes da
feature 01 (orbitais/rover, todas reais), **estes são valores de
fisiologia humana em EVA — nenhum vem de telemetria real do nosso
traje (não existe um traje físico neste projeto), e a maioria não
tinha fonte verificável até esta revisão.**

| # | Valor | Usado em | Status | Fonte / observação |
|---|---|---|---|---|
| 1 | Consumo de O₂ (L/min) | `TAXA_O2_L_POR_MIN` (`route_planning.py`) | ⚠️ sem fonte real confirmada | Valor atual (0,84) tinha só um comentário vago ("EVA Apollo") sem link. Melhor referência real encontrada: estudo NASA do traje p/ Marte (ICES 2026 Mars Schematic Study, NTRS 20260002884) — 350W médios numa EVA de 8h, que convertido pela relação fisiológica padrão (~5 kcal/L O₂) dá **~1,0 L/min**. Ainda não aplicado no código — decisão pendente. |
| 2 | Velocidade de caminhada (m/s) | `VELOCIDADE_BASE_M_S` (`route_planning.py`) | ⚠️ sem fonte real confirmada pra Marte | Valor atual (0,8) também sem fonte verificável. Dado real mais próximo achado: caminhada Apollo em terreno plano ~0,6 m/s — mas é dado **lunar**, gravidade bem menor que a de Marte, então não é diretamente aplicável. Não achada referência de caminhada em gravidade marciana com número publicado. |
| 3 | Capacidade de O₂ do traje (L) | `CAPACIDADE_O2_L_PADRAO` (`web/ui/rota.js`) | ⚠️ sem fonte oficial de projeto de traje | Valor atual (400L, editável no painel) é da mesma ordem de grandeza de uma EVA de 8h a ~1,0 L/min (~480L), mas não é o número oficial de nenhum projeto de traje NASA (o projeto real de 2025 cita ~8,6kg de O₂ por EVA de 8h, que já inclui margem/vazamento/pressurização, não só respiração). |
| 4 | Posição da base (ponto de partida/retorno) | modo traje (`docs/raio-x-implementacao.md`) | ⚠️ provisória | Ainda não definida com coordenada real — afeta diretamente o cálculo de O₂ de ida+volta e o alerta de "voltar à base". |

**Diferença importante em relação à feature 01:** lá, "sem fonte" quase
sempre significa "o instrumento real não cobre essa área/época"
(CRISM, AI4Mars) — é uma ausência de dado documentada e definitiva.
Aqui, em vez disso, os números existem e rodam, mas foram escritos
como se fossem citação de um dado real sem essa citação existir de
fato — é um risco de credibilidade diferente (parece dado real, não é
ainda), não uma limitação de cobertura orbital. Ver discussão completa
na sessão de 2026-11-14 (não há doc de feature 02 equivalente ao
`feature-08-agente-local.md` hoje — considerar criar um).

## Notas técnicas

- `adapters/mars_trek_wmts.py`: lida com CRS geográfico (graus) e
  projetado (metros), detectado pela magnitude do `TopLeftCorner`.
  Alguns campos numéricos do XML vêm como float (`"2.0"`) mesmo sendo
  inteiros — já tratado.
- `adapters/arcgis_image_server.py`: serve rasters com valor real de
  pixel via `exportImage` — preferir sempre que existir
  `ArcGISImageService`, é melhor que WMTS equivalente pra sampling.
- Busca pública no ArcGIS Online (`arcgis.com/sharing/rest/search`,
  sem auth) é uma técnica reutilizável pra achar conteúdo
  USGS/Esri-hospedado fora do Mars Trek (geologia, nomenclatura,
  trajetos) — ver memória de sessão pra detalhes.
