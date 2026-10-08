# TRL por componente, derivado de la evidencia (T.TRL)

> Rúbrica: `deeptech-validation-toolkit/references/rubrica-trl.md`. TRL 4 pide repetibilidad n ≥ 3, protocolo
> preinscrito (regla 5 de FUNDAMENTO) y que un tercero pueda auditar el protocolo y las corridas.
> Una fila sólo sube de TRL con una corrida nombrada en `registro/corridas/`; lo no demostrado no sube.
> `tests/arquitectura/test_trl.py` cruza esta tabla con `plan/plan.json`, `registro/corridas/` y `registro/veredictos.jsonl`.
> Discrepancia 7 de FUNDAMENTO: el rótulo «TRL 4» del manifiesto no se hereda; se deriva de esta tabla.

## Matriz

| componente | nodos | corridas | TRL sin hardware | TRL con hardware | evidencia y límite |
|---|---|---|---|---|---|
| Dominio (Peres, Toeplitz + LHL) | `F1.02`, `F1.03`, `P.E1` | `E1a`, `C.E1` | 4 | n/m | Tres semillas preinscritas (P.E1); el control PRNG pasa M1–M5 (E1 CUMPLE). Es aritmética pura: no depende de la fuente. |
| Fuente simulada con ruido (Aer) | `F3.01`, `F3.02`, `S.03`, `P.E1` | `E1b` | 3 | n/m | El muestreo de Aer usa un PRNG (S.03, D-002). El modelo de ruido es propio y no se contrastó con un backend real: que reproduzca el ruido físico es un límite declarado, sin prueba. |
| Mitigación de lectura: twirling propio | `F4.01`, `S.02`, `P.E2` | `E1c`, `C.E2` | 4 | n/m | E2 CUMPLE en tres semillas y tres niveles de ruido, sobre ruido modelado: el twirling baja el sesgo de lectura entre 11 y 32 veces. Que el efecto se mantenga sobre ruido real es un límite declarado, sin prueba. |
| Mitigación: ZNE y PEC | `F4.02`, `S.02`, `P.E2` | `C.E2` | 3 | n/m | Sin efecto sobre el sesgo de lectura (hasta +6,6 % en ⟨Z⟩, C.E2): no suben de TRL, sólo se muestran inocuas. Actúan sobre valores esperados, no sobre el bitstream (D-009). Que sirvan sobre ruido real es un límite declarado, sin prueba (D-003). |
| Validación (NIST SP 800-22 y 90B) | `F5.01`, `F5.02`, `S.04`, `P.E1` | `E1d`, `C.E1` | 4 | n/m | Con control positivo (fuentes defectuosas rechazadas) y control negativo (PRNG pasa). Valida estadística, no origen (D-002; el control negativo es D-007). |
| Cifrado AES-GCM | `F6.01`, `F6.02`, `P.E3` | `C.E3` | 3 | n/m | El ciclo de cifrado con reserva de claves (30–63 mil tx/s) es medición de perfil B: no decide el veredicto preinscrito, así que no basta para TRL 4. La reserva con productor en paralelo se midió después como E3b (fila de latencia); esta fila sigue citando sólo E3. |
| Pipeline integrado (M1–M5 y M7) | `F2.03`, `F7.06`, `P.E1`, `P.E3` | `C.E1`, `C.E3` | 3 | n/m | E1 CUMPLE con tres semillas, pero el pipeline integrado falla M7 en E3, y E1 se apoya en M4 y M5 informativas de la mitigada. Hallazgo R.00-1: la clave sin mitigar también pasa M1–M5, por lo que M1–M5 no demuestran el valor de la mitigación ni el origen. Sólo el postprocesamiento (fila de dominio, extracción y validación) sostiene TRL 4. |
| Tasa sostenida M6 | `P.E3`, `C.E3` | `C.E3` | 3 | n/m | M6 = 180–195 kbit/s cumple su umbral en las tres semillas, a un hilo; pero el veredicto de C.E3 es único y NO CUMPLE (M7), y no se separa a posteriori: no sube a 4. |
| Latencia de transacción del pipeline completo (M7), diseño de 0.1.0: la clave se genera dentro de la transacción | `P.E3`, `C.E3`, `E3` | `C.E3` | 3 | n/m | E3 NO CUMPLE por M7: p95 5,5–9,4 s frente a 500 ms, en las tres semillas. Medido y repetido, pero el criterio de éxito preinscrito falla: no está validada. Este diseño no se borra ni se reabre: la fila de abajo es otro diseño. |
| Latencia de transacción con la clave de una reserva generada aparte (M7, E3b) | `F6.03`, `P.E3b`, `C.E3b`, `E3b` | `C.E3b` | 4 | n/m | E3b CUMPLE en las tres semillas con protocolo preinscrito (n = 3): p95 de 0,17 a 0,18 ms frente a 500 ms (M7), productor de 177 a 199 kbit/s contra un umbral de 10 kbit/s y un consumo declarado de 35,2 kbit/s (T1), 0 esperas en 12 000 transacciones por semilla (T3). TRL 4 del componente según la rúbrica (repetibilidad n ≥ 3, protocolo preinscrito, auditable), sobre simulador. Límites: el arranque (6,6 a 6,7 s hasta la primera clave) se informa aparte y no decide; la demanda de 100 tx/s es declarada por el equipo; las claves se generan con el dimensionado `mcv` de 0.1.0 y no se re-midió con el conservador (⚠️ sin verificar su efecto sobre la latencia); sin cola ni red de IBM. No sube al sistema. |
| Dimensionado de la clave y control negativo del pipeline completo (E5) | `F5.05`, `P.E5`, `C.E5`, `E5` | `C.E5` | 4 | n/m | E5 CUMPLE en tres semillas, tres fuentes con dependencia entre bits y la fuente buena. Con el dimensionado de 0.1.0 (`mcv`) las nueve claves defectuosas pasan M1–M5 y superan el techo teórico de la fuente (hallazgo R.00-1 medido en cadena completa); el dimensionado conservador las acorta bajo ese techo y la buena conserva entre el 89,5 y el 92,3 % de su clave (veredicto E5). Límites: el conservador es opt-in (por defecto, `mcv`); cubre tres defectos de dependencia con respuesta analítica, no uno adversarial; sobre simulador. |
| Fuente cuántica real (hardware IBM) | `F3.04`, `F3.06` | `HW` | 3 | n/m | Sin hardware (D-010, constancia en `HW.json`, `job_id` nulo). Sólo se sostiene lo que da el simulador. El origen cuántico NO se afirma (D-002). Sólo una corrida real con `job_id` y n ≥ 3 permitiría discutir TRL 4; hasta entonces es un límite declarado. |

