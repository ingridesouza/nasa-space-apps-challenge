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

## Bloqueador atual

- **Descobrir o `product_id` do HiRISE DEM de Gale.** No mesmo painel de
  busca "Gale Crater" apareceu um resultado **"MRO HiRISE, Gale Crater
  DEM"** — é bem provável que seja exatamente o DTM de 1 m pendente (item
  6 da tabela do doc da feature 01). Repetir o processo: clicar no
  resultado → **Add** → pegar a Request URL do `WMTSCapabilities.xml`
  novo no Network → atualizar/criar entrada em `layers.yaml`.
  - Atenção: a tabela da feature 01 diz que o DTM "não é WMTS genérico"
    e pode estar em GeoTIFF via PDS Annex/USGS em vez de WMTS — se o
    resultado do Trek for só uma visualização e não o dado bruto
    utilizável para sampling de elevação, pode ser necessário achar o
    produto real no PDS Annex do HiRISE mesmo assim.
  - Depois, repetir para MOLA e THEMIS (itens 3-4 da tabela) buscando
    pelo nome do local no mesmo painel.

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
