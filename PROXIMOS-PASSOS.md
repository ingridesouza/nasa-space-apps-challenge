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
| 7 | Clima — REMS | ✅ confirmado | PDS Atmospheres Node, produto RNV por sol |
| 8 | Radiação — RAD | ⚠️ dado real achado, parser pendente | PDS-PPI (UCLA), formato complexo (1306 seções) |
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

## RAD (radiação, item 8): dado real confirmado, mas formato complexo

Achei o arquivo real do sol 4650 em
`pds-ppi.igpp.ucla.edu/data/MSL-M-RAD-3-RDR-V1.0/DATA/SOL_<lo>_<hi>/RAD_RDR_<ano>_<doy>_<hh>_<mm>_<sol>_V00.TXT`
(mesma convenção de buckets `SOL_<lo>_<hi>` do REMS). Confirmei um valor
real de dose em `[DOSIMETRY_TOTAL_DOSE_E: 00]` = `6.64562` (unidade a
confirmar na documentação SIS).

**Por que não virou adaptador ainda:** o arquivo tem **1306 seções**
num formato texto proprietário (housekeeping, histogramas, LET,
dosimetria por detector...), bem mais complexo que o CSV do REMS. Não é
um bloqueador de disponibilidade de dado — é só mais trabalho de parser
dedicado.

- [ ] Escrever parser focado só no que a feature 05 precisa: extrair
      `DOSIMETRY_TOTAL_DOSE_E` (dose total, detector E) por sol — não
      tentar parsear as outras ~1300 seções (histogramas/LET/PHA são
      para análise científica fina, fora de escopo do MVP).
- [ ] Confirmar a unidade real do valor de dose na documentação SIS
      (`RAD_EDR_SIS.HTM` / RDR equivalente) antes de exibir na UI.

## Próximos blocos de trabalho

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
