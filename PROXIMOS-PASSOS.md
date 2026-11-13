# Próximos passos — feature 01 (mapa hiperlocal do boxwork)

## Status das camadas (tabela da feature 01, seção 1)

| # | Camada | Status | `product_id` / fonte |
|---|---|---|---|
| 1 | Óptica detalhe — HiRISE 25cm | ✅ confirmado | `curiosity_hirise_mosaic` (WMTS) |
| 2 | Óptica contexto — CTX ~6m | ✅ confirmado | `Gale_CTX_BlockAdj_dd` (WMTS) |
| 3 | Topografia regional — MOLA | ✅ confirmado | `mola128_mola64_merge_90Nto90S_SimpleC_clon0` (ArcGIS) |
| 4 | Térmica — THEMIS | ✅ confirmado (só visual) | `THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018` (WMTS) |
| 5 | Mineralogia — CRISM | ⚠️ bloqueado | índice de observações, cobertura esparsa (ver abaixo) |
| 6 | Topografia local 1m — DTM HiRISE | ✅ confirmado | `Gale_DEM_SMG_1m` (ArcGIS, elevação real) + hillshade visual no mapa |
| 7 | Clima — REMS | ✅ confirmado | PDS Atmospheres Node, produto RNV por sol |
| 8 | Radiação — RAD | ✅ confirmado | PDS-PPI (UCLA), dose do detector E por observação |
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

## REMS (clima, item 7) resolvido ✅ (2026-11-11)

`adapters/pds_rems.py` baixa a tabela ambiental calibrada (ENVRDR) de
qualquer sol do PDS Atmospheres Node e extrai pressão, temperatura do
ar, UV e umidade. Testado com o sol 4650 (mesmo exemplo do doc da
feature 01): pressão ~709 Pa, temperatura -69.5°C de madrugada subindo
conforme o sol nasce, UV aparecendo a partir de ~6h local — tudo
plausível para Marte. Rodar: `python scripts/fetch_rems_test.py [sol]`.

**Estrutura real (não documentada publicamente, descoberta navegando o
diretório):**
`atmos.nmsu.edu/PDS/data/PDS4/msl_rems_bundle/data_calibrated/SOL_<lo>_<hi>/SOL<sol>/`
— pastas em buckets de ~90-135 sols, uma pasta por sol dentro. O produto
"RNV" é o ambiental calibrado (o que interessa); "ADR"/"RMD"/"RTL" são
outros níveis de processamento, não usados.

## RAD (radiação, item 8) resolvido ✅ (2026-11-11)

`adapters/pds_rad.py` baixa o arquivo real do sol em
`pds-ppi.igpp.ucla.edu/data/MSL-M-RAD-3-RDR-V1.0/DATA/SOL_<lo>_<hi>/RAD_RDR_<ano>_<doy>_<hh>_<mm>_<sol>_V00.TXT`
(mesma convenção de buckets `SOL_<lo>_<hi>` do REMS) e extrai a dose do
detector E (`DOSIMETRY_TOTAL_DOSE_E`) por observação, casada com o
horário (`OBSERVATION`) pelo mesmo índice `NN` — a dosimetria só existe
em índices pares (nem toda observação baixa telemetria completa).
Unidade: µGy/hora (confirmado no `RAD_RDR_SIS.HTM`, seção 4.2.1.6).

Testado contra o sol 4650: 87 leituras, dose média ~6.53 µGy/h → ~157
µGy/dia estimado, mesma ordem de grandeza da dose diária conhecida na
superfície de Marte. Rodar: `python scripts/fetch_rad_test.py [sol]`.

O arquivo tem 1306 seções no total (housekeeping, histogramas, LET,
PHA...) — só extraímos `OBSERVATION` e `DOSIMETRY_TOTAL_DOSE_E`,
suficiente pro painel de condições (feature 05). As outras seções são
análise científica fina, fora de escopo do MVP.

## Próximos blocos de trabalho

- [ ] **Fotos do rover** (item 9, feature 3 da Victoria) — **bloqueado
      por posição, não por foto**. A API pública de imagens
      (`mars.nasa.gov/api/v1/raw_image_items/`) funciona e devolve fotos
      reais (testado, sol 4650), mas `site`/`drive`/`xyz` vêm `null` --
      não dá posição. Tentei: índice PDS do volume Mastcam
      (`MSLMST_0032/INDEX/RDRINDEX.LBL`) tem `ROVER_MOTION_COUNTER`
      (site/drive), mas isso sozinho não converte pra lat/lon sem uma
      tabela de localização; procurei um traverse já publicado por
      terceiros (GeoJSON/CSV) e não achei nenhum atual. Conclusão: cada
      foto precisa de posição real e DIFERENTE pra "fotos próximas" (por
      raio) fazer sentido -- não dá pra usar posição aproximada única
      como fizemos pros alvos científicos, isso falsearia a busca por
      distância. Resolver exige o mesmo processo que destravou o
      product_id do CTX: abrir o MMGIS/Mars Trek no navegador com
      DevTools e capturar o endpoint real de posição por site/drive.
      **Depende do item 11 (abaixo), não é independente.**
