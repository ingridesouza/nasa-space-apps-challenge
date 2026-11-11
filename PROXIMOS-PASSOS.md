# Próximos passos — feature 01 (mapa hiperlocal do boxwork)

## Status das camadas (tabela da feature 01, seção 1)

| # | Camada | Status | `product_id` / fonte |
|---|---|---|---|
| 1 | Óptica detalhe — HiRISE 25cm | ✅ confirmado | `curiosity_hirise_mosaic` (WMTS) |
| 2 | Óptica contexto — CTX ~6m | ✅ confirmado | `Gale_CTX_BlockAdj_dd` (WMTS) |
| 3 | Topografia regional — MOLA | ✅ confirmado | `mola128_mola64_merge_90Nto90S_SimpleC_clon0` (ArcGIS) |
| 4 | Térmica — THEMIS | ✅ confirmado (só visual) | `THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018` (WMTS) |
| 5 | Mineralogia — CRISM | ⚠️ bloqueado | índice de observações, cobertura esparsa (ver abaixo) |
| 6 | Topografia local 1m — DTM HiRISE | ✅ confirmado | `Gale_DEM_SMG_1m` (ArcGIS, elevação real) |
| 7 | Clima — REMS | ❌ não começado | PDS Atmospheres (fonte diferente, tabular) |
| 8 | Radiação — RAD | ❌ não começado | PDS Atmospheres (mesma fonte do clima) |
| 9 | Fotos do rover — MSL | ❌ não começado | API de imagens do MSL |
| 10 | Classe de terreno — AI4Mars | ❌ não começado | Zenodo/Hugging Face |
| 11 | Posição/trajeto — MMGIS | ❌ não começado | mars.nasa.gov |
| 12 | Nomenclatura — USGS/IAU | ❌ não começado | planetarynames |

Todas as confirmadas (1-4, 6) estão em `data-pipeline/config/layers.yaml`
e testadas com dado real (ver commits do dia 2026-11-11).

## Ferramenta de busca automatizada (use antes de tentar achar qualquer produto novo)

`python scripts/lookup_mars_trek_product.py "<termo>" --details` busca
direto no índice do Mars Trek, sem precisar de DevTools/navegador.
Endpoint descoberto inspecionando `jpl/config/config.json` do próprio
site (`searchAutoLayerItemsUrl`). Útil só para o que o Mars Trek serve
(itens 1-6); REMS/RAD/MSL/AI4Mars/MMGIS/nomenclatura são fontes
diferentes (PDS, APIs próprias).

## Bloqueador real: CRISM (mineralogia, item 5)

CRISM **não tem um raster pronto de mineral por pixel** no Mars Trek —
o que existe é um índice de observações pontuais
(`mars_mro_crism_mtrdr_c0a_humex_frt_sites`, serviço `ArcGISFeature`,
query em `.../MapServer/0/query`). Consultado contra toda a extensão da
Cratera Gale: só **3 observações** (`FRT0000A091`, `FRT000037DF`,
`FRT000045F2`), nenhuma cobrindo o bbox de teste do boxwork usado até
agora — a mais próxima fica a ~60 km.

- [ ] Repetir a consulta com as coordenadas REAIS do boxwork escolhido
      assim que decididas (não o bbox de teste).
- [ ] Se não houver cobertura: usar o campo `medicao_curiosity` (texto,
      já previsto no schema `science_targets`) como fonte principal de
      mineralogia — o próprio doc da feature 01 já trata isso como
      complementar, não como bloqueador.
- [ ] Se houver: baixar o produto via `ProdURL` (aponta pro PDS/ODE,
      `ode.rsl.wustl.edu`), não pelo Mars Trek.

## Próximos blocos de trabalho (fontes diferentes do Mars Trek)

- [ ] **REMS/RAD** (clima e radiação, itens 7-8): PDS Atmospheres Node.
      É tabular por sol, não raster — tratar como valor amarrado à
      posição do rover (via MMGIS), não como camada de mapa (ver seção
      2.3 do doc da feature 01).
- [ ] **Fotos do rover** (item 9, feature 3 da Victoria): API de imagens
      do MSL (`mars.nasa.gov/raw_images/...`). Baixar ~200 imagens do
      boxwork pra teste offline de busca por raio.
- [ ] **AI4Mars** (item 10): dataset no Zenodo/Hugging Face, filtrar por
      sol/local do boxwork.
- [ ] **MMGIS** (item 11): trajeto do rover por sol/site/drive → lat/lon
      — liga fotos e clima/radiação a uma coordenada real.
- [ ] **Nomenclatura** (item 12): USGS/IAU Gazetteer.

## Pendências gerais

- [ ] Estruturar os 8-10 alvos científicos da ficha "pokédex" (feature 4
      da Victoria) a partir de notícias/blog do Curiosity e do PDS.
- [ ] Confirmar tudo contra a aba Resources assim que abrir (sexta) —
      nenhuma integração é definitiva antes disso.

## Depois de fechar as camadas restantes

- Banco local (SQLite + SpatiaLite/GeoPackage) com as tabelas
  `rover_images`, `science_targets`, `raster_registry`.
- Endpoint `GET /api/point?lat&lon` em `api/` (contrato reusado pela
  feature 02 de Hugo e pela feature 08).
- Primeiro protótipo de mapa em `frontend/` (MapLibre GL) consumindo os
  tiles locais gerados pelo pipeline.

## Notas técnicas do adaptador WMTS

- `adapters/mars_trek_wmts.py` lida com dois casos de CRS: geográfico
  (graus) e projetado (metros) — detectado automaticamente pela
  magnitude do `TopLeftCorner`.
- Alguns campos numéricos do XML do Mars Trek vêm como float (`"2.0"`)
  mesmo sendo inteiros por definição do schema WMTS — já tratado.
- `adapters/arcgis_image_server.py` serve rasters com valor real de
  pixel (elevação, não imagem renderizada) via `exportImage` — usar
  sempre que o produto tiver um endpoint `ArcGISImageService`, é melhor
  que o WMTS equivalente para sampling.
