PY := $(CURDIR)/.venv/bin/python
# Local agent (feature 08): the model lives in the offline package, not in git (3.3 GB > GitHub limit).
# Copying the whole data/local/ carries the model along; the ollama binary is installed once.
# Gemma 3 4B (Google)
# beat Llama 3.2 3B on the same questions (found the target and the forecast; Llama got both wrong).
MODEL := gemma3:4b
export OLLAMA_MODELS := $(CURDIR)/data/local/ollama
OLLAMA_UP = command -v ollama >/dev/null && (curl -s localhost:11434 >/dev/null || (ollama serve >/dev/null 2>&1 &))

.PHONY: build run front test

build:
	test -x $(PY) || python3 -m venv .venv
	$(PY) -m ensurepip
	$(PY) -m pip install -r data-pipeline/requirements.txt -r api/requirements.txt
	cd data-pipeline && \
	$(PY) scripts/fetch_dtm_test.py && \
	$(PY) scripts/fetch_insolation_relief.py && \
	$(PY) scripts/fetch_ctx_test.py ctx_optical && \
	$(PY) scripts/fetch_ctx_test.py hirise_optical && \
	$(PY) scripts/fetch_themis_ti.py && \
	$(PY) scripts/fetch_nomenclature.py && \
	$(PY) scripts/fetch_rover_waypoints.py && \
	$(PY) scripts/cache_conditions.py && \
	$(PY) scripts/cache_climatology.py && \
	$(PY) scripts/cache_atmosphere_track.py && \
	$(PY) db/populate_raster_registry.py && \
	cd f03 && $(PY) etl/build.py
	@if command -v ollama >/dev/null; then $(OLLAMA_UP); sleep 3; ollama pull $(MODEL); \
	else echo "ollama not installed: no agent (/api/ask returns 503; alerts keep working). Install it and run make build again."; fi

run:
	@$(OLLAMA_UP) || echo "ollama not installed: /api/ask returns 503; alerts keep working"
	cd api && $(PY) -m uvicorn main:app --reload

front:
	@echo "Front is served by the API: run 'make run' and open http://localhost:8000"

test:
	cd api && $(PY) test_alerts.py && $(PY) test_agent.py && $(PY) test_forecast.py && $(PY) -m pytest -q test_f03.py
