# CHANGELOG

## [Sin publicar]

### 0.2.0 en preparación (sin fecha de release)
- E3b, CUMPLE en tres semillas (`registro/veredictos.jsonl`, corridas `C.E3b`): la latencia de transacción con la clave de una reserva generada aparte por un proceso productor da p95 de 0,17 a 0,18 ms con la reserva cebada (umbral 500 ms), con capacidad del productor de 177 a 199 kbit/s (entregado en régimen, 47,8 kbit/s) y sin esperas; el arranque, de 6,6 a 6,7 s, se informa aparte y una transacción que llegue durante él incumpliría M7. No es comparable con E3 (generar y cifrar frente a sólo cifrar) y su T2 era casi trivial por la baja utilización. Es otro diseño con preinscripción propia: E3 (0.1.0) sigue en NO CUMPLE y no se reabre. Limitación: las claves se generan con el dimensionado `mcv` de 0.1.0. Sólo simulador, sin cola ni red de IBM.
- E5, CUMPLE (corrida `C.E5`): control negativo del pipeline completo con fuentes que dependen de sus bits. Mide el hallazgo R.00-1 en cadena completa (con `mcv`, las claves defectuosas pasan M1 a M5 y salen de 1,2 a 2,5 veces más largas que lo que la fuente sostiene).
- Dimensionado conservador (mínimo de MCV y 90B más la contabilidad de la entropía de la fuente), opt-in: por defecto sigue `mcv`. `min(MCV, 90B)` por sí solo no alcanza en la fuente markov_fuerte. No se re-midieron E3 ni E3b con él (⚠️ sin verificar su efecto sobre la latencia).
- Reserva asíncrona de claves (F6.03): productor en otro proceso y consumidor con registro de consumo.
- Documentación: pitch, deck, guion, README, TRL (E5, control negativo, en TRL 4 como componente; la latencia con reserva y el dimensionado conservador en 3; el sistema sigue en TRL 3), hoja de ruta e informe técnico, al día con E3b y E5. El test de cifras cruza ahora también `docs/pitch/DECK.md`.

### Camino a hardware (para 0.3.0; sin ningún resultado en hardware real)
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
