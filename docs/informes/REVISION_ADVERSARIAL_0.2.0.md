# Revisión adversarial R.02 — previa al release 0.2.0 (2026-10-08)

Tres revisores independientes, de solo lectura, atacaron el repositorio en el commit `ff22cf3` (0.2.0 en preparación: E3b, E5 y el camino a hardware). Cada hallazgo se verificó contra el texto, el registro o el código antes de aceptarlo. R.02 es distinta de R.00 (diseño) y de R.01 (release 0.1.0, `docs/informes/REVISION_ADVERSARIAL_0.1.0.md`).

| revisor | alcance | nota |
|---|---|---|
| A | afirmaciones, criterios de éxito, estadística, cifras | 7,5 / 10 |
| C | coherencia de documentos, DAG, instalación, identidad | 6,0 / 10 |
| B | código, criptografía, camino a IBM | 5,5 / 10 |

Las identidades de los hallazgos llevan el prefijo `R2-` para no chocar con las de R.01. La severidad es la que se asignó al clasificarlos aquí, no necesariamente la que puso cada revisor. Los hallazgos de código (revisor B) los corrigió el agente de código y se enlazan por commit en su sección.

Las cifras citadas salen de `registro/corridas/C.E3b_*_e3b_000.json` (campo `reporte.tasa_entregada_ventana_bps`: 47 845 a 47 849 bit/s en las tres semillas, 1,36 veces el consumo de 35 200 bit/s) y de `registro/corridas/C.E5_*_e5_*.json` (las 36 claves entregadas pasan M1 a M5).

## Hallazgos de afirmaciones (revisor A) y su disposición

| id | sev. | hallazgo | disposición |
|---|---|---|---|
| R2-A1 | media | «Una clave que nadie puede recalcular» es falso en simulador: la semilla es pública | **corregido** `f02f078`: GUION y DECK dicen «con una fuente real no se podría recalcular; hoy, en simulador, sí» |
| R2-A2 | media | T2 (M7) de E3b era casi trivial: utilización baja y 4 cambios de clave en 12 000 transacciones; «criterios que podían fallar» sobrestimaba E3b y E5 | **corregido** `f02f078` (PITCH, DECK, GUION) y `fc3c322` (paper: resumen, E3b, discusión, conclusiones): «T2 era casi trivial por la baja utilización; el riesgo estaba en T1 y T3». Cifra propia: con 100 tx/s y latencia media de 0,11 ms (media de las 12 000 latencias de cada artefacto) el consumidor está ocupado ≈ 1,1 % del tiempo; el revisor dijo ≈ 1,5 %, y aquí se usa la calculada |
| R2-A3 | alta | La comparación «5,5 a 9,4 s → 0,17 ms» («más de cuatro órdenes de magnitud») no es equivalente: E3 mide generar y cifrar, E3b sólo cifrar con la reserva ya cebada | **corregido** `f02f078` y `fc3c322`: se quitó «órdenes de magnitud» y cada titular (README, paper, PITCH, DECK, GUION, TRL, ROADMAP, CHANGELOG) lleva el calificador «con la reserva cebada» y la advertencia del arranque de ~6,6 s |
| R2-A4 | alta | «Productor de 177 a 199 kbit/s» es la capacidad; lo entregado en régimen es `tasa_entregada_ventana_bps` ≈ 47,8 kbit/s (1,36 veces el consumo) | **corregido**: «capacidad 177 a 199 kbit/s; entregado 47,8 kbit/s» en README, PITCH, DECK, TRL, paper (resumen, tabla de E3b, texto, conclusiones), ROADMAP, CHANGELOG. En PITCH y DECK la cifra de 47,8 lleva marcador y el test de cifras la cruza con el registro |
| R2-A5 | media | E5 es casi un control por construcción: fuentes defectuosas elegidas detectables por el 90B (D5); el lado «rechazada» nunca se ejerce (las 36 claves pasan M1 a M5); K2 y G2 se fijaron tras un diagnóstico con el mismo generador de defectos | **corregido** `f02f078` y `fc3c322`: texto en paper (resumen, límites de E5, discusión), README (resultado y limitaciones), PITCH, DECK, GUION y TRL |
| R2-A6 | media | TRL de E3b y de E5 sobrestimados (el arranque de 6,6 s incumple M7; sin probar con λ alto ni arranque en frío; E5 mezclaba control negativo con dimensionado conservador) | **corregido** `f02f078`: E3b pasa a TRL 3 (4 sólo con la reserva cebada); E5 se parte en «control negativo (4)» y «dimensionado conservador (3, no integrado, opt-in)». Se ajustó `tests/arquitectura/test_documentos_e3b_e5.py` (la fila de E3b exige `| 3 |`); `test_trl.py` queda verde sin cambios. El TRL del sistema sigue en 3 |
| R2-A7 | baja | El paper dice que el 90B acortaría la clave 20–26 %, y E5 mide 7,5–10,5 % con `min_mcv_90b` | **corregido** `fc3c322`: una frase reconcilia (90B de la muestra cruda de E1 frente al MCV, 20–26 %; 90B del *pool* con la fuente buena de E5, 7,5–10,5 %: 1 − 885 035/956 905 y 1 − 856 258/956 560) |
| R2-A8 | baja | «Cinco experimentos preinscritos» y «preinscritos y juzgados» cuando E4 está preinscrito y sin juzgar | **corregido** `f02f078` y `fc3c322`: «cinco juzgados (E1, E2, E3, E3b y E5); E4, preinscrita, bloqueada por falta de credencial» |

