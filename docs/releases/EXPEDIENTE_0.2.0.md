# Expediente técnico 0.2.0 — QRecauda

Versión del paquete: 0.2.0 (`pyproject.toml`, `qrecauda.__version__`, `CITATION.cff`, `uv.lock`); tag local `v0.2.0`; fecha 2026-10-08.

Añade a 0.1.0 la reserva asíncrona de claves y su medición (E3b), el control negativo del pipeline completo (E5), el dimensionado conservador (opt-in), la demo y el camino a IBM contra un backend falso. **TRL del sistema: 3** (`docs/TRL.md`). El origen cuántico no se afirma (D-002) y no hay corrida en hardware IBM (D-010).

## 1. Alcance del release

| entra | no entra |
|---|---|
| Reserva asíncrona de claves (F6.03): productor en otro proceso, consumidor con registro de consumo | Hardware cuántico real; `FuenteIbm` y el camino a IBM sólo se ensayaron contra un backend falso (`scripts/ibm_run.sh ensayo`) |
| E3b (latencia con la clave de una reserva generada aparte) y E5 (control negativo del pipeline completo), preinscritos y juzgados | E4 (hardware frente a su gemelo en Aer): preinscrita (P.E4), C.E4 bloqueado por «sin credencial IBM», sin veredicto |
| Dimensionado conservador (mínimo de MCV y 90B más la contabilidad de la entropía de la fuente), **opt-in**; por defecto sigue `mcv` | Producción real: sin entropía del sistema operativo mezclada ni cursor persistente (D-011) |
| `qrecauda demo` (tres ramas lado a lado, AES-256-GCM de un peaje y un trayecto de Metro), `qrecauda hardware`, presupuesto de QPU, `scripts/ibm_run.sh` | Origen cuántico; certificación (SP 800-90B completo, FIPS 140-3); gestión de claves |
| Correcciones de R.02 (tres revisores, 7,5 / 6,0 / 5,5) en afirmaciones, documentos y código | Un E3 que cumpla M7: E3 de 0.1.0 sigue **NO CUMPLE** y no se reabre |

## 2. Arquitectura y puntos de entrada

Cuatro macro-capas (datos, lógica, integración, transversales) sobre puertos y adaptadores; detalle en `docs/DISENO.md` (§2·bis, reserva asíncrona F6.03). Siete contratos de imports (`.importlinter`) con tests que muerden.

- CLI: `qrecauda correr <declaración.toml>`, `qrecauda juzgar <ID>`, `qrecauda demo [--rapido] [--dimensionado {mcv,conservador}] [--fuente ibm [--ensayo]]`, `qrecauda hardware`. Las opciones globales (`--formato`, `--config`, `--raiz`) van antes del subcomando.
- Fachada: `qrecauda.api`.
- Script: `scripts/ibm_run.sh ensayo` y `scripts/ibm_run.sh real RUTA_TOKEN` (el token entra por ruta, nunca por valor; modo 0600 exigido).

## 3. Cómo se probó

- `./scripts/ci_local.sh`: ruff, mypy, lint-imports, coherencia del plan, estado del DAG y pytest completo; 883 tests en el commit previo a la versión, todo en verde. DAG de 79 nodos.
- Tests de contrato de capas, de atribución, de TRL (`tests/arquitectura/test_trl.py`), de cifras del pitch y de ⚠️ vigentes (`test_release_sin_dudas.py`), de coherencia de los documentos con el registro (`test_documentos_e3b_e5.py`).
- Adaptador de IBM probado con dobles (`tests/adaptadores/test_ibm_hardware.py`, `test_ibm_runtime.py`) y `ibm_run.sh` con un `uv` falso (`tests/aplicacion/test_ibm_run_sh.py`).
- Cobertura: **no se mide** (el repositorio no la configura); ningún porcentaje se afirma.
- Revisión adversarial R.02 (afirmaciones 7,5 / coherencia 6,0 / código 5,5): hallazgos, disposición y sha de cada corrección en `docs/informes/REVISION_ADVERSARIAL_0.2.0.md`.

## 4. Resultados

Cada cifra sale de `registro/corridas/` y de `registro/veredictos.jsonl`; preinscripciones en `docs/preinscripciones/`, declaraciones en `declaraciones/`. Reproducción: `qrecauda juzgar E3b` y `qrecauda juzgar E5` rejuzgan sobre las corridas registradas; volver a correr (`qrecauda correr declaraciones/E3b.toml`, `.../E5.toml`) exige los cuatro extras, el binario 90B y una máquina sin carga.

