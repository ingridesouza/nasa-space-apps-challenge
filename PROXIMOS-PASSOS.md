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

## Bloqueador atual

- Repetir a busca automatizada para achar MOLA e THEMIS (itens 3-4 da
  tabela da feature 01), e CRISM (mineralogia) — buscar por termos como
  `"MOLA Gale"`, `"THEMIS Gale"`, `"CRISM Gale"` com o script acima.
  Se não aparecer nada específico de Gale, cair pro produto global
  (MOLA e THEMIS são cobertura completa do planeta, então deve existir
  algo tipo "MOLA Elevation" sem o nome do local).

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
