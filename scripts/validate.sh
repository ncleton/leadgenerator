#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

uv run --project plugins/leadgenerator black --check plugins/leadgenerator/src tests
uv run --project plugins/leadgenerator ruff check plugins/leadgenerator/src tests
uv run --project plugins/leadgenerator pytest -c plugins/leadgenerator/pyproject.toml
python3 scripts/check_distribution_privacy.py
python3 scripts/agent-privacy-check.py guard --root . --tracked
