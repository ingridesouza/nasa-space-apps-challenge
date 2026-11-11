# Próximos passos — feature 01 (mapa hiperlocal do boxwork)

## CTX resolvido ✅ (2026-11-11)

`product_id` real confirmado: **`Gale_CTX_BlockAdj_dd`** — mosaico CTX
específico de Gale (não o global genérico), já em
`data-pipeline/config/layers.yaml`. Testado e validado:
`python scripts/fetch_ctx_test.py ctx_optica` baixa tiles reais (6 m/px,
terreno com crateras confirmado visualmente).

**Como foi achado (repetir para as próximas camadas):** no
`trek.nasa.gov/mars`, abrir o painel **Search**, digitar o nome do local
(ex. "Gale Crater"), clicar no resultado específico (ex. "MRO CTX, Gale
Crater Mosaic") e no botão verde **Add** — isso injeta a camada no mapa
de verdade e dispara a request real do `WMTSCapabilities.xml` (visível
no DevTools → Network, filtrando por `Capabilities`). Bem mais confiável
que tentar adivinhar o `product_id` ou navegar/zoom manualmente — a
busca já teve dois resultados específicos de Gale (CTX e HiRISE DEM) no
mesmo lugar.

## DTM HiRISE 1m resolvido ✅ (2026-11-11)

Camada `dtm_hirise_1m`: produto **`Gale_DEM_SMG_1m`**, servido via
ArcGIS ImageServer (`adapters/arcgis_image_server.py`), confirmado com
valores reais de elevação (-4531 m a -4476 m, consistente com o piso da
Cratera Gale). Resolve o item 6 da tabela da feature 01 — a tabela
previa que seria preciso ir atrás do PDS Annex/USGS, mas o próprio Mars
Trek já serve o dado bruto (não só visualização) via `exportImage`.
Testado: `python scripts/fetch_dtm_test.py`.

## Ferramenta de busca automatizada

`scripts/lookup_mars_trek_product.py "<termo>" --details` substitui o
processo manual de DevTools para achar `product_id`/endpoint de
qualquer produto do Mars Trek. Endpoint descoberto inspecionando o
`jpl/config/config.json` do próprio site.

## MOLA e THEMIS resolvidos ✅ (2026-11-11)

- `mola_topografia_regional`: produto global
  `mola128_mola64_merge_90Nto90S_SimpleC_clon0`, via ArcGIS (elevação
  real testada: -4513 m a -4465 m, consistente com a HiRISE).
- `themis_termica`: produto global
  `THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018`, só WMTS (imagem IR
  renderizada, sem valor de temperatura amostrável por pixel — serve só
  como camada visual, não para sampling numérico).

## Bloqueador real: CRISM (mineralogia) não é uma camada simples

Diferente das outras, CRISM **não tem um raster pronto de mineral por
pixel** no Mars Trek — o que existe é um índice de observações pontuais
(`mars_mro_crism_mtrdr_c0a_humex_frt_sites`, serviço `ArcGISFeature`).
Consultei esse índice contra toda a extensão da Cratera Gale e só achei
**3 observações CRISM** (`FRT0000A091`, `FRT000037DF`, `FRT000045F2`),
nenhuma cobrindo o bbox de teste do boxwork usado até agora — a mais
próxima fica a ~60 km de distância.

**Isso é um risco real para a feature 4 (ficha científica/CRISM) e
precisa ser resolvido assim que o recorte final do boxwork for
decidido:**
- [ ] Repetir a consulta de bbox contra
      `mars_mro_crism_mtrdr_c0a_humex_frt_sites/MapServer/0/query` com
      as coordenadas REAIS do boxwork escolhido (não o bbox de teste) —
      ver se alguma das 3 observações (ou outras fora do recorte atual
      de busca) realmente intersecta.
- [ ] Se não houver cobertura CRISM no boxwork exato: usar o campo
      `medicao_curiosity` (texto, já previsto no schema
      `science_targets`) como fonte principal de mineralogia — o
      próprio doc da feature 01 já trata isso como complementar
      ("medições do Curiosity como pontos"), não como bloqueador.
- [ ] Se houver: baixar o produto via `ProdURL` (aponta pro PDS/ODE,
      `ode.rsl.wustl.edu`), não pelo Mars Trek.

## O que já está pronto e validado

- `data-pipeline/adapters/mars_trek_wmts.py`: adaptador genérico WMTS,
  testado contra dado real do Mars Trek (produto `msss_atlas_simp_clon`,
  ver `smoke_test` em `config/layers.yaml`). Faz `GetCapabilities`,
  converte lat/lon → tile (geográfico e projetado), baixa o tile.
- Dois bugs reais já corrigidos durante o teste: campos numéricos do
  XML vindo como float (`"2.0"`), e `TopLeftCorner` em graus vs. metros
  dependendo do CRS do produto.

## Pendências de pesquisa (sem depender do pipeline — podem rodar em paralelo)

- [ ] ID exato do DTM HiRISE de 1 m do boxwork (PDS Annex do HiRISE /
      USGS Astrogeology).
- [ ] Baixar ~200 imagens do boxwork via API de imagens do MSL, para
      teste offline de busca por raio (feature 3).
- [ ] Estruturar os 8-10 alvos científicos da ficha "pokédex" a partir
      de notícias/blog do Curiosity e do PDS (feature 4).
- [ ] Confirmar tudo contra a aba Resources assim que abrir (sexta) —
      nenhuma integração é definitiva antes disso.

## Depois do CTX resolvido

- Banco local (SQLite + SpatiaLite/GeoPackage) com as tabelas
  `rover_images`, `science_targets`, `raster_registry`.
- Endpoint `GET /api/point?lat&lon` em `api/` (contrato reusado pela
  feature 02 de Hugo e pela feature 08).
- Primeiro protótipo de mapa em `frontend/` (MapLibre GL) consumindo os
  tiles locais gerados pelo pipeline.
