#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_PYTHON:-${REPO_DIR}/.venv/bin/python}"
CURRENT_YEAR="$(date +%Y)"
FROM_YEAR="$((CURRENT_YEAR - 1))"

cd "${REPO_DIR}"
PYTHONPATH=packages "${PYTHON_BIN}" -m data_pipeline.cli refresh-moc \
  --from-year "${FROM_YEAR}" \
  --to-year "${CURRENT_YEAR}"
