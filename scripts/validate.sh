#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

uv run --project plugins/lead-studio black --check plugins/lead-studio/src tests
uv run --project plugins/lead-studio ruff check plugins/lead-studio/src tests
uv run --project plugins/lead-studio pytest -c plugins/lead-studio/pyproject.toml
python3 scripts/check_distribution_privacy.py
python3 scripts/agent-privacy-check.py guard --root . --tracked
