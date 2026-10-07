#!/usr/bin/env bash
# Borra del PC lo que instaló este proyecto: el venv (vive en el repo) y, de la caché global de uv, SÓLO los paquetes del SDK
# cuántico. Las demás cachés y otros proyectos no se tocan. Correrlo cuando acabe el proyecto.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf .venv .mypy_cache .ruff_cache .pytest_cache .hypothesis
for p in qiskit qiskit-aer qiskit-ibm-runtime qiskit-ibm-transpiler qiskit-mitigation qiskit-qasm3-import mthree nistrng runningman \
         symengine rustworkx stevedore pbr ibm-platform-services ibm-cloud-sdk-core websocket-client; do
  uv cache clean "$p" >/dev/null 2>&1 || true
done
echo "entorno de QRECAUDA borrado (venv + caché del SDK cuántico)"
