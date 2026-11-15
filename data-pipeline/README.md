# data-pipeline

Ingestion and normalization of the real data (Mars Trek, PDS, MSL image
API, AI4Mars, MMGIS) into the internal schema used by feature 01
(`raster_registry`; photos and science targets come from the ETL in `f03/` — see
`feature-01-mapa-hiperlocal-boxwork.md` at the repo root, section 3.1).

## Structure

- `adapters/` — one adapter per data source. Each implements
  `LayerAdapter` (`adapters/base.py`) and isolates that source's raw
  format. Switching the official source (after Friday's Resources tab)
  should be a **config** change, not a logic change.
- `config/layers.yaml` — which adapter/product/bbox to use per layer.
- `scripts/` — pipeline run/test scripts.

## Setup

```bash
cd data-pipeline
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## Quick test (CTX adapter)

```bash
python scripts/fetch_ctx_test.py
```

This confirms, with real data, that: the product's `GetCapabilities` exists,
the tile template is read correctly from the XML (never guessed), and the
lat/lon → row/col conversion matches the real coverage of the test bbox.

**Note:** `product_id` in `config/layers.yaml` is a placeholder — see the
pending confirmation in `feature-01-mapa-hiperlocal-boxwork.md`,
section 5.
