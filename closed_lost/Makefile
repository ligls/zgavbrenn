# Closed Lost renewal workbench
#
#   make install   - Python deps + npm deps
#   make import    - xlsx -> data/opportunities.json + data/closed_lost.sqlite (+ validation report)
#   make run       - build the front end if needed, then serve everything on http://127.0.0.1:8765
#   make dev       - Flask API + Vite dev server with hot reload (http://127.0.0.1:5173)
#   make build     - rebuild frontend/dist
#   make standalone - one self-contained HTML file (data embedded) -> data/Closed_Lost_Workbench.html
#   make sheets    - collaboration workbook for Google Sheets -> data/Closed_Lost_Q4_2024_collaboration.xlsx
#   make test      - parser / repair / hint unit tests
#
# Override the source file: make import XLSX=path/to/Closed_Lost_....xlsx
# Rows whose Opportunity Name matches EXCLUDE (case-insensitive regex) are dropped at import.
# Default drops renewal opportunities: renewal(s), renew, the typo renwal, and the RNW / RNWL / RNWLS
# abbreviations. Use `make import EXCLUDE=` to keep everything, or EXCLUDE=renewal for the word alone.

PY   ?= python3
PORT ?= 8765
EXCLUDE ?= renew|renwal|(?<![a-z])rnw(?:ls?)?(?![a-z])
EXCLUDE_LABEL ?= renewal / RNW
XLSX ?= $(firstword $(wildcard ../Closed_Lost*.xlsx Closed_Lost*.xlsx data/Closed_Lost*.xlsx))

.PHONY: install import run dev build standalone sheets test clean

install:
	$(PY) -m pip install -r requirements.txt
	cd frontend && npm install

import:
	$(PY) importer/import_data.py $(XLSX) $(if $(EXCLUDE),--exclude-name "$(EXCLUDE)" --exclude-label "$(EXCLUDE_LABEL)")

build:
	cd frontend && npm install --no-audit --no-fund && npm run build

standalone:
	cd frontend && npm install --no-audit --no-fund && npm run build:standalone
	$(PY) importer/build_standalone.py

sheets:
	$(PY) importer/export_sheets.py $(if $(EDITS),--edits "$(EDITS)")

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
	rm -rf frontend/dist frontend/dist-standalone importer/__pycache__ importer/tests/__pycache__ .pytest_cache
