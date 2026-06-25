#!/usr/bin/env sh
set -eu

rm -rf .pytest_cache .ruff_cache .mypy_cache frontend/dist data/processed/resource_chunks.json
python scripts/seed_database.py
echo "Local environment reset."