## Hallazgos de coherencia (revisor C) y su disposición

| id | sev. | hallazgo | disposición |
|---|---|---|---|
| R2-C-B1 | alta | `uv sync --group dev` (README, USO) no basta para `qrecauda demo` | **corregido** `fc3c322`: la línea es `uv sync --frozen --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado` y la ejecución, `.venv/bin/qrecauda demo` o `uv run --no-sync qrecauda demo`; corregidos README (instalación, demo, «Reproducir»), USO y HARDWARE. El README añade el bloque de dos comandos de IBM (`scripts/ibm_run.sh ensayo` y `real RUTA_TOKEN`) con la estimación de QPU marcada ⚠️ sin verificar, el requisito de Python (3.13 probado; `requires-python >= 3.11`) y tres líneas sobre qué es un «veredicto». Tiempo de la demo: **no medido** (carga de la máquina de 2,2 al intentar, por encima del límite de 2); el README dice «sin medir en esta máquina». `--dimensionado {mcv,conservador}` e `--instancia` se documentan como «disponible en 0.2.0», con los nombres que la CLI ya expone en el árbol de trabajo |
| R2-C-A1 | media | Historial con la identidad real en commits anteriores; el texto es anónimo | **declarado** `fc3c322`: README («Sobre el historial del repositorio») y `docs/paper/README.md`: la historia no se reescribe (los sha están en el registro) y no se promete anonimato del repositorio |
| R2-C-A2 | baja | `docs/wiki/wiki.json` y `tests/test_dag_estandar.py` contienen rutas del entorno personal | **declarado, sin mover** `fc3c322`: `docs/wiki/README.md` nuevo explica que es *tooling* del autor y que las rutas son locales |
| R2-C-A3 | baja | `CLAUDE.md` está versionado | **declarado** `fc3c322`: `CONTRIBUTING.md` aclara que es el protocolo de trabajo del repositorio |
| R2-C-M1 | media | E5 figuraba «hecho» sin estado de veredicto | **corregido** `340c55e`: línea `juzgado` de E5 (evidencia `f379ec0`, el commit del veredicto) en `registro/nodos.jsonl` y `ESTADO.md` regenerado; `dag.py validar` y `estado --comprobar` verdes |
| R2-C-M2 | media | `RETOMA.md` obsoleto | **corregido** `fc3c322`: 78 nodos, E3b y E5 juzgados, R.02 en curso, hoja REL-0.3.0 y C.E4 bloqueado |
| R2-C-M3 | baja | «Plan de 59 nodos» en el paper frente a 78 nodos en las conclusiones | **corregido** `fc3c322`: el texto y la figura se rotulan «instantánea de 0.1.0» (el plan tiene hoy 78 nodos y 189 aristas); las conclusiones se corrigen a 72 cerrados (67 hechos y 5 juzgados); `paper.pdf` regenerado. La figura no se regeneró a propósito: ya era la instantánea de 0.1.0 (59 nodos) y ahora se declara |
| R2-C-M4 | media | `declaraciones/` descrito como «E1, E2 y E3»; USO y DISENO sin E3b, E5 ni reserva asíncrona (F6.03) | **corregido** `fc3c322`: README (estructura), paper (reproducción y mapa de fuentes), USO (§3) y DISENO (§2·bis, reserva asíncrona F6.03) |
| R2-C-M7 | media | Las enmiendas de E1 y E3 no estaban listadas con su historia completa | **corregido** `fc3c322`: lista en el README y fila nueva en la tabla del paper. Verificado con `git log`: E1, dos enmiendas antes de C.E1 (`1a06602` pasa M4 de la mitigada a informativa; `37b89ca` y `447c907` cambian P1 de «90B > 0,9» a «separación del instrumento», tras una calibración con las semillas declaradas); E3, enmiendas de 2026-10-07 y tres del 2026-10-08 (`15bd897`, `8cc0ec1`, `41cd058`), todas antes de C.E3 (`fdb4386`, 14:46); y `d9c9c6d` (15:08, **posterior** a C.E3) que sólo cambió la redacción de una referencia a E1 en `docs/preinscripciones/E3.md`, sin tocar umbrales ni criterios. El paper decía «todas las enmiendas son anteriores a la corrida»: ya no |
| R2-C-B2 | baja | Tiempos de la demo incoherentes entre README y la ayuda de la CLI | **cerrado** en `2eb42d4` (ver la sección de código). Estado previo, parcial: el README dice «`--rapido`, unos segundos» y «completa, sin medir»; la ayuda de la CLI (código, no se toca aquí) dice «la cadena entera en un minuto» y «segundos en vez de un minuto». Si se mide, alinear ambos; **anotado para el agente de código** |
| R2-C-B3 | baja | El flag global `--formato` va antes del subcomando y no estaba dicho en el README | **corregido** `fc3c322`: README (uso rápido) y USO §2 |
| R2-C-B5 | baja | El sufijo `20261009` de las corridas parece una fecha | **corregido** `fc3c322`: README y USO aclaran que es la semilla |

