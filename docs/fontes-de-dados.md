# Fontes de dados do projeto H2G2

Levantamento de todas as fontes de dados (científicas, de imagem e de código/bibliotecas front-end)
identificadas no repositório, a partir do estado de `origin/main` (commit `627bd02`). Para cada uma:
de onde vem, onde é usada no código e para que serve. Segue a diretriz do `CLAUDE.md`: nenhum dado
real é inventado aqui — o que não está documentado no código é marcado explicitamente.

> Convenção do projeto: toda fonte científica tem nível de confiança (`medido`, `inferido`, `estimada`,
> `mock`). Fontes marcadas como **mock** só existem atrás da flag `source: mock`/`science_source: mock`
> em `data-pipeline/f03/config.yaml` e nunca são o padrão de entrega.

## 1. Imagem e topografia orbital (Mars Trek / USGS)

| Fonte | Instituição / produto | Onde é usada | Para quê |
|---|---|---|---|
| **HiRISE óptico (25 cm)** — `curiosity_hirise_mosaic` | NASA/JPL · Mars Trek, WMTS (`trek.nasa.gov/tiles`) | `data-pipeline/adapters/mars_trek_wmts.py`, config em `data-pipeline/config/layers.yaml` (`hirise_optica`), registrado por `data-pipeline/db/populate_raster_registry.py`, camada no front em `web/layers.js` | Camada base de imagem de detalhe do mapa (Feature 01) e fundo dos panoramas/fichas (F03/F04) |
| **CTX óptico (~6 m)** — `Gale_CTX_BlockAdj_dd` | NASA/JPL · Mars Trek, WMTS | idem acima (`ctx_optica`) | Camada de contexto regional do mapa (F01) |
| **DTM HiRISE 1 m de Gale** — serviço `Gale_DEM_SMG_1m` | USGS Astrogeology (MRO HiRISE Gale Crater DEM) · Mars Trek `ArcGISImageServer` (`exportImage`) | `data-pipeline/adapters/arcgis_image_server.py`, `layers.yaml` (`dtm_hirise_1m`) | Elevação real (relevo local); base do hillshade (`relevo_hillshade`, gerado por `api/mosaics.py`) e do risco de inclinação (`risco_previsto`, `api/previsao.py`) — Features 01, 02, 06, 16 |
| **MOLA (topografia regional, ~200 m)** — serviço `mola128_mola64_merge_90Nto90S_SimpleC_clon0` | NASA/MGS · USGS, via Mars Trek `ArcGISImageServer` | `layers.yaml` (`mola_topografia_regional`) | Contexto regional de elevação |
| **THEMIS térmica (~100 m)** — `THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018` | Mars Odyssey/THEMIS · Mars Trek, WMTS | `layers.yaml` (`themis_termica`) | Camada térmica visual (sem amostragem de valor real — só WMTS, sem endpoint ArcGIS) |
| **THEMIS inércia térmica quantitativa (100 m)** — `THEMIS_TI_Mosaic_Quant_30S120E_100mpp.cub` | Mars Odyssey/THEMIS · mosaico global do USGS Astropedia (`asc-astropedia.s3.us-west-2.amazonaws.com/Mars/Odyssey/THEMIS-Global-Thermal-Inertia-Mosaic/`), mosaico multi-ano | `data-pipeline/scripts/fetch_themis_ti.py` (lê só a janela por `/vsicurl/`, 42×42 células, TI 260–503), `api/termico.py`, camada `themis_ti` em `web/layers.js` | Camada térmica com valor real (Feature 01): cor por célula, `inercia_termica` no `/api/point`. Substitui a Day IR no mapa |
| **Mosaico global de referência** — `msss_atlas_simp_clon` | Mars Trek | `layers.yaml` (`smoke_test`) | Smoke test do adaptador WMTS — não é camada final de nenhuma feature |
| **Nomenclatura IAU/USGS** — webmap "Mars High-Resolution Mosaic Viewer" (item ArcGIS Online `b164957a19544f55a8d6a001c952a590`) | USGS Astrogeology / IAU Gazetteer, via API pública do ArcGIS Online | `data-pipeline/scripts/fetch_nomenclature.py` → `data/local/nomenclature.json` | Rotular feições do mapa com nomes oficiais (Feature 01) |