`n/m` = no medido: no existe corrida con hardware, así que ninguna fila tiene un TRL «con hardware».

## TRL del sistema

**TRL del sistema: 3** (la fila más baja; no el promedio ni el más alto).

Siete filas están en TRL 3: fuente simulada, ZNE y PEC, cifrado AES-GCM, pipeline integrado, tasa M6, latencia M7 del diseño de 0.1.0 y fuente real.
Lo fija, con peso propio, la fuente cuántica real (sin hardware). La latencia con reserva (E3b) y el dimensionado con control
negativo (E5) están en TRL 4 como componentes, igual que el postprocesamiento (dominio, twirling propio y validación), todo en simulador;
el rótulo «TRL 4» del manifiesto no se sostiene para el sistema completo.

## Qué lo subiría

- Latencia: E3b cerró M7 en simulador (la fila de arriba). Falta medirla con la cola y la red de IBM dentro, y re-medir con el dimensionado conservador de E5 si pasa a ser el predeterminado.
- Fuente real: `qrecauda correr` o `qrecauda hardware` (`scripts/ibm_run.sh`, `docs/HARDWARE.md`) con la fuente `ibm` y un token por ruta, que produzca `HW.json` con `job_id` (D-010, «Cómo se revertiría»). La preinscripción P.E4 está escrita; C.E4 está bloqueado por falta de credencial y no existe ningún resultado en hardware real.
