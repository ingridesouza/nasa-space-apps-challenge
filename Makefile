PY := $(CURDIR)/.venv/bin/python

.PHONY: build run front

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
	$(PY) db/populate_raster_registry.py && \
	$(PY) db/seed_rover_images.py && \
	$(PY) db/seed_science_targets.py
	cd frontend && npm install && (test -f .env || cp .env.example .env)

run:
	cd api && $(PY) -m uvicorn main:app --reload

front:
	cd frontend && npm run dev