## Hallazgos de código (revisor B) y su disposición

Los numerados (1 a 10) son los del informe del revisor B; los demás se identifican por su contenido, porque la corrección no cita número. Cada fila resume lo que dice el mensaje del commit y lo que `git show --stat` confirma que tocó.

| commit | qué cubre | archivos principales |
|---|---|---|
| `8b7b568` | Hallazgos 1, 2 y 7, adaptador de IBM y presupuesto de QPU: el gasto cuenta desde el `job_id` y se concilia con `usage()`; el trabajo huérfano se cancela; los errores de programación ya no se disfrazan de red y token; la instancia llega al servicio; aviso por stderr si falta la cuota restante; duración 0.0 aborta en real; límites del backend y puerta x comprobados; errores HTTP sin detalle; tope de QPU finito, positivo y acotado | `adaptadores/ibm_runtime.py`, `dominio/presupuesto_qpu.py` y sus tests |
| `1d9365b` | Hallazgos 2, 4, 5, 9 y 10, CLI, fachada, composición y script: tope de QPU validado en CLI, fachada, composición y `ibm_run.sh` (`qrecauda` sin subcomando usa el tope por omisión); modo «trabajo» por omisión; `--instancia`; `demo --dimensionado {mcv,conservador}` y `--shots`, con 90B por vistas de qubit como opción (lo medido en E5 no cambia); permisos 0600 del token y arrays compatibles con bash < 4.4; lugares de Lima en la demo | `entrada/cli.py`, `api.py`, `composicion.py`, `aplicacion/demo.py`, `aplicacion/dimensionado.py`, `scripts/ibm_run.sh`, `GLOSARIO.md` y tests |
| `02f167e` | Reutilización de claves por semilla: paso de semilla 10**6 (E3b conserva 100), guarda de contexto en la reserva y la transacción, y decisión D-011 | `aplicacion/reserva_asincrona.py`, `aplicacion/transaccion.py`, `docs/decisiones/D-011.md`, `tests/aplicacion/test_claves_reproducibles.py` |
| `7085633` | Muestra del 90B en tmpfs con modo 0700; binario en la caché del usuario con propietario y permisos verificados; CI sin `-march=native` y en `ubuntu-24.04` | `adaptadores/min_entropia.py`, `spikes/S04_90b/build_nist.sh`, `.github/workflows/ci.yml` |
| `ff08097` | Productor en proceso: el hijo vigila al padre, informa cualquier excepción y `detener()` es idempotente | `adaptadores/productor_en_proceso.py` |
| `e4a9ff3` | Extra `demo` y mensajes de extra ausente con la línea exacta de instalación | `pyproject.toml`, `uv.lock`, `composicion.py` |
| `2eb42d4` | Coherencia posterior: binario de 90B en `~/.cache/qrecauda/nist90b` en RETOMA, USO y los spikes; `ibm_run.sh` con `uv run --no-sync`; tiempos de la demo alineados con el README | `RETOMA.md`, `docs/USO.md`, `scripts/ibm_run.sh`, ayuda de la CLI |

