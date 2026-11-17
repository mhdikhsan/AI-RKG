# Core AI Risk KG pipeline. Each target delegates to scripts/run.py, so the same
# steps also work without make:  python -m scripts.run <target>
ifeq ($(OS),Windows_NT)
  PY ?= .venv/Scripts/python
else
  PY ?= .venv/bin/python
endif

.PHONY: all fetch stage map roles authored merge validate coverage report site check-ontology test venv

all:
	$(PY) -m scripts.run all

fetch stage map roles authored merge validate coverage report site check-ontology:
	$(PY) -m scripts.run $@

test:
	$(PY) -m pytest -q tests llm_mitigation/tests

venv:
	python -m venv .venv
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e llm_mitigation
