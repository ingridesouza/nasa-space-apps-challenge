PY := $(CURDIR)/.venv/bin/python
# Agente local (feature 08): o modelo fica no pacote offline, não no git (3,3 GB > limite do GitHub).
# Copiar data/local/ inteiro leva junto o modelo; o binário do ollama se instala uma vez.
# Gemma 3 4B (Google)
# venceu o Llama 3.2 3B nas mesmas perguntas (achou o alvo e a previsão; o Llama errou as duas).
MODELO := gemma3:4b
export OLLAMA_MODELS := $(CURDIR)/data/local/ollama
OLLAMA_SOBE = command -v ollama >/dev/null && (curl -s localhost:11434 >/dev/null || (ollama serve >/dev/null 2>&1 &))

.PHONY: build run front test

build:
	test -x $(PY) || python3 -m venv .venv
	$(PY) -m ensurepip
	$(PY) -m pip install -r data-pipeline/requirements.txt -r api/requirements.txt
	cd data-pipeline && \
	$(PY) scripts/fetch_dtm_test.py && \
	$(PY) scripts/fetch_ctx_test.py ctx_optica && \
	$(PY) scripts/fetch_ctx_test.py hirise_optica && \
	$(PY) scripts/fetch_ctx_test.py themis_termica && \
	$(PY) scripts/fetch_nomenclature.py && \
	$(PY) scripts/fetch_rover_waypoints.py && \
	$(PY) scripts/cache_conditions.py && \
	$(PY) scripts/cache_climatologia.py && \
	$(PY) db/populate_raster_registry.py && \
	$(PY) db/seed_rover_images.py && \
	$(PY) scripts/download_rover_photos.py && \
	$(PY) db/seed_science_targets.py
	@if command -v ollama >/dev/null; then $(OLLAMA_SOBE); sleep 3; ollama pull $(MODELO); \
	else echo "ollama não instalado: sem agente (/api/ask responde 503; os alertas seguem). Instale e rode make build de novo."; fi

run:
	@$(OLLAMA_SOBE) || echo "ollama não instalado: /api/ask responde 503; os alertas seguem"
	cd api && $(PY) -m uvicorn main:app --reload

front:
	@echo "Front servido pela API: rode 'make run' e abra http://localhost:8000"

test:
	cd api && $(PY) test_alertas.py && $(PY) test_agente.py && $(PY) test_f03.py && $(PY) test_previsao.py
