#!/usr/bin/env bash
set -euo pipefail

# Run full repo tests in a reproducible way.
# - creates a virtualenv at .venv if missing
# - installs requirements
# - sets PYTHONPATH and demo classifier env
# - runs pytest and saves output to test-results.txt

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  echo "Creating virtualenv .venv..."
  python -m venv .venv
fi

echo "Activating virtualenv and installing requirements..."
source .venv/bin/activate
pip install --upgrade pip >/dev/null
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
fi

export PYTHONPATH=.
export USE_DEMO_CLASSIFIER=1
# default sqlite file for SQLAlchemy-backed tests (override externally if needed)
export CLASSIFIER_DB_URL=${CLASSIFIER_DB_URL:-"sqlite+pysqlite:///./classifier_test.db"}

echo "Running pytest (quiet)..."
pytest -q "$@" | tee test-results.txt
rc=${PIPESTATUS[0]:-0}

echo "Tests finished with exit code $rc. Output saved to test-results.txt"
exit $rc
