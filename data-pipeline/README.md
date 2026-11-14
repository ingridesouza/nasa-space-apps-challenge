# data-pipeline

Ingestão e normalização dos dados reais (Mars Trek, PDS, API de imagens do
MSL, AI4Mars, MMGIS) para o schema interno usado pela feature 01
(`raster_registry`; fotos e alvos científicos vêm do ETL em `f03/` — ver
`feature-01-mapa-hiperlocal-boxwork.md` na raiz do repo, seção 3.1).

## Estrutura

- `adapters/` — um adaptador por fonte de dado. Cada um implementa
  `LayerAdapter` (`adapters/base.py`) e isola o formato bruto daquela
  fonte. Trocar a fonte oficial (pós aba Resources de sexta) deve ser
  mudança de **config**, não de lógica.
- `config/layers.yaml` — qual adaptador/produto/bbox usar por camada.
- `scripts/` — scripts de execução/teste do pipeline.

## Setup

```bash
cd data-pipeline
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## Teste rápido (adaptador CTX)

```bash
python scripts/fetch_ctx_test.py
```

Isso confirma, com dado real, que: o `GetCapabilities` do produto existe,
o template de tile é lido corretamente do XML (nunca chutado), e a
conversão lat/lon → row/col bate com a cobertura real do bbox de teste.

**Atenção:** `product_id` em `config/layers.yaml` é um placeholder — ver
pendência de confirmação no `feature-01-mapa-hiperlocal-boxwork.md`,
seção 5.
