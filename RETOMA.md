# RETOMA — QRECAUDA (una página)

1. Lee `ESTADO.md` y corre `python3 plan/dag.py siguiente`: el estado vive en `registro/nodos.jsonl`, no aquí.
2. Objetivo y reglas: `docs/FUNDAMENTO.md` (§Objetivo, §Discrepancias declaradas). Arquitectura: `docs/DISENO.md`. Amenazas: `docs/AMENAZAS.md`.
3. Entorno: `uv sync --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado` (venv desechable;
   `scripts/limpiar_entorno.sh` lo borra al acabar). `uv run` sin `--no-sync` puede quitar los extras: usa `.venv/bin/python`.
4. Antes de empujar: `./scripts/ci_local.sh`. Hooks: `scripts/instalar_hooks.sh`. Commits por rutas concretas, sin atribución a modelos.
5. Cerrar un nodo = commit que toque su entrega + línea nueva en `registro/nodos.jsonl` + `python3 plan/dag.py estado`.
6. El binario de 90B vive en `/tmp/qrecauda_nist90b`; si falta: `bash spikes/S04_90b/build_nist.sh`.
7. Estado a 2026-10-08: 59 nodos (54 hechos, 3 juzgados, 2 pendientes: R.01 lista y REL-0.1.0). Sin hardware IBM: constancia en D-010. Remoto público `jramirezgen/qrecauda` con espejo `bare` (`scripts/remotos.md`); la historia lleva la identidad de git del dueño del repo y el informe es anónimo. Cifras vigentes: `python3 plan/dag.py estado`.
