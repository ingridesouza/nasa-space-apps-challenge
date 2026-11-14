# api

Endpoint `GET /api/point?lat&lon` descrito em
`feature-01-mapa-hiperlocal-boxwork.md` (seção 3.2). Contrato
reaproveitado pela feature 02 (rota/A*, Hugo) e feature 08 (assistente
de voz) — mudanças de schema aqui devem ser alinhadas com o time antes
de aplicadas.

## Rodar localmente

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Testar: `http://127.0.0.1:8000/api/point?lat=-4.59&lon=137.44`

## Status

- ✅ **Sampling de raster** (elevação + slope): funciona de verdade para
  qualquer camada do tipo `raster_unico` no `raster_registry` (hoje:
  DTM HiRISE 1m e MOLA). Slope calculado por diferença finita numa
  janela 3x3 — simples, não é um algoritmo "oficial" de slope, mas usa
  dado de elevação real.
- ✅ **Fotos próximas e alvo científico**: busca por raio via R-Tree
  nativo do SQLite nas tabelas do F03/F04 (`photos`, `targets`,
  `measurements`), geradas por `data-pipeline/f03/etl/build.py`.
- ❌ **Camadas `tiles_wmts`** (CTX, HiRISE óptica, THEMIS) não entram no
  sampling — são tiles PNG sem georreferência individual, precisariam
  virar um mosaico georreferenciado antes (fora de escopo do MVP).

## Banco local

Schema e scripts de população ficam em `../data-pipeline/db/` (schema
compartilhado entre pipeline de ingestão e API). Rodar
`python data-pipeline/db/populate_raster_registry.py` depois de baixar
novas camadas raster.