R2-C-B2 queda **cerrado** en `2eb42d4` sin inventar tiempos: la ayuda de la CLI y el README dicen ahora lo mismo («tiempo sin medir»). La carga de la máquina era de 3,0 a 3,9 (`/proc/loadavg`, 2026-10-08), por encima del límite de 2 fijado para medir, así que no se midió la demo.

### Lo que sigue abierto

- **Producción real sin entropía del SO ni cursor persistente (D-011).** Una clave de Aer sembrada o de un PRNG es reproducible por construcción: sólo sirve para validar. El contexto «produccion» de los servicios de transacción rechaza una clave sin origen cuántico declarado, pero la guarda es mínima (no impide pasar `contexto="produccion"` con hardware y semilla fija). Falta, y **no existe todavía**, una fuente real de bits más entropía del sistema operativo mezclada, y un cursor persistente que impida reutilizar una clave tras un reinicio. Mientras tanto no se afirma «clave de producción».
- **Cuota del plan abierto de IBM.** La cuota de QPU del plan abierto y el consumo real de una corrida E4 son ⚠️ sin verificar: no hay credencial (D-010) y el presupuesto de QPU sólo se ensayó contra un backend falso.
- **Historia git no anónima, por decisión cerrada.** Los commits anteriores conservan la identidad de git del dueño del repo; no se reescribe porque los sha están en el registro (R2-C-A1).
- **No se re-midieron E3 ni E3b** con el dimensionado conservador ni tras los cambios de código de R.02c: sus veredictos siguen siendo los de las corridas registradas.

## Observaciones al agente de código

Resueltas: `ibm_run.sh` usa `uv run --no-sync` y la ayuda de la demo ya no promete «un minuto» (`2eb42d4`). Los dos tests que fallaban por trabajo en curso (trinquetes y glosario) pasan desde `1d9365b` y `8b7b568`; la verificación final es `scripts/ci_local.sh`.

## Qué no se cerró

- Lo listado en «Lo que sigue abierto» arriba: producción real, cuota del plan abierto, historia git y re-medición con el dimensionado conservador.
