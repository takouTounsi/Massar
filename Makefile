PYTHON ?= python

.PHONY: test seed demo generate-data ingest lint format

test:
	$(PYTHON) -m pytest -q

seed:
	$(PYTHON) scripts/seed_database.py

demo:
	$(PYTHON) scripts/run_demo.py

generate-data:
	$(PYTHON) scripts/generate_synthetic_profiles.py

ingest:
	$(PYTHON) scripts/ingest_knowledge_base.py

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy shared services tests

format:
	$(PYTHON) -m ruff format .
