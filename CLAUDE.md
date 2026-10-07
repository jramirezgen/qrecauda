# QRECAUDA — instrucciones del repo

**Empieza por `RETOMA.md`.** `docs/FUNDAMENTO.md` manda sobre objetivo, alcance y reglas; sólo cambia por enmienda.

- El estado vive en `registro/` y `ESTADO.md` (generado). Nunca en el chat ni en la memoria.
- El plan es `plan/construir_dag.py` → `plan/plan.json`. No se edita el JSON; no se cierra un nodo sin un commit que toque su entrega.
- Arquitectura: `docs/DISENO.md`. `uv run lint-imports` y `./scripts/ci_local.sh` ANTES de empujar.
- Una cifra sale de una corrida nombrada. Un secreto entra por ruta, nunca por valor ni impreso.
- Nunca se atribuye nada a un modelo en commits, PR o releases (hook `scripts/hooks/commit-msg`; `scripts/instalar_hooks.sh`).
- Lo marcado ⚠️ sin verificar es hipótesis, no premisa (FUNDAMENTO, «Discrepancias declaradas»).
- Wiki: el tablero de incidencias es la puerta; no se toca un canvas sin pasar por él (skill `wiki-de-proyecto`).
- Entorno desechable: todo el SDK vive en `.venv` (uv), nunca global ni en contenedor (decisión del usuario 2026-10-07); `scripts/limpiar_entorno.sh` lo borra al acabar.
- Se responde siempre en español.
