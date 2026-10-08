# Revisión adversarial R.01 — previa al release 0.1.0 (2026-10-08)

Tres revisores independientes, de solo lectura y sin acceso a la conversación, atacaron el commit `f1e8c3b` desde ángulos distintos.
Cada hallazgo se verificó contra el texto o el código antes de aceptarlo. Esta revisión es distinta de R.00 (diseño, 2026-10-07):
R.01 juzga las claims con las eurekas y las mediciones ya hechas.

| revisor | alcance | nota |
|---|---|---|
| A | afirmaciones, criterios de éxito, estadística, cifras | 6,0 / 10 |
| B | código, criptografía, contratos de imports | 6,0 / 10 |
| C | coherencia de documentos y DAG, identidad, atribución | 5,5 / 10 |

El veredicto de E3 (NO CUMPLE por M7) resistió la revisión: el revisor A recalculó M6, M7, medianas por etapa, rechazos y los tres veredictos con
su propio código y coinciden con el registro. Los CUMPLE de E1 y E2 resultaron más débiles de lo que se presentaba, y el paper, el pitch y el TRL se corrigieron.

## Hallazgos y disposición

| id | sev. | hallazgo | disposición |
|---|---|---|---|
| B-1 | bloqueante | La pareja (clave, nonce) de AES-GCM se repetía al crear dos servicios sobre el mismo `Resultado`; E3 lo hacía con TX_A y el perfil B | **corregido** `8254470`: registro de consumo por sha256 de la clave, con candado; U4 cuenta TX_A |
| A-1 (B) | alta | Carrera en `ReservaDeClave.siguiente` y `CifradorAesGcm.cifrar` | **corregido** `8254470`, con test de 8 hilos |
| A-2 (B) | alta | `calidad_de_clave_aprobada` aprobaba con métricas ausentes y `ValidadorNist` no emitía M1 | **corregido** `f64b252` |
| A-3 (B) / A1 (A) | alta | El dimensionado usa MCV (ciego a la dependencia) y supone IID; una fuente Markov de min-entropía 0,322 da una clave ≈3 veces más larga de lo que sostiene | **limitación declarada** (AMENAZAS, paper, ROADMAP): mejora futura `min(MCV, 90B)`; cambiarlo mueve las claves y exigiría repetir E1–E3 |
| A2 (A) | alta | M2 preinscrito por bloques de 4096 no está implementado; se mide la clave entera (0,994 frente a ≈0,943) | **desviación declarada** en el paper; el veredicto no cambia; la preinscripción no se toca tras correr |
| A3 (A) | alta | El CUMPLE de E1 y E2 sale en parte de identidades del twirling | **corregido en el texto**: el paper, el pitch y el TRL lo dicen |
| B1 (A) | alta | M4 y M5 de la mitigada pasaron a informativas; sin la enmienda E1 sería CUMPLE PARCIAL | **declarado** en resumen, paper, pitch y TRL |
| A4 (A) | media | P1 se calibró con las mismas semillas: prueba de regresión, no control con poder | **declarado** |
| B2 (A), M-6 (B) | media | Las enmiendas de E3 se hicieron el día de la corrida y se descartó un intento sin cifras | **declarado** como grado de libertad; M7 está 8,9–19 veces sobre el umbral, el veredicto no depende |
| C1, C2 (A) | media | ~30 p-valores a α = 0,01 sin corrección; el IC de E2 ignora la varianza del twirling | **declarado** como límite estadístico |
| D1, D2 (A), A2 (C) | media | Paper obsoleto frente al registro; "≈14 %" de acortamiento mal calculado | **corregido** `70d7eb7`, conteos regenerados |
| B2 (C) | bloqueante | Titular "Entropía cuántica certificada" en README, `pyproject.toml`, `__init__.py` | **corregido** `d9c9c6d` |
| B1 (C) | bloqueante | Identidad del autor en la historia (nombre del dueño de la cuenta pública) y `paper/README.md:22` | **aclarado**: el informe es anónimo (alias); la historia lleva la identidad de git del dueño del repo, por decisión suya; no se reescribe |
| A1, A3, A4 (C) | alta | AMENAZAS dice que el 90B decide; FUNDAMENTO y TRL con estados y filas obsoletos | **corregido** `d9c9c6d` |
| A6 (C) | alta | ⚠️ vigentes que el test del release debe vetar | **corregido** y vigilado por `test_release_sin_dudas.py` |
| M1–M5 (C) | media | Citas D-007/D-002, D-003 sin marcar sustituida, conteo de contratos, RETOMA y CHANGELOG | **corregido** `d9c9c6d` y plan |
| M-1 (B) | media | Contratos C2/C4/C5 sin test que muerda | **corregido** `a893d9a` |
| M-2 (B) | media | El hook `commit-msg` era un regex corto | **corregido** `ed552e9` |
| M-3 (B) | media | Filtrar claves por pruebas estadísticas (≈4 % descartadas) | **documentado** como práctica desaconsejada |
| M-4 (B) | media | `Bits` se imprimía entero | **corregido** `f64b252` |
| M-5, M-7 (B) | media | M5 distinta según validador; T4 no cuenta la CPU del hijo 90B | **abierto**, anotado en ROADMAP |
| M7, M8 (C) | media | El código puede rotular "cuántico" con un `job_id`; E3 medido con un proceso ajeno | **abierto / declarado** (enmienda de carga, núcleo fijado, T4 ≤ 1,10) |
| BAJA | baja | Rutas absolutas de herramientas, replay, `FuenteDeSemilla` muerta, `ruff` fuera de `src` | **abierto**, sin efecto sobre las claims |

## Qué cambió tras la corrida de E3

Los arreglos B-1, A-2 y M-4 tocan el código de cifrado y de validación posterior a la medición de C.E3 (commit `41cd058`). No alteran la cadena hasta Toeplitz ni
los tiempos de M6 y M7, que dependen de ese tramo y de la validación; el cifrado pesa 0,19 ms de una repetición de varios segundos. El veredicto de E3 se conserva sin repetir la corrida; la
diferencia queda declarada aquí y en el paper.

## Lo que queda abierto a propósito

Dimensionar con `min(MCV, 90B)`, M2 por bloques y un control negativo del pipeline completo exigen repetir E1 y E3 con preinscripción nueva: son el trabajo de `docs/ROADMAP.md`, no del release 0.1.0.
