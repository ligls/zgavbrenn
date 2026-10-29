# Closed Lost renewal workbench
#
#   make install   - Python deps + npm deps
#   make import    - xlsx -> data/opportunities.json + data/closed_lost.sqlite (+ validation report)
#   make run       - build the front end if needed, then serve everything on http://127.0.0.1:8765
#   make dev       - Flask API + Vite dev server with hot reload (http://127.0.0.1:5173)
#   make build     - rebuild frontend/dist
#   make test      - parser / repair / hint unit tests
#
# Override the source file: make import XLSX=path/to/Closed_Lost_....xlsx

PY   ?= python3
PORT ?= 8765
XLSX ?= $(firstword $(wildcard ../Closed_Lost*.xlsx Closed_Lost*.xlsx data/Closed_Lost*.xlsx))

.PHONY: install import run dev build test clean

install:
	$(PY) -m pip install -r requirements.txt
	cd frontend && npm install

import:
	$(PY) importer/import_data.py $(XLSX)

build:
	cd frontend && npm install --no-audit --no-fund && npm run build

run:
	@test -f frontend/dist/index.html || $(MAKE) build
	$(PY) server/server.py --port $(PORT)

dev:
	@trap 'kill 0' INT TERM EXIT; \
	$(PY) server/server.py --port $(PORT) & \
	cd frontend && npm run dev

test:
	$(PY) -m pytest importer/tests -q

clean:
	rm -rf frontend/dist importer/__pycache__ importer/tests/__pycache__ .pytest_cache
