# FUNDAMENTO de QRecauda

> Manda sobre el objetivo, el alcance y las reglas. Sólo cambia por enmienda (`docs/enmiendas/`, aún vacía).
> Fuentes: `docs/origen/MENSAJE_FUNDACIONAL.md` (el manifiesto del equipo) y
> `docs/origen/ESTRATEGIA_QRNG_QRECAUDA.md` (la estrategia, 60 KB). Donde difieren, manda este documento,
> y la diferencia está en «Discrepancias declaradas».

## Objetivo general

Construir un **pipeline QRNG reproducible**: circuito H⊗n → muestreo → mitigación → extractores
(von Neumann/Peres + Toeplitz) → validación NIST → clave, con un caso de uso de recaudación peruana
(peaje/Metro) y siete métricas de aceptación medidas, no declaradas.

*Track 4 · Hackatón Qiskit IBM Lima. Tesis del equipo: «La aleatoriedad clásica se predice. La recaudación del Perú no debería.»*

## Objetivos por rama (estado: resuelto o pausado, nunca «olvidado»)

| rama | objetivo específico | estado |
|---|---|---|
| núcleo | dominio puro + bala trazadora con PRNG (F1, F2) | **escrito, sin commitear** — se cierra al commitear |
| simulador | Aer + modelo de ruido + mitigación (F3, F4) | pausado hasta S.01 |
| hardware | SamplerV2 sobre IBM real (F3.04) | pausado: depende de acceso y de S.01 |
| validación | NIST + 90B, contrastados con el validador propio (F5) | pausado |
| caso de uso | AES-GCM con la clave del pipeline (F6) | pausado |
| difusión | notebook, pitch, roadmap, wiki (F7) | pausado |

## Alcance v0.1.0

Incluye: pipeline de punta a punta en PC (16 GB, sin colas), modelo de ruido propio, mitigación, extractores,
validación estadística, demo de cifrado, notebook, pitch, wiki. **Hardware IBM real es opcional** (`F3.04` es el adaptador con un doble;
`F3.06` cierra con una corrida real o con la constancia de que no hay acceso) y ni la demo ni el release dependen de él.

No incluye: integración con sistemas de OSITRAN/MTC/Metro, certificación FIPS/ISO, multiplexado en varios backends,
HSM, distribución de claves.

## Reglas

1. **Una cifra sale de una corrida nombrada** (`registro/corridas/`), nunca de memoria ni del pitch.
2. **Los secretos entran por ruta, nunca por valor** y no se imprimen ni truncados.
3. **Nunca se atribuye nada a un modelo** en commits, PR o releases (hook `commit-msg`).
4. **El plan es el DAG** (`plan/`); el estado vive en `registro/`; `ESTADO.md` es generado.
5. **Preinscribir antes de correr**: umbral y criterio de cada eureka se fijan en `docs/preinscripciones/` antes de la corrida.
6. **La CI local corre antes de empujar** (`scripts/ci_local.sh`).

## Discrepancias declaradas con el mensaje fundacional

El mensaje fundacional es la autoridad sobre el *objetivo*. Lo siguiente son puntos donde su *método* choca con lo que
las bibliotecas o la estadística permiten; se declaran antes de actuar y cada una tiene un spike o un test que la resuelve.
Todo lo marcado ⚠️ es hipótesis de trabajo, no premisa.