## 2. Trajeto, fotos e panoramas do rover Curiosity (MSL)

| Fonte | Instituição / produto | Onde é usada | Para quê |
|---|---|---|---|
| **MSL_waypoints.json** (posição por parada: sol/site/drive/lat/lon/elevação) | NASA/JPL · MMGIS (`mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json`) | `data-pipeline/scripts/fetch_rover_waypoints.py`, `data-pipeline/f03/etl/sources/public.py` (`PublicPositions`, `refresh_waypoints`), arquivo local em `data-pipeline/f03/dados/MSL_waypoints.json`, referenciado em `data-pipeline/f03/config.yaml` (`public.waypoints_url`) | Posição real do rover em cada parada — liga fotos, panoramas e séries de REMS/RAD a uma coordenada (Features 01, 03, 13) |
| **PLACES (posições intermediárias)** — `localized_interp.csv` | Origem não documentada explicitamente no código (dado derivado/interpolado de localização MSL; arquivo local em `data-pipeline/f03/dados/`) | `PublicPositions._load_places` em `data-pipeline/f03/etl/sources/public.py` | Reserva de posição para drives sem registro exato no MMGIS |
| **API de imagens brutas do MSL** (`raw_image_items`) | NASA/JPL (`mars.nasa.gov/api/v1/raw_image_items/`) | `PublicPhotos` em `data-pipeline/f03/etl/sources/public.py`; URL em `data-pipeline/f03/config.yaml` (`public.raw_images_api`); cache em `data/local/f03-cache/` | Fotos Navcam (NAV_LEFT_B/NAV_RIGHT_B) de cada parada, exibidas na feature de fotos/panorama (F03) |
| **Panoramas Navcam selecionados** — `panoramas.csv` + imagens em `dados_panoramas/panos/` | NASA/JPL (coletados via `mars.nasa.gov`, script próprio) | `data-pipeline/f03/coletar_panoramas.py`, `PublicPanos` em `etl/sources/public.py`, `data-pipeline/f03/config.yaml` (`public.panoramas_csv`) | Visualização panorâmica 360° no ponto (Feature 03, via Pannellum) |
| **Panorama colorido Mastcam** (`colored_image.jpg`, ex. `color_PIA26696B`) | NASA/JPL-Caltech/MSSS — página oficial `science.nasa.gov/resource/curiosity-rover-360-degree-panorama-nevado-sajama/` | `data-pipeline/f03/config.yaml` (`color_panos`) | Panorama colorido alternativo ao Navcam em preto-e-branco (F03) |
| **Fotos Mastcam dos alvos científicos** (ex. `4564ML1077430011801950C00_DXXX.jpg`) | NASA/JPL-Caltech/MSSS, baixadas via URL por `_mastcam()` em `data-pipeline/f03/etl/sources/science_public.py` | `data-pipeline/f03/dados/mastcam/`, usado pelas fichas científicas (F04) | Imagem do alvo estudado na ficha "pokédex" |

## 3. Dados científicos pontuais (PDS)