- [x] ~~AI4Mars~~ (item 10) — **bloqueador estrutural, não de busca**:
      testei o mirror `harpreetsahota/ai4mars-msl` no Hugging Face
      (23.400 imagens reais). A imagem mais recente do dataset
      corresponde a **~sol 2579 (nov/2019)** -- quase 2000 sóis ANTES da
      campanha de boxwork (sol 4564-4660, set/2025). O dataset foi
      publicado em 2021, antes do Curiosity chegar no boxwork -- não
      existe (e não pode existir) classificação AI4Mars pra essa região,
      independente de quanto se procure. Item encerrado como
      definitivamente indisponível, não como pendência.
- [ ] **MMGIS** (item 11): trajeto do rover por sol/site/drive → lat/lon
      — liga fotos e clima/radiação a uma coordenada real. Bloqueador
      real pro item 9 (ver acima).
- [ ] **Nomenclatura** (item 12): USGS/IAU Gazetteer.

## Pendências gerais

- [x] ~~Estruturar alvos científicos~~ **parcial**: 3 achados reais e
      citáveis da campanha de boxwork 2025 (cristas cimentadas por
      sulfato, furo "Altadena", alvos "Totoral/Sillar") inseridos via
      `db/seed_science_targets.py` — posições são **aproximadas**
      (nenhuma fonte pública dá lat/lon exata do alvo, só sol e nome
      informal). O conjunto completo de 8-10 alvos (ficha "pokédex") é
      trabalho da feature 4 (Victoria), isto só desbloqueia a categoria
      "medições do Curiosity como pontos" da feature 01 com o mínimo
      real.
- [ ] Confirmar tudo contra a aba Resources assim que abrir (sexta) —
      nenhuma integração é definitiva antes disso.
- [ ] Quando a posição real do rover nos sóis 4564/4600-4606/4650 for
      localizada (MMGIS ou PDS), substituir as coordenadas aproximadas
      acima pelas reais.

## Banco local + API resolvidos ✅ (2026-11-11)

- `data-pipeline/db/schema.sql`: `rover_images`, `science_targets`,
  `raster_registry` + índices espaciais via **R-Tree nativo do SQLite**
  (sem precisar de SpatiaLite/GDAL — mais simples de rodar em qualquer
  máquina do time). `populate_raster_registry.py` já carrega as 5
  camadas raster confirmadas.
- `api/main.py`: `GET /api/point?lat&lon` funcionando de verdade.
  Testado: `lat=-4.59&lon=137.44` devolve elevação real da DTM
  (-4503m, slope 3.55°) e da MOLA (-4501m, slope 0.62°) — consistente
  entre as duas fontes. Fora do bbox devolve vazio sem quebrar.
- **Pendente:** `nearby_photos`/`science_target` têm a lógica pronta
  (busca por raio real, distância/bearing calculados com o raio de
  Marte) mas as tabelas estão vazias até os itens 9 (fotos MSL) e 4
  (alvos científicos) serem resolvidos.
- **Fora de escopo do sampling:** camadas `tiles_wmts` (CTX, HiRISE
  óptica, THEMIS) são tiles PNG sem georreferência por arquivo — só
  servem pra exibir no mapa, não pra consultar valor num ponto.

## Frontend resolvido ✅ (2026-11-11)

`frontend/` (React + Vite + TS + MapLibre GL), tema HUD/centro de
missão. Núcleo funcionando com dado 100% real:
- Mapa com CTX/HiRISE/Relevo(hillshade)/THEMIS, cada um com
  toggle+opacidade (`LayerControlPanel`) — os tiles WMTS não dão pra
  servir como fonte `tiles` XYZ padrão do MapLibre (grade do Mars Trek
  não é Web Mercator, ver `api/mosaics.py`), por isso viram mosaico
  único (`GET /mosaics/{layer}.png`) exibido via `ImageSource`.
- Relevo: hillshade real gerado na hora a partir do DTM
  (`build_hillshade_png`, fórmula Horn/ESRI, não é algoritmo oficial
  calibrado mas usa elevação real).
- Clique no ponto → `PointInfoPanel`: veredito de segurança colorido
  (slope vs. limite de 20° da Artemis, ver `raster_sampling.classify_slope`),
  fotos próximas e ficha científica (agora com os 3 alvos reais acima).
- `ConditionsPanel`: REMS+RAD do sol de referência (4650), cacheado
  localmente (`data-pipeline/scripts/cache_conditions.py`) — sem
  chamada de rede em tempo de request.
- "Geofísica: fora de escopo" e "Mineralogia (CRISM): em breve"
  explícitos no painel de camadas (spec pedia "dizer isso com clareza").

**Pendente nessa frente:** a "continuidade" do zoom é por overzoom de
uma única amostra por camada (não uma pirâmide completa) — ver nota em
`frontend/src/map/style.ts`. O bbox usado em tudo isto ainda é a
amostra de teste, não o boxwork final.

## Próximo passo

- Fotos do rover (item 9) / MMGIS (item 11) pra popular `rover_images`
  e ativar `nearby_photos` de verdade, OU
- Confirmar o bbox final do boxwork (pendência de equipe/Resources).

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