| experimento | veredicto | cifra decisiva (corridas nombradas) | denominador |
|---|---|---|---|
| E3b · latencia con reserva generada aparte | **CUMPLE**, con reserva cebada | `C.E3b`: M7 p95 de 0,17 a 0,18 ms (umbral 500 ms); capacidad del productor de 177 a 199 kbit/s; **entregado en régimen 47,8 kbit/s** (1,36 veces el consumo de 35,2 kbit/s); sin esperas; arranque de 6,6 a 6,7 s, informativo | 3 semillas (20261007, 20261008, 20261009) × 12 000 transacciones |
| E5 · control negativo del pipeline completo | **CUMPLE** | `C.E5`: con `mcv`, las claves de las fuentes defectuosas pasan M1–M5 y salen de 1,2 a 2,5 veces más largas que lo que la fuente sostiene (R.00-1 en cadena completa); con el dimensionado conservador la fuente buena conserva de 0,895 a 0,923 de la clave de `mcv` (mínimo 0,75; 883 109 de 956 905 bits en la semilla 20261007) y las defectuosas quedan bajo sus techos K1 y K2 | 3 semillas × 3 fuentes con dependencia × 3 dimensionados, más la fuente buena; las 9 claves defectuosas con `mcv` y las 36 claves entregadas en total pasan M1–M5 |
| Demo | rótulo «simulado: Aer es pseudoaleatorio, sin origen cuántico» | el sesgo de la muestra baja de 0,03 a cuatro diezmilésimas con la mitigación; la clave de las tres ramas pasa la batería: la batería no prueba el origen. Figura: `presentacion/figura_demo.py`, sobre corridas registradas | no es una medición preinscrita; no escribe en `registro/` |
| E3 (0.1.0) | **NO CUMPLE** (sin cambio) | `C.E3`: M7 p95 de 5,5 a 9,4 s frente a 500 ms | no se reabre |

Lecturas que no se deben hacer: E3b **no es comparable** con E3 (E3 genera y cifra; E3b sólo cifra con la reserva ya cebada), y su criterio T2 (M7) era casi trivial por la baja utilización (consumidor ocupado ≈ 1,1 % del tiempo); el riesgo estaba en T1 y T3. E5 es casi un control por construcción: las fuentes defectuosas se eligieron detectables por el 90B y el lado «rechazada» nunca se ejerce.

## 5. Despliegue

Python 3.13 (probado; `requires-python >= 3.11`) en un venv de `uv`, sin contenedores:

```bash
uv sync --frozen --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado
bash spikes/S04_90b/build_nist.sh        # compila ea_non_iid en ~/.cache/qrecauda/nist90b (red y g++)
uv run --no-sync qrecauda demo           # --no-sync: sin él, uv puede quitar los extras
```

Dependencias fijadas en `uv.lock`. El binario de 90B vive en `~/.cache/qrecauda/nist90b` (con respaldo en `/tmp/qrecauda_nist90b` si sólo existe el de 0.1.0) y se verifica que sea del usuario o de root y no escribible por otros. Sin credenciales: un token de IBM, si algún día existe, entra por ruta. `scripts/limpiar_entorno.sh` borra el entorno.

## 6. Límites y deuda conocida

- **Sin hardware real.** Ninguna cifra es de IBM. C.E4 está bloqueado por «sin credencial IBM» y E4 espera a C.E4; la cuota del plan abierto y el consumo de QPU de una corrida real son ⚠️ sin verificar.
- **E3 de 0.1.0 sigue NO CUMPLE**; E3b es otro diseño con preinscripción propia.
- **E3b depende de la reserva cebada**: el arranque (6,6 a 6,7 s) incumpliría M7 para una transacción que llegara durante él. Sin pruebas con λ alto ni arranque en frío.
- **Dimensionado conservador**: opt-in (por defecto `mcv`) y **no se re-midieron E3 ni E3b con él** (⚠️ sin verificar su efecto sobre la latencia). Las claves de E3b se generaron con `mcv`. `min(MCV, 90B)` por sí solo no alcanza en la fuente markov_fuerte.
- **Aer sembrado = claves reproducibles** (D-011): quien conozca la semilla regenera la clave; sirve para validar, no para proteger. La guarda de contexto («validacion» por omisión; «produccion» exige origen cuántico declarado) es mínima. Producción real exige una fuente real de bits más entropía del SO mezclada y un cursor persistente, y **no existen todavía**. C.E3b conserva el paso de semilla 100 que se midió; el resto usa 10**6.
- Supuesto IID: el MCV no ve dependencia temporal; con una fuente correlacionada la longitud segura se sobrestima (`docs/AMENAZAS.md`). El 90B es contraste informativo y no valida la clave.
- M2 por bloques de 4096 no está implementado; se mide la clave entera. El registro de nonces vive en la memoria del proceso.
- Tiempo de `qrecauda demo`: **sin medir** (máquina con carga al intentarlo).
- Historia git: los commits anteriores conservan la identidad de git del dueño del repo; no se reescribe (los sha están en el registro) y no se promete anonimato del repositorio.
- **TRL del sistema: 3.** E5 (control negativo) en 4 como componente; la latencia con reserva y el dimensionado conservador en 3.
