#!/usr/bin/env bash
# CI local: correrlo ANTES de empujar. Sale distinto de cero si algo falla.
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado --quiet
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy
uv run lint-imports
uv run python plan/construir_dag.py --comprobar
uv run python plan/dag.py validar
uv run python plan/dag.py estado --comprobar
uv run pytest