| Fonte | Instituição / produto | Onde é usada | Para quê |
|---|---|---|---|
| **REMS (clima/atmosfera)** — tabela ENVRDR calibrada, por sol | NASA MSL · PDS Atmospheres Node (`atmos.nmsu.edu/PDS/data/PDS4/msl_rems_bundle/data_calibrated/`) | `data-pipeline/adapters/pds_rems.py`, cache em `data-pipeline/scripts/cache_conditions.py`/`cache_climatologia.py` → `data/local/conditions/` | Painel de condições em tempo real (Feature 05) e climatologia histórica para previsão (Feature 06) |
| **RAD (radiação)** — arquivo `.TXT` por sol, seções `DOSIMETRY_TOTAL_DOSE_E` | NASA MSL · PDS-PPI/UCLA (`pds-ppi.igpp.ucla.edu/data/MSL-M-RAD-3-RDR-V1.0/DATA/`) | `data-pipeline/adapters/pds_rad.py`, mesmo cache de condições | Dose de radiação por observação, exibida no painel de condições (F05) e usada no custo de rota (F02) |
| **APXS** (óxidos por alvo) — arquivos `apb_*.csv` | NASA MSL · PDS Geosciences Node (`pds-geosciences.wustl.edu`) | `data-pipeline/f03/dados/pds/apxs/`, lidos por `read_apxs`/`PublicScience._apxs` em `data-pipeline/f03/etl/sources/science_public.py` | Composição química medida no alvo, ficha científica (F04) |
| **ChemCam / MOC** (óxidos por disparo de laser) — `moc_4489_4612.csv` etc. | NASA MSL · PDS Geosciences Node (`.../msl-m-chemcam-libs-4_5-rdr-v1/.../data/moc/`) | `data-pipeline/f03/dados/pds/chemcam/`, `read_moc`/`PublicScience._chemcam` | Composição química por laser, ficha científica (F04) |
| **CheMin** (mineralogia por difração) — arquivos `cmb_*.csv` | NASA MSL · PDS Geosciences Node | `data-pipeline/f03/dados/pds/chemin/`, `read_chemin`/`PublicScience._chemin` | Fração cristalina/minerais do alvo, ficha científica (F04) |
| **CRISM** (mineralogia de órbita) — produto MTRDR `FRT000058A3` | MRO · PDS Geosciences Node (`pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-mptargeted-v1/...`) | `data-pipeline/f03/etl/crism.py` (recorte), `data-pipeline/f03/dados/crism_boxwork.json`, amostrado por `PublicOrbital.sample` em `etl/sources/science_public.py`; config em `data-pipeline/f03/config.yaml` (`crism.su_url`/`crism.page_url`) | Indício mineral visto de órbita na ficha científica (F04) |

## 4. Algoritmos e dados derivados (sem download externo)

| Fonte | Instituição / referência | Onde é usada | Para quê |
|---|---|---|---|
| **Algoritmo Mars24** (Ls, Mars Sol Date) — Allison & McEwen (2000) | NASA GISS (`giss.nasa.gov/tools/mars24/help/algorithm.html`) | `api/tempo_marte.py`, usado por `api/alertas.py`, `api/previsao.py` | Cálculo de tempo/estação marciana sem precisar de rede (Feature 08 — modo sem Terra) |
| **Raio equatorial de Marte** (3 396 190 m, IAU) | Constante IAU, citada em `data-pipeline/adapters/mars_trek_wmts.py`, `data-pipeline/f03/config.yaml` (`mars_radius_m`), CLAUDE.md | Geometria marciana (haversine/bearing) em `api/geo.py` e no adaptador WMTS | Única implementação de geometria do app |

## 5. Dataset mencionado mas não integrado

| Fonte | Instituição / produto | Onde é citado | Status |
|---|---|---|---|
| **AI4Mars** (classe de terreno por pixel: solo, rocha-mãe, areia, rocha grande) | JPL/NASA, dataset CVPR 2021 (Swan et al.) — Zenodo (`ai4mars-dataset-merged-0.6.zip`, ~17,8 GB) e espelho em Parquet no Hugging Face | `api/alertas.py`, `api/raster_sampling.py`, `api/route_planning.py`, `data-pipeline/README.md`, `docs/Plano_Produto_Completo.md`, `feature-01-mapa-hiperlocal-boxwork.md` | **Não integrado.** O dataset não cobre a época/local da campanha do boxwork — `classe_ai4mars` é sempre devolvido como `null` no contrato da API (`/api/point`), nunca inventado. Tratado como "sem dado de areia", nunca como "sem areia" |

## 6. Bibliotecas de código front-end (vendorizadas em `web/lib/`)

