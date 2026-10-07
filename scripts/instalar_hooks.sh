#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
git config core.hooksPath scripts/hooks
echo "hooks instalados: core.hooksPath = scripts/hooks"
