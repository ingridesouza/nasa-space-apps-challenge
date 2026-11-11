# Próximos passos — feature 01 (mapa hiperlocal do boxwork)

## Bloqueador atual

- **Descobrir o `product_id` real do CTX no Mars Trek.** O chute inicial
  (`Mars_MRO_CTX_mosaic_global_6m`) dá 404 — não existe no catálogo com
  esse nome, e não há um endpoint público de índice/catálogo documentado
  para buscar por nome.
  - Caminho: abrir `trek.nasa.gov/mars` no navegador, DevTools → Network
    → marcar **Keep log** → ativar a camada CTX no painel de camadas do
    site → procurar no Network por `xml` ou `tiles/Mars` (não `wmts` —
    não aparece literalmente na URL) → copiar a Request URL → o
    `product_id` é o trecho entre `/EQ/` e `/1.0.0/`.
  - Depois de achar: atualizar `product_id` em
    `data-pipeline/config/layers.yaml` (entrada `ctx_optica`) e rodar
    `python scripts/fetch_ctx_test.py ctx_optica` para validar.
  - Repetir o mesmo processo para HiRISE, MOLA e THEMIS (itens 1-4 da
    tabela do doc da feature 01) depois que o CTX funcionar — o
    adaptador (`MarsTrekWMTSAdapter`) já serve para qualquer um deles,
    só muda a config.

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
