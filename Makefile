PY := $(CURDIR)/.venv/bin/python
# Agente local (feature 08): o modelo fica no pacote offline, não no git (3,3 GB > limite do GitHub).
# Copiar data/local/ inteiro leva junto o modelo; o binário do ollama se instala uma vez.
# Gemma 4 E2B (Google): 6/6 em make agente-medir, com tool calling; e4b, granite4 e phi4-mini fizeram 2/6
# (sem chamar a ferramenta ou dizendo "seguro"). Precisa de Ollama novo (o 0.12.11 do Fedora não carrega o gemma4).
MODELO := gemma4:e2b
# Ollama instalado no usuário (~/.local/ollama, release oficial) vem antes do do sistema, se existir.
export PATH := $(HOME)/.local/ollama/bin:$(PATH)
export OLLAMA_MODELS := $(CURDIR)/data/local/ollama
OLLAMA_SOBE = command -v ollama >/dev/null && (curl -s localhost:11434 >/dev/null || (ollama serve >/dev/null 2>&1 &))

.PHONY: build run front test voz-gravar voz-medir agente-medir

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
	cd f03 && $(PY) etl/build.py
	# Voz (F08): Whisper no pacote offline, como o modelo do agente (escolha medida em make voz-medir)
	$(PY) -c "from faster_whisper import download_model as d; [d(m, cache_dir='data/local/whisper') for m in ('large-v3', 'turbo')]"
	@if command -v ollama >/dev/null; then $(OLLAMA_SOBE); sleep 3; ollama pull $(MODELO); \
	else echo "ollama não instalado: sem agente (/api/ask responde 503; os alertas seguem). Instale e rode make build de novo."; fi

run:
	@$(OLLAMA_SOBE) || echo "ollama não instalado: /api/ask responde 503; os alertas seguem"
	cd api && $(PY) -m uvicorn main:app --reload

front:
	@echo "Front servido pela API: rode 'make run' e abra http://localhost:8000"

test:
	cd api && $(PY) test_alertas.py && $(PY) test_agente.py && $(PY) test_previsao.py && $(PY) test_voz.py && $(PY) -m pytest -q test_f03.py
	@if command -v node >/dev/null; then node web/test_voz.mjs; else echo "node ausente: pulei web/test_voz.mjs"; fi

# Fase 0 da voz: grava as frases no microfone da demo e compara os modelos Whisper
voz-gravar:
	cd api && $(PY) medir_voz.py --gravar

voz-medir:
	cd api && $(PY) medir_voz.py large-v3 turbo

agente-medir:
	cd api && $(PY) medir_agente.py gemma4:e2b granite4 phi4-mini