| # | El mensaje dice | Lo que hay que resolver | Cómo se resuelve | Estado |
|---|---|---|---|---|
| 1 | «No dependemos de hardware real» y, en la estrategia, «ejecutado sobre procesadores físicos de IBM» | Son dos alcances distintos | El backend es un puerto (D-001): simulador por defecto, hardware opcional | decidido |
| 2 | Aer + modelo de ruido produce «entropía cuántica» | **El muestreo de AerSimulator usa un PRNG**: sus bits son pseudoaleatorios aunque el circuito sea H⊗n | `Origen.SIMULADOR_AER` no reclama origen cuántico (D-002); spike S.03 lo demuestra; el pitch lo dice | decidido, falta S.03 |
| 3 | TREX + ZNE + PEC/PNA mitigan el *bitstream* de SamplerV2 | ⚠️ ZNE y PEC se definen sobre valores esperados (Estimator); `resilience_level` y `measure_mitigation` son opciones de EstimatorV2, no de SamplerV2 | Spike S.02; mientras tanto: lectura sobre bitstrings, ZNE/PEC sobre ⟨Z⟩ (D-003) | ⚠️ sin verificar |
| 4 | «TREX vía `mthree`» | ⚠️ TREX (twirled readout) y `mthree` (mitigación matrix-free) son técnicas distintas; y `mthree` puede no soportar el qiskit actual | Spike S.01 fija versiones; el adaptador se llama por lo que implementa | ⚠️ sin verificar |
| 5 | Min-entropía > 0,9 es una prueba de calidad | Medida **tras** Toeplitz es ≈ 1 por construcción: no informa. La informativa es la de la entrada al extractor | Se reportan las dos: `h_min` de entrada (decide la longitud segura) y la de salida (M2) | decidido |
| 6 | «Claves certificadas» | NIST SP 800-22 es una batería de **pruebas estadísticas**: un PRNG las pasa. No certifica origen ni impredecibilidad | El eureka E1 lleva un control negativo (PRNG pasa) y el informe lo dice (D-007) | decidido |
| 7 | «TRL 4» (el manifiesto lo define como «en una PC de 16 GB, sin colas ni credenciales») | La rúbrica de TRL pide repetibilidad n ≥ 3, protocolo preinscrito y auditable por un tercero, y el TRL real es el de la afirmación más débil: la fuente cuántica en simulador es TRL 3 | `T.TRL` deriva el rótulo de la evidencia; el simulador sostiene el pipeline de postprocesamiento y cifrado, y la fuente cuántica sube sólo con `F3.06` (corrida real con `job_id`) | declarado, lo cierra `T.TRL` |
| 8 | Min-entropía por MCV decide la longitud de la clave y la «certifica» | MCV mira la frecuencia marginal y es ciego a la dependencia: una cadena de Markov con permanencia 0,8 (real 0,32 bit/bit) da 0,990 y pasa | Estimador 90B no-IID tras un puerto propio (`S.04`, `F5.02`) y control positivo `C.E1d`; ε = 2⁻⁶⁴ es un parámetro de diseño, no una garantía | decidido, falta `S.04` |
| 9 | M1 < 1 % y M2 > 0,9 como umbrales de aceptación | A N = 800 000 monobit exige un sesgo < 0,0014 (siete veces más estricto que M1) y M2 sobre una clave de 256 bits no puede pasar de 0,785 | `P.E0` fija M2 sobre bloques de 4096 bits y el dimensionamiento de la cadena | decidido, falta `P.E0` |

## Los códigos O1–O7 y R1–R6

El mensaje fundacional no los numera; se toman de sus listas, en su orden.

| código | texto del mensaje fundacional | lo realiza |
|---|---|---|
| O1 | circuito QRNG de 8–10 qubits sobre AerSimulator | `F3.01` |
| O2 | modelo de ruido personalizado (lectura, decoherencia, cross-talk) | `F3.02` |
| O3 | mitigación local con TREX (`mthree`) y ZNE | `F4.01`, `F4.02` |
| O4 | extractores von Neumann + Toeplitz | `F1.02` |
| O5 | validación NIST SP 800-22 con `nistrng` | `F5.01` |
| O6 | demo de cifrado de una transacción de peaje/Metro | `F6.01`, `F6.02` |
| O7 | notebook reproducible | `F7.01` |
| R1 | modelización algebraica (canal Pauli-Lindblad, `NoiseLearnerV3`) | `F3.02` (matriz de confusión; Pauli-Lindblad queda declarado no aplicable en local) |
| R2 | stack actual (`SamplerV2`, PUBs, `Batch`/`Session`) | `F3.01`, `S.01` |
| R3 | transpilación guiada por IA | `F3.03` |
| R4 | QEM (TREX, ZNE, PEC/PNA, `Samplomatic`) | `S.02`, `F4.02` |
| R5 | reproducibilidad (GitHub, `requirements.txt`, versiones exactas) | `S.01`, `F7.01` |
| R6 | impacto (OSITRAN, MTC, Metro de Lima, peajes) | `F7.02` |

## Limitaciones (no cerrables en la hackatón)

- El simulador no aporta entropía cuántica; sólo el hardware lo hace y aun así **no se certifica** su origen sin
  pruebas de Bell o autoverificación (fuera de alcance).
- El semillado de Toeplitz exige bits uniformes independientes: se toman del mismo pool (D-004); la suposición de
  independencia entre bloques es una hipótesis del modelo de ruido, no un hecho medido.
- Las latencias medidas en PC no incluyen la cola ni la red de IBM Quantum.
