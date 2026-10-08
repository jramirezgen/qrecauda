# CHANGELOG

## [Sin publicar]
- `qrecauda demo`: tres ramas lado a lado, AES-256-GCM de un peaje y un trayecto de Metro y rótulo de origen; `--rapido`, `--fuente ibm`, `--ensayo`.
- `qrecauda hardware` y camino a IBM: twirling con PUBs, registro por trabajo, presupuesto de QPU (`--max-segundos-qpu`, código 11), ensayo contra un backend falso, `scripts/ibm_run.sh` y `docs/HARDWARE.md`.
- Preinscripción P.E4 (hardware frente a su gemelo en Aer). C.E4 y E4 siguen abiertos: sin credencial IBM no hay ninguna cifra de hardware.
- Cuaderno `notebooks/qrecauda_vivo.ipynb` (parámetro `FUENTE`).

## [0.1.0] - 2026-10-08
Primera versión: pipeline QRNG reproducible en simulador con ruido (TRL del sistema 3). Detalle, límites y reproducción en `docs/releases/EXPEDIENTE_0.1.0.md`; revisión en `docs/informes/REVISION_ADVERSARIAL_0.1.0.md`.
- Corregido en la revisión R.01: reutilización de (clave, nonce) AES-GCM, carrera en la reserva de claves, aprobación de clave con métricas ausentes, `Bits` sin imprimir la clave, hook de atribución más estricto.
- Andamiaje: capas, contratos de imports, DAG de 59 nodos, siete contratos de imports, núcleo puro (Bits, extractores, métricas), bala trazadora con PRNG, almacén y informe versionados.
- Experimentos: E1 CUMPLE, E2 CUMPLE (ZNE y PEC sin efecto sobre la lectura), E3 NO CUMPLE por M7 (p95 de 5,5 a 9,4 s frente a 500 ms); M6 cumple.
- Decisiones D-009 (twirling propio; sustituye en parte a D-003) y D-010 (sin acceso a hardware IBM).
- TRL del sistema: 3 (`docs/TRL.md`). Sin origen cuántico afirmado (D-002).
