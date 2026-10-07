# Revisión adversarial R.00 — diseño y DAG de QRECAUDA (2026-10-07)

Un agente independiente, de solo lectura, sin acceso a la conversación, atacó los artefactos de diseño (A contaminación,
B contradicciones, C capas, D dominio, E mecanismos en prosa, F camino crítico, G ejecutabilidad). **Notas del revisor:**
arquitectura de capas 6/10, DAG hacia TRL 4 3,5/10, ejecutabilidad de tirón 3/10. Cada hallazgo se verificó contra el texto
o el código antes de aceptarlo; lo aceptado entró al tablero (INC-003…INC-007) antes que al DAG.

## Verificados con una ejecución propia

| # | hallazgo | comprobación | veredicto |
|---|---|---|---|
| 1 | M1–M5 se miden sobre la salida de Toeplitz: E1 pasa por construcción | `pipeline.py` evalúa `clave`; con p(1) = 0,9 el revisor obtuvo APROBADO | aceptado → `F2.03`, `P.E1`, `C.E1b/c` |
| 2 | MCV es ciego a la dependencia | Markov con permanencia 0,8: MCV = 0,990 frente a −log2(0,8) = 0,322 | aceptado → `S.04`, `F5.02`, `C.E1d` |
| 6 | el hardware opcional es ancestro de la hoja | ancestros de `REL-0.1.0` incluían `F3.04`, `F0.09`, `F7.05` | aceptado → `F3.06`, `REL-0.1.0` |
| 9 | `C.E3` no desciende de Aer, mitigación ni NIST | ancestros de `C.E3` sin `F3.01`, `F4.01`, `F5.01` | aceptado → `C.E3`, `F7.06` |
| 10 | O1–O7 sin definición | el mensaje fundacional no numera nada | aceptado → tabla en FUNDAMENTO |
| 11 | C2 contradice el diseño de `aer`/`ruido`/`transpilacion` | `.importlinter` y `adaptadores/__init__.py` | aceptado y **corregido**: `aer` es paquete |
| 13 | reglas de imports de DISENO que el código viola | `composicion` importa `transversal` | aceptado y corregido (prosa, C3, trinquete `np.random`) |
| 18 | M2 con 256 bits no puede pasar | cota MCV al 99 %: 0,785 con 256 bits, 0,90 con 1288; monobit con N = 800 000 exige sesgo < 0,0014 | aceptado → `P.E0` |

## Aceptados sin ejecución propia (se leyeron en el texto)

3, 4, 5, 7, 8, 12, 14, 15, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28 → nodos `P.E0`, `S.04`, `F2.07`, `F3.05`,
`F3.06`, `F7.06`, `T.TRL`, `C.E1d`, `R.00` y enmiendas a `F1.02`, `F1.03`, `F2.01`–`F2.06`, `F3.01`–`F3.04`, `F4.01`, `F4.02`,
`F5.01`, `F5.02`, `F6.01`, `F6.02`, `P.E1`–`P.E3`, `F7.01`, `F7.02`, `R.01`, `REL-0.1.0`.

## Degradados o con reserva

- **16 y 17** dependen de ⚠️ afirmaciones no verificadas (alcance de mthree, backend falso disponible): quedan como spikes
  `S.01`/`S.02` con `resultado.json`, no como hechos.
- **20** (≈ 250 µs por disparo en hardware): ⚠️ sin verificar; no entra al plan como cifra.
- **24** (tests débiles de Toeplitz): entra como exigencia de `F1.02`, no se implementa ahora.

## Lo que esta revisión NO prueba

Es una revisión del diseño: nada se ha construido más allá de la bala trazadora con PRNG. «10/10» sigue sin demostrarse
hasta que corran las eurekas; `R.01` es la revisión propia del release y es distinta de esta.
