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

- [ ] Reconsultar com o bbox real atualizado (ver seção acima) — ainda
      não refeito.
- [ ] Sem cobertura: usar `medicao_curiosity` (já populado nos 3 alvos
      científicos) como fonte principal de mineralogia.

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

- [ ] Reconsultar CRISM com o bbox real (ver seção acima).
- [ ] Confirmar tudo contra a aba Resources assim que abrir — **já
      verificado em 2026-11-12**: Mars Trek (nossa base) bate com o
      oficial; galeria de fotos oficial aponta pra Jezero/Perseverance,
      mantivemos Gale com a API da Curiosity (já validada).
- [ ] Estruturar os 8-10 alvos científicos completos da ficha "pokédex"
      é trabalho da feature 4 (Victoria) — já temos 3 reais prontos
      pra ela reaproveitar.
- [ ] `docs/PITCH.md` tem o argumento central (Gale vs. Jezero: só Gale
      tem clima+radiação co-localizados) pronto pra quem for montar a
      apresentação.

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
