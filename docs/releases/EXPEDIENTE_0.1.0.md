# Expediente técnico 0.1.0 — QRecauda

Pipeline QRNG reproducible en simulador con ruido, para la recaudación peruana. **TRL del sistema: 3** (`docs/TRL.md`). El origen cuántico no se afirma (D-002) y no hay corrida en hardware IBM (D-010).

## 1. Alcance del release

| entra | no entra |
|---|---|
| Cadena fuente → mitigación → Peres → Toeplitz (LHL) → validación → clave → AES-256-GCM | Hardware cuántico real; el adaptador `FuenteIbm` sólo se probó con dobles |
| Twirling de lectura propio; ZNE y PEC medidos (sin efecto sobre la lectura) | Origen cuántico; certificación (SP 800-90B completo, FIPS 140-3); gestión de claves |
| M1–M7, tres experimentos preinscritos E1, E2, E3 con 3 semillas cada uno | Una latencia de transacción que cumpla M7 (E3 NO CUMPLE) |

## 2. Arquitectura y puntos de entrada

Cuatro macro-capas (datos, lógica, integración, transversales) sobre puertos y adaptadores; detalle en `docs/DISENO.md`. Siete contratos de imports (`.importlinter`) con tests que muerden.
Entradas: CLI `qrecauda correr <declaración.toml>` y `qrecauda juzgar <ID>`; fachada `qrecauda.api`.

## 3. Cómo se probó

- `./scripts/ci_local.sh`: ruff, mypy, lint-imports, coherencia del plan, estado del DAG y pytest completo (todo en verde al cerrar el release).
- Tests de contrato de capas, de atribución, de TRL (`tests/arquitectura/test_trl.py`), de cifras del pitch y de ⚠️ vigentes (`test_release_sin_dudas.py`).
- Revisión adversarial R.01: tres revisores independientes (6,0 / 6,0 / 5,5) y un bloqueante corregido (`docs/informes/REVISION_ADVERSARIAL_0.1.0.md`).

## 4. Validación contra línea base

Cada cifra sale de `registro/corridas/` y de `registro/veredictos.jsonl`; la preinscripción de cada experimento está en `docs/preinscripciones/` y las declaraciones en `declaraciones/`.

| experimento | veredicto | cifra decisiva (corridas nombradas) |
|---|---|---|
| E1 · pipeline con fuente simulada | CUMPLE, condicionado a que M4 y M5 de la mitigada sean informativas | `C.E1`; la clave sin mitigar también pasa M1–M5 (R.00-1) |
| E2 · mitigación | CUMPLE | `C.E2`: residuo 0,00036–0,0013 en los niveles sintéticos; ZNE y PEC sin efecto |
| E3 · tasa y latencia | **NO CUMPLE** | `C.E3`: M6 180–195 kbit/s (cumple 10 kbit/s); M7 p95 5,5–9,4 s frente a 500 ms |

Reproducción: `uv sync --frozen --group dev --extra informe` y `.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/qrecauda.ipynb` regeneran las tablas; `qrecauda juzgar E1|E2|E3` rejuzga sobre las corridas registradas.

## 5. Despliegue

Python 3.13 en un venv de `uv` (sin contenedores): `uv sync --frozen --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado`. Dependencias fijadas en `uv.lock`. Sin credenciales: un token de IBM, si algún día existe, entra por ruta. `scripts/limpiar_entorno.sh` borra el entorno.

## 6. Límites y deuda conocida

- Supuesto IID: la clave se dimensiona con MCV, que no ve dependencia temporal; con una fuente correlacionada la longitud segura se sobrestima (AMENAZAS, «Limitaciones declaradas»).
- M2 por bloques de 4096 no está implementado; se mide la clave entera. Desviación declarada, sin efecto sobre el veredicto.
- El 90B es contraste informativo y no valida la clave.
- El registro de nonces vive en la memoria del proceso; no protege entre procesos.
- La latencia por transacción exige un diseño con reserva de claves asíncrona y una preinscripción nueva (`docs/ROADMAP.md`).
