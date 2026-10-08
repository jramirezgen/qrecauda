# RETOMA — QRECAUDA (una página)

1. Lee `ESTADO.md` y corre `python3 plan/dag.py siguiente`: el estado vive en `registro/nodos.jsonl`, no aquí.
2. Objetivo y reglas: `docs/FUNDAMENTO.md` (§Objetivo, §Discrepancias declaradas). Arquitectura: `docs/DISENO.md`. Amenazas: `docs/AMENAZAS.md`.
3. Entorno: `uv sync --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado` (venv desechable;
   `scripts/limpiar_entorno.sh` lo borra al acabar). `uv run` sin `--no-sync` puede quitar los extras: usa `.venv/bin/python`.
4. Antes de empujar: `./scripts/ci_local.sh`. Hooks: `scripts/instalar_hooks.sh`. Commits por rutas concretas, sin atribución a modelos.
5. Cerrar un nodo = commit que toque su entrega + línea nueva en `registro/nodos.jsonl` + `python3 plan/dag.py estado`.
6. El binario de 90B vive en `/tmp/qrecauda_nist90b`; si falta: `bash spikes/S04_90b/build_nist.sh`.
7. Estado a 2026-10-08: 78 nodos (`ESTADO.md` da el conteo vivo); 0.1.0 publicada. En curso 0.2.0: E3b (latencia con la clave de una reserva generada aparte) y E5 (control negativo del pipeline completo) están juzgados (CUMPLE, con matices declarados: E3b no es comparable con E3 y su T2 era casi trivial; E5 es casi un control por construcción). **R.02 (revisión adversarial) está en curso**: sus hallazgos y disposiciones viven en `docs/informes/REVISION_ADVERSARIAL_0.2.0.md`; tras ella, REL-0.2.0. Sin hardware IBM: constancia en D-010. Remoto público `jramirezgen/qrecauda` con espejo `bare` (`scripts/remotos.md`); la historia conserva la identidad de git del dueño del repo en commits anteriores (no se reescribe: los sha están en el registro) y el texto del informe es anónimo. Cifras vigentes: `python3 plan/dag.py estado`.
8. Hardware de IBM (0.3.0, sin publicar): camino listo y ensayado contra un backend falso (`scripts/ibm_run.sh ensayo`); P.E4 preinscrita y commiteada, NO se toca. C.E4 está bloqueado por «sin credencial IBM» y E4 espera a C.E4: sólo el dueño con su token (por ruta) corre `scripts/ibm_run.sh real RUTA_TOKEN` y luego `qrecauda juzgar E4`. Paso a paso y lo no verificado: `docs/HARDWARE.md`. La hoja del DAG es REL-0.3.0 (0.3.0, sin publicar).