| Biblioteca | Versão | Origem (de onde foi baixada) | Onde é usada | Para quê |
|---|---|---|---|---|
| **MapLibre GL JS** | v6.17.0 (comentário de licença no próprio arquivo aponta a tag da versão no GitHub) | `github.com/maplibre/maplibre-gl-js` | `web/lib/maplibre/maplibre-gl.mjs`, `maplibre-gl-worker.mjs`, `maplibre-gl.css`, usada pelo mapa principal (Feature 01) | Renderização do mapa em camadas, vetorial/raster |
| **Pannellum** | 2.5.6 (declarado no cabeçalho do arquivo) | `github.com/mpetroff/pannellum` | `web/lib/pannellum/pannellum.js` (front atual) e `web/f03/lib/pannellum.js` (front antigo do F03/F04) | Visualizador de panorama 360° (Feature 03) |
| **Leaflet** | Não documentada no código (sem comentário de versão no `.min.js` minificado) | Origem não documentada no código — presumivelmente `leafletjs.com`/CDN oficial, mas isso não está registrado no repositório | `web/f03/lib/leaflet.min.js` (só no front antigo de F03/F04, em `/f03/`) | Mapa do front antigo, antes da migração para MapLibre |

## 7. Fontes/tipografia vendorizadas

| Arquivo | Origem | Onde é usada |
|---|---|---|
| `chakra-400/500/600.woff2`, `jbmono.woff2`, `plex.woff2` | Origem não documentada no código (nomes sugerem as famílias Chakra Petch, JetBrains Mono e IBM Plex, mas não há comentário/README confirmando a fonte de download, ex. Google Fonts) | `web/fonts/` (front atual) e `web/f03/fonts/` (front antigo) — tipografia da interface |

## 8. Arquivos de imagem soltos em `api/` (não rastreados pelo git)

`api/hirise_optica.png`, `api/relevo_hillshade.png`, `api/themis_termica.png` aparecem como arquivos
não versionados (`git status`). Os mesmos nomes de camada (`hirise_optica`, `relevo_hillshade`,
`themis_termica`) existem em `web/layers.js` e `data-pipeline/db/populate_raster_registry.py`, mas
nenhum caminho de código referencia esses três arquivos `.png` especificamente dentro de `api/` —
**origem e propósito não documentados no código**; parecem saídas manuais de teste/depuração e não
fazem parte do pipeline de build (`make build`).

## 9. Citações bibliográficas e de contexto (não são dados, mas fundamentam decisões de produto)

Listadas em `docs/Plano_Produto_Completo.md` (seção "Fontes"):

- [NASA: Curiosity e o boxwork do Monte Sharp](https://www.nasa.gov/missions/mars-science-laboratory/curiosity-rover/NASAs-curiosity-rover-sees-martian-spiderwebs-up-close/)
- [NASA SUITS 2023–2024: descrição da missão em Marte](https://nasa.gov/wp-content/uploads/2023/09/fy24-suits-mission-description.pdf)
- [NASA: conceito de operações de EVA lunar (Artemis)](https://www.nasa.gov/wp-content/uploads/2020/01/topic_1-_eva_lunar_surface_concept_of_operations.pdf)
- [NASA: planejamento de EVAs lunares e AEGIS](https://ntrs.nasa.gov/api/citations/20250006988/downloads/ASCEND%20presentation%20-%20Planning%20Lunar%20EVAs.pdf)
- [NASA Ames: atraso de comunicação e operação autônoma](https://www.nasa.gov/ames/core-area-of-expertise-intelligent-and-adaptive-systems/)
- [AI4Mars (JPL, CVPR 2021)](https://openaccess.thecvf.com/content/CVPR2021W/AI4Space/papers/Swan_AI4MARS_A_Dataset_for_Terrain-Aware_Autonomous_Driving_on_Mars_CVPRW_2021_paper.pdf)
- [Previsão do tempo em Marte com redes neurais e REMS](https://ui.adsabs.harvard.edu/abs/2019EGUGA..2111304D/abstract)
- [Registro de marca de Douglas Adams](https://trademark.justia.com/owners/adams-douglas-643862)

Também citadas na mesma tabela de fontes de dados do plano de produto, sem adaptador de código ainda
implementado:

- **Poeira sazonal** — Climatologia de poeira do LMD (parceiros CNES/ESA), portal global — referenciada no plano, sem script de ETL no repositório.
- **Gelo raso** — SWIM (PSI, `swim.psi.edu`) — citada só como contexto ("Gale é equatorial, sem gelo acessível"), sem integração de dado.
