# Cómo contribuir

Gracias por mirar el proyecto. Antes de abrir un cambio, lee [`docs/FUNDAMENTO.md`](docs/FUNDAMENTO.md) (objetivo, alcance y reglas) y [`docs/DISENO.md`](docs/DISENO.md) (capas). Para instalar y ejecutar, ver [`docs/USO.md`](docs/USO.md). `CLAUDE.md`, en la raíz, está versionado a propósito: es el protocolo de trabajo del repositorio (qué leer primero, dónde vive el estado, reglas de cifras, secretos y commits) para quien trabaje en él con un asistente; no es una configuración personal.

## Entorno

```bash
uv sync --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado --extra informe
scripts/instalar_hooks.sh          # una vez por clon
bash spikes/S04_90b/build_nist.sh  # estimador 90B, para los tests que lo usan
```

Los hooks son `commit-msg` (rechaza la atribución a un modelo) y `pre-push` (corre la CI local).

## Flujo de trabajo

1. Abre una incidencia con la plantilla que corresponda, o parte de un nodo del plan (`python3 plan/dag.py siguiente`).
2. Crea una rama desde `main`.
3. Escribe el test antes que el código cuando cambies comportamiento. Un bug se reproduce con un test que falla.
4. Corre `./scripts/ci_local.sh` antes de empujar. Ejecuta ruff, `ruff format --check`, mypy estricto, `lint-imports`, las comprobaciones del DAG y pytest. La CI de GitHub repite los mismos pasos.
5. Abre el pull request con la plantilla y enlaza la incidencia o el nodo.

## Reglas del repo

**Capas.** El dominio es puro: sin I/O, reloj, aleatoriedad global ni SDK. Los SDK pesados solo se importan dentro de `adaptadores/`. Siete contratos de `import-linter` (`.importlinter`) lo hacen cumplir. Un cambio que los rompa no se acepta: se rediseña.

**El plan es un DAG.** El plan se genera con `plan/construir_dag.py` y se guarda en `plan/plan.json`. No edites el JSON. El estado vive en `registro/nodos.jsonl` (solo se añade) y `ESTADO.md` se regenera con `python3 plan/dag.py estado`. Un nodo se cierra con un commit que toque su entrega y una línea nueva en el registro.

**Preinscribir antes de correr.** Umbral y criterio de cada experimento se escriben en `docs/preinscripciones/` y `declaraciones/` antes de la primera corrida. Un veredicto que no cumple queda en el registro. No se reabre ni se reinterpreta después de ver el resultado. Un diseño distinto es un experimento nuevo con su propia preinscripción.

**Una cifra sale de una corrida nombrada.** Ninguna cifra en un documento viene de memoria. Cita la corrida o el veredicto de `registro/`.

**Lo no verificado se marca.** Usa `⚠️ sin verificar` y trátalo como hipótesis. No lo encadenes en conclusiones.

**Secretos.** Entran por ruta (`ibm_token_ruta`, `QRECAUDA_IBM_TOKEN_FILE`), nunca por valor. No los imprimas ni los trunques, y no los incluyas en ningún commit. Un trinquete de la suite detecta credenciales en el código.

**Sin rutas absolutas ni datos personales** en archivos versionados.

## Commits

- Mensajes en español, en imperativo o infinitivo corto, con el nodo al inicio si existe: `F5.02: estimador 90B tras un puerto`.
- Haz el commit por rutas, para no arrastrar cambios ajenos: `git commit -m "..." -- ruta1 ruta2`. Los archivos nuevos se añaden antes con `git add ruta`.
- Sin atribución a modelos de lenguaje en commits, pull requests ni releases: ni trailers de coautoría ni líneas de «generado con». El hook `commit-msg` lo rechaza y un test recorre la historia.

## Estilo

- Python 3.13, líneas de hasta 140 caracteres, `ruff` con `E, F, W, I, B, UP, SIM`, `mypy --strict` sobre `src`.
- Los nombres del dominio están en español y siguen `docs/GLOSARIO.md`. Un test lo comprueba.
- La prosa de la documentación es directa: sin muletillas ni adjetivos de relleno, con cifras y fuente.

## Dónde preguntar

En las incidencias del repositorio. Los problemas de seguridad siguen [`SECURITY.md`](SECURITY.md). Al participar aceptas el [código de conducta](CODE_OF_CONDUCT.md).
