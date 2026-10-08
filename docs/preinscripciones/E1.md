# P.E1 — Preinscripción de E1: el pipeline entrega claves que cumplen M1–M5 con entrada ruidosa

Fecha: 2026-10-07. Valores en `declaraciones/E1.toml`; hereda `declaraciones/PARAMETROS.toml` (P.E0) y no cambia nada de él.
Nada de esto se ha corrido: **este documento no contiene ninguna cifra medida**. Lo derivado a mano está rotulado «analítico»;
las cifras de los spikes llevan su fuente; lo no comprobado, ⚠️. Una cifra de resultado saldrá de `registro/corridas/` o no se publica (FUNDAMENTO, regla 1).

## Qué afirma E1 y qué NO

**Afirma** (mensaje fundacional, O1–O5; FUNDAMENTO, objetivo): con entrada ruidosa (Aer + ruido de lectura asimétrico), el pipeline
(mitigación → Peres → Toeplitz → validación) entrega una clave que cumple **M1–M5** (`dominio/metricas.py`, desigualdades estrictas),
y la medición es capaz de distinguir una fuente mala de una buena (controles).

**No afirma**:
- **Nada sobre origen cuántico.** El muestreo de AerSimulator usa un PRNG (D-002, spike S.03). Que la clave pase NIST **no certifica origen ni impredecibilidad** (D-007, FUNDAMENTO discrepancia 6): C.E1a existe para demostrarlo.
- Nada sobre hardware real, cross-talk (no modelado) ni M6/M7 (los juzga E3).
- Que ε = 2⁻⁶⁴ sea una garantía: es un parámetro de diseño (discrepancia 8).
- Nada sobre los niveles de ruido bajo y alto: los barre E2. **E1 usa un solo nivel, el medio `(p(1|0), p(0|1)) = (0,02; 0,08)`** (el de E3), elegido hoy por ser el que el spike S.02 midió; ⚠️ es una elección de esta preinscripción, no un mandato de P.E0.

## Decisión previa a correr (delegada, 2026-10-07): M5 sobre la muestra «mitigada» es sólo informativa

**M5 (frecuencia por bloques, `adaptadores/nist.py`) se juzga sobre la CLAVE final y sobre la muestra cruda de la fuente ideal (C.E1a). Sobre la muestra «mitigada» se mide, se reporta y no decide.**

Motivo (diagnóstico previo del equipo, no una corrida registrada): el twirling por bloques de 200 deja un sesgo local de ±0,03 de signo aleatorio entre bloques.
El sesgo global se cancela (M1 y M3 lo ven bien), pero M5 mira justamente las frecuencias por bloques y lo detecta: χ²/N ≈ 1,8 y falla en 7 de 8 semillas, mientras que la clave sí pasa.
No es un fallo del pipeline sino una propiedad de la técnica que M5 mide correctamente; juzgar la mitigada por M5 castigaría a la mitigación por lo que la hace bien (simetrizar en media).
El pase relevante es el de la **clave**, que es lo que se cifra.

Qué NO cambia con esta decisión: ningún umbral (M5 sigue siendo p > 0,01 estricto) ni la medición de M5 en los tres puntos (P.E0 regla 4); sólo cambia qué punto decide. Tampoco se relaja M5 sobre la clave.

### ⚠️ Alerta analítica sobre M4 en la mitigada (no decidida; se declara)

M4 (runs) sobre la mitigada **comparte, con esta hipótesis, la causa de M5**. Comprobación de escritorio fuera del registro, no una cifra de resultado:
una secuencia sintética de 3,2 M de bits con sesgo local ±0,03 en bloques de 200 (signo aleatorio) da, en una semilla, monobit p ≈ 0,05 (pasa), runs p ≈ 3·10⁻¹⁰ (falla), frecuencia por bloques p ≈ 4·10⁻⁵ (falla);
la ideal sintética pasa las tres. Razón analítica: el número esperado de rachas cae en un factor ≈ (1 − 4δ²) con δ = 0,03 (≈ 0,36 %), unos 4–5 σ a este tamaño.
Si la mitigada real tiene ese sesgo local, **M4 en la mitigada fallará** por la misma causa que M5. Se deja **M4 decisiva en la mitigada, tal como pide el plan**, porque la delegación cubría sólo M5; mover M4 es decisión de quien dirige y exige **enmienda fechada anterior a C.E1c**.
Si no se enmienda y falla, el desenlace es el que la tabla dicta (NO CUMPLE, con M4 nombrada y la causa), no una avería.

> **Resuelto: ver «Enmienda fechada 2026-10-07» al final.** M4 en la mitigada pasa a informativa. El texto de esta sección es el original y se conserva.

## Diseño

| qué | valor | de dónde |
|---|---|---|
| qubits × shots | 8 × 400 000 = 3 200 000 bits crudos | P.E0 |
| semillas | 20261007, 20261008, 20261009; las tres cuentan, no se elige entre ellas | P.E0 |
| ruido de lectura (C.E1b, C.E1c) | nivel **medio** `(0,02; 0,08)`; sesgo analítico `|(p01 − p10)/2|` = **0,030** | P.E0 `[ruido_lectura]`; analítico |
| mitigación (C.E1c) | `twirling_propio`, `bloque` = 200, la semilla de la corrida; **no se ajusta** | F4.01, D-009, E2 |
| extracción | Peres (profundidad 8) + Toeplitz, ε = 2⁻⁶⁴ | P.E0 |
| M2 | de **salida**: mediana de bloques de 4096 bits (cota MCV al 99 %), mínimo aparte; de **entrada**: `h_min` del estimador, decide la longitud segura | P.E0 `[validacion]`, FUNDAMENTO discrepancia 5 |
| 90B | `ea_non_iid` (S.04, F5.02), sobre la cruda y la mitigada (≥ 1 000 000 de bits) | P.E0 regla 4 |
| M1, M3, M4, M5 | en tres puntos: cruda, mitigada, clave. M1 = `|p̂(1) − ½|` agregado de toda la muestra | P.E0 regla 4, `dominio/metricas.py` |

Las cuatro corridas usan las mismas tres semillas. Cada semilla produce un `InformeCorrida` (`datos/informe.py`) con `corrida` = `C.E1a`…`C.E1d`.

## Las cuatro corridas y sus criterios (fijados antes de correr)

### C.E1a — control negativo: un PRNG clásico pasa (la batería no distingue origen)

Fuente `FuentePrng` (origen `PRNG_CLASICO`), sin sesgo, 8 × 400 000 bits, tres semillas, sin mitigación.
**Criterio:** en cada semilla la cruda pasa M1, M3, M4, M5 y la clave pasa M1–M5. **Que pase es el resultado esperado y se declara** en el informe: significa que M1–M5 **no** prueban origen cuántico (D-007).
Es además el control N1 del instrumento: si la batería rechaza una fuente ideal conocida, no se sabe qué mide.
⚠️ Tasa de falsa alarma analítica: seis p-valores por semilla (M3, M4, M5 en cruda y en clave) × 3 semillas = 18 pruebas a α = 0,01; la probabilidad de que alguna caiga por azar es 1 − 0,99¹⁸ ≈ **0,165** si fueran independientes (⚠️ no verificado; las de cruda y clave no lo son del todo).
Es alta, y se acepta a ciencia cierta. Si ocurre: N1 falla, la corrida es inválida (código 9) con el p-valor y su valor registrados; **no se repite con otra semilla** (P.E0 regla 3). Distinguir azar de defecto exigirá una preinscripción nueva (E1a-bis) con la proporción de secuencias de NIST (93 × 10 240) como criterio, no un parche aquí.

### C.E1b — Aer ruidoso sin mitigar

Fuente Aer con el nivel medio, sin mitigador, tres semillas.
**Criterios, por semilla:**
- **B1 (decide):** la cruda **falla M1 o M3** (`|p̂(1) − ½| ≥ 0,01` o monobit p ≤ 0,01). Analítico: el sesgo inyectado es 0,030, tres veces el umbral de M1 y, a N = 3,2 M, varias decenas de σ de monobit.
- **D1 (control del detector):** `|sesgo medido de la cruda − 0,030| ≤ 0,002`. Si el aparato no ve el sesgo inyectado, la corrida es inválida (misma tolerancia que C1 de E2, que a su vez viene de F3.02).
- **Se reporta, no decide:** M4 y M5 de la cruda; el 90B de la cruda; y si la **clave** pasa M1–M5. Que Toeplitz limpie una cruda que falla es el hallazgo R.00-1 del pipeline (medir sólo la clave haría que cualquier fuente pasase), no un criterio de E1b.

### C.E1c — Aer ruidoso mitigado (twirling propio)

Mismo nivel y semillas que C.E1b, con `twirling_propio` (bloque 200).
**Criterios, por semilla (conjuntivos):**
- **M-1 (decide):** la **mitigada** pasa **M1, M3 y M4**. *(Enmendado 2026-10-07, ver al final: M4 en la mitigada es informativa; M-1 decide por M1 y M3.)*
- **M-2 (decide):** la **clave** pasa **M1, M2, M3, M4 y M5**.
- **Informativo (decisión previa):** M5 de la mitigada; el 90B de la cruda y de la mitigada con su `h_min` de entrada; la proporción de secuencias NIST de la clave (93 × 10 240, α = 0,01; mínimo aceptable ≈ 0,959 = 0,99 − 3·√(0,0099/93), analítico, P.E0).
- El 90B de la mitigada **no decide** aquí: su umbral 0,9 sólo decide en C.E1d (instrumento) y vía M2 de salida. ⚠️ Es decisión de esta preinscripción: el 90B es conservador a la baja (S.04: en IID p(1) = 0,7, h real 0,515 y el mínimo NIST dio 0,322), y su distribución sobre una fuente ideal de 1 M bits no está medida en este repo; fijarle un umbral decisivo en la mitigada antes de verla sería inventarlo.
- ⚠️ sin verificar que la «cruda» que registra C.E1c reproduzca la de C.E1b a igual semilla (depende de cómo el adaptador del twirling separa ambas muestras).

### C.E1d — control positivo: fuentes defectuosas rechazadas, fuente ideal aceptada

Sin sentido físico: fuentes sintéticas de **1 000 000 de bits** (el mínimo del 90B), una por semilla, con la semilla de la corrida:

| fuente | parámetro (como en el spike S.04) | rechazo exigido |
|---|---|---|
| sesgada | p(1) = 0,7 | M1 falla y M3 falla |
| periódica | `00001111` repetida | al menos una de M1/M3/M4/M5 **o** 90B < 0,9 |
| **Markov** | permanencia 0,8 (h real 0,322 bit/bit, analítico) | **90B < 0,9 y MCV ≥ 0,9** (el MCV la deja pasar) |
| ideal | PRNG sin sesgo | pasa M1, M3, M4, M5 **y** 90B > 0,9 |

Precedente medido (S.04, 1 000 000 de bits, semilla 20261007; no es resultado de E1): MCV de la Markov 0,9916 (pasa), mínimo NIST 0,170 (rechaza), periódica MCV 0,9963 y mínimo NIST 0; el MCV propio coincide con el de NIST a 6 decimales.
**Un control positivo que falla (P1) invalida E1**: sin él, un veredicto «pasa» no informa. En particular, si la fuente **ideal** no supera 90B > 0,9, el umbral 0,9 no es utilizable con ese estimador y esa longitud (⚠️ no medido), y la corrida es inválida; no se rebaja 0,9 aquí.

### ⚠️ Discrepancia con el plan: «la Markov por h_min y no por NIST»

El criterio del nodo C.E1d (`plan/`) dice que la Markov debe rechazarse «por h_min y no por NIST». Esta preinscripción **no lo adopta** porque es analíticamente improbable y la tesis de la discrepancia 8 es otra: la ciega es el **MCV**, no NIST.
La Markov con permanencia 0,8 cambia de valor en un 20 % de los pasos frente a un 50 % esperado: el test de rachas (M4) la ve de lejos. Comprobación de escritorio fuera del registro (1 M bits sintéticos): monobit p ≈ 0,009, runs p ≈ 0, frecuencia por bloques p ≈ 10⁻³⁶.
Lo que se preinscribe es lo que sí sostiene la discrepancia: **MCV ≥ 0,9 y 90B < 0,9**; qué métricas NIST la rechazan se reporta, y que M4/M5 también la rechacen es esperado. No se edita `plan/` (fuera de este encargo); queda como hallazgo para quien lo dirige.

## Controles (sin ellos no hay veredicto; así lo exige `qrecauda juzgar`)

| id | tipo | qué | si falla |
|---|---|---|---|
| N1 | negativo del instrumento | C.E1a: la batería acepta una fuente ideal | corrida inválida (probabilidad de falsa alarma ≈ 0,165, ver arriba) |
| D1 | positivo del detector | C.E1b: el sesgo medido coincide con el inyectado (0,030 ± 0,002) | inválida |
| P1 | positivo del estimador | C.E1d: sesgada, periódica y Markov rechazadas; ideal aceptada; MCV de la Markov ≥ 0,9 | inválida |

Un control que falla no es un «no cumple»: es «no se midió bien» (`CorridaInvalida`, código 9).

## Tabla de desenlaces (decididos hoy)

| desenlace | condición | qué se escribe | qué NO se hace |
|---|---|---|---|
| **CUMPLE** | N1, D1, P1 válidos; C.E1a, B1 de C.E1b, M-1 y M-2 de C.E1c en las 3 semillas | veredicto aprobado, con el rótulo «el pipeline entrega claves que pasan M1–M5; **esto no certifica origen cuántico**» | presentar la clave como «certificada» |
| **NO CUMPLE** | M-1 o M-2 de C.E1c fallan en alguna semilla | resultado negativo que **nombra** semilla, métrica y p-valor/valor; una semilla que falla no se repite ni se sustituye | relajar un umbral; repetir con otra semilla; mover M4 a informativa después de verla |
| **NULO** | B1 falla: la cruda **no** falla M1 ni M3 con el ruido declarado (D1 válido) | «el ruido medio no deteriora la muestra al punto de que M1/M3 lo vean»; E1 no dice nada sobre la mitigación | subir el nivel de ruido para «provocarlo» (sería otra pregunta: E1b-bis preinscrita) |
| **CUMPLE PARCIAL** | M-2 (clave) pasa pero M-1 (mitigada) falla | «la clave pasa; la mitigada no, en la métrica X» | declarar E1 cumplido sin el matiz |
| **INVÁLIDA** | N1, D1 o P1 fallan | incidencia con la causa; no hay veredicto | emitir veredicto |
| **INCONCLUSO por muestra** | alguna prueba no tiene bits suficientes (p. ej. 90B < 1 M) | P.E0 regla 1: se suben los shots y se corre de nuevo con la misma declaración enmendada **antes** | relajar umbrales |

El hallazgo «la clave de C.E1b pasa aunque la cruda falle» se escribe tal cual sea cual sea el desenlace; no condiciona CUMPLE/NO CUMPLE.
Reintentar tras un resultado negativo exige una **preinscripción nueva** (E1b-bis…) con otra hipótesis; el veredicto anterior se conserva (registro append-only).

## Cómo juzga el juez actual (⚠️ límite declarado)

`aplicacion/juez.py` no tiene criterio propio para E1: usa el respaldo genérico `_juzgar_informes`, que lee **un `InformeCorrida` por semilla** y aprueba si su veredicto
(sobre la clave) cumple M1–M5. Eso es **estrictamente menos** que esta preinscripción:
- no lee la cruda ni la mitigada (las medidas por etapa están en `informe.etapas`, que el respaldo ignora);
- no distingue las cuatro corridas: con cuatro informes por semilla, `por_semilla` conserva el último y descarta los otros;
- los controles sólo pueden exigirse como booleanos de `[controles].requeridos` (N1, D1, P1) que el `Ejecutor` calcula; un fallo ahí se informa como corrida inválida, que es lo correcto para controles, pero **B1, M-1 y M-2 no pueden expresarse como controles** (un «no cumple» no es una avería).
Hasta que exista un `_juzgar_e1` (nodo nuevo, no escrito aquí) el veredicto de E1 no puede emitirse honestamente por el respaldo; no se «adapta» la preinscripción al respaldo.
Además `nodo_corrida` de la declaración es único (`C.E1`) mientras el plan fija cuatro rutas `registro/corridas/E1a…E1d.json`; reconciliar ambos es trabajo del `Ejecutor`/juez, no de este documento.

## Trazabilidad

- C.E1a–d citan el sha del commit de esta preinscripción (`preinscripcion_sha`); `juzgar` se niega si ese commit no precede a la corrida o si el documento cambió después.
- Entorno con `transversal.reproducibilidad.entorno()`; BLAS a un hilo; corrida bajo el candado de máquina.
- Cifras «analítico»: reproducibles con una línea de Python. Ninguna es un resultado.

## Abierto (⚠️ sin verificar)

1. Que el twirling real deje el sesgo local ±0,03 descrito (diagnóstico del equipo, sin corrida registrada) y que M4 sobre la mitigada sufra lo mismo (alerta arriba).
2. La distribución del 90B (`ea_non_iid`) sobre una fuente ideal de 1 M bits: no medida; condiciona P1. **Medida el 2026-10-07 (antes de correr E1) y resuelta por la «Enmienda 2 (P1)» al final.**
3. Qué «cruda» registra el twirling en C.E1c (¿la misma de C.E1b?).
4. Falsa alarma de N1 ≈ 0,165 (supone independencia).
5. Que 3,2 M bits de clave-pool alcancen para 1 M de 90B tras `Peres`; se mide en la corrida, no se asume.
6. El hueco del respaldo del juez y el nodo único `C.E1` (arriba).
7. El nivel medio como único nivel de E1 es elección de esta preinscripción.

## Cómo se revertiría
Un error en esta tabla antes de correr se corrige por **enmienda fechada** de este documento y de `E1.toml`, en commit propio y anterior a la primera corrida de E1. Después de correr, no se toca.

## Enmienda fechada 2026-10-07 (anterior a C.E1c; no cambia ningún umbral)

**M4 (runs) sobre la muestra «mitigada» pasa a informativa**, igual que M5: se mide, se reporta y no decide. Decisión de quien dirige, tomada antes de correr C.E1c.

- Motivo: es la misma causa que ya llevó a M5 a informativa. El twirling por bloques de 200 deja un sesgo local de ±0,03 con signo aleatorio entre bloques; el sesgo global se cancela (M1 y M3 lo ven bien) pero las pruebas que miran estructura local lo detectan.
  La simulación de escritorio de la alerta de arriba (fuera del registro, no es un resultado) indica que runs también falla: p ≈ 3·10⁻¹⁰ frente a monobit p ≈ 0,05. Juzgar la mitigada por M4 castigaría a la mitigación por lo que hace bien (simetrizar en media).
- **M-1 queda así:** la mitigada pasa **M1 y M3** (M3 decidía ya, y sigue decidiendo). M4 y M5 de la mitigada se reportan sin decidir.
- **Lo que NO cambia:** ningún umbral (M4 sigue siendo p > 0,01 estricto); la medición de M1, M3, M4 y M5 en los tres puntos (P.E0 regla 4); **la clave sigue decidiendo M1–M5 completas** (M-2); y la cruda de C.E1a sigue decidiendo M1, M3, M4, M5 (N1).
- Qué sigue pudiendo salir: si la clave pasa y la mitigada falla M1 o M3, el desenlace es CUMPLE PARCIAL, como dicta la tabla.
- ⚠️ Esta enmienda se decide por un diagnóstico y una simulación de escritorio, no por una corrida registrada: que M4 falle realmente en la mitigada queda sin verificar y se reportará.

## Enmienda fechada 2026-10-07 (2): P1 pasa de «umbral absoluto 0,9» a «separación del instrumento» (anterior a toda corrida de E1; no toca M1–M5)

**Qué se enmienda.** Sólo el criterio P1 (control positivo del estimador, C.E1d). Se reemplazan, en la fila «ideal» y en la fila «Markov» de la tabla de C.E1d,
el umbral absoluto 90B = 0,9 por dos constantes calibradas, ambas en `declaraciones/E1.toml [criterios.c_e1d]`. Ningún umbral de M1–M5 cambia
(`dominio/metricas.py` queda intacto, incluido M2 de la clave, 0,9). El texto original de arriba se conserva; lo que manda es esto.

**Honestidad sobre cuándo se midió.** El 90B de la fuente ideal se midió **antes de correr E1**, pero **sobre las semillas declaradas** (20261007/8/9) y ocho más:
no es una medida «ciega» de la declaración, es una calibración hecha con las semillas que la corrida usará. Por eso el piso se fija con las 11 medidas y con margen (abajo),
y se declara aquí que quien lo fijó ya conocía los tres valores de las semillas declaradas (0,821; 0,902; 0,832). Esto no es un resultado de E1.

**Hecho medido.** `spikes/S04_90b/calibracion_p1.py` → `spikes/S04_90b/calibracion_p1.json` (1 000 000 bits por fuente y semilla, `ea_non_iid -i -a` v1.1.8,
mismas clases de fuente que el ejecutor; semillas 20261007–20261009 y 20261010–20261017):

| fuente | 90B mín – máx (11 semillas) | MCV mín – máx |
|---|---|---|
| ideal (PRNG) | **0,821 – 0,903**; sólo 2 de 11 superan 0,9 (0,902 y 0,903) | — |
| Markov (permanencia 0,8; h real 0,322 analítico) | 0,1699 – 0,1717 (Collision) | 0,9898 – 0,9962 |
| sesgada (p(1) = 0,7; h real 0,515) | 0,3208 – 0,3237 | — |
| periódica `00001111` | 0 en las 11 | — |

Lectura: el criterio original («ideal con 90B > 0,9») fallaba en 9 de 11 fuentes **ideales**, o sea declaraba inválido al instrumento por una propiedad suya y no de la fuente:
con 1 M de bits el mínimo de 10 estimadores es una cota inferior conservadora (ya lo decía S.04: IID p = 0,7 → 0,322 frente a 0,515 teórico) y, además, sesgada incluso sobre una fuente perfecta (h = 1).
El umbral 0,9 de M2 es el de la **clave de salida** tras Toeplitz, otra magnitud; trasladarlo al estimador de entrada con 1 M de bits fue un error de la preinscripción, no un fallo de la fuente.

**Nuevo P1 (por semilla; las cuatro condiciones a la vez; el 0,9 original no se «rebaja», se sustituye por una prueba de separación):**

1. **ideal**: M1, M3, M4, M5 pasan **y** 90B ≥ `piso_ideal_90b` = **0,8**. Cómo sale: mínimo de las 11 medidas (0,821) redondeado hacia abajo a 0,1; deja 0,021 de margen bajo el mínimo observado.
2. **Markov**: 90B < `techo_rechazo_90b` = **0,5** **y** MCV ≥ 0,9 (ceguera del MCV, discrepancia 8). Observado: 90B ≤ 0,1717 (0,33 por debajo del techo), MCV ≥ 0,9898.
3. **periódica**: alguna de M1/M3/M4/M5 falla **o** 90B < 0,5. Observado: 0.
4. **sesgada**: M1 falla y M3 falla (sin cambio). Su 90B (≈ 0,322) se reporta, no decide.

Separación calibrada: peor ideal (0,821) − mejor Markov (0,1717) = **0,649**; el piso 0,8 y el techo 0,5 dejan 0,3 de hueco entre ambos, que es el que el instrumento debe poder cruzar para que un «pasa» o un «rechaza» informe algo.
Por qué es más defendible que bajar el umbral a un valor suelto: la pregunta que P1 contesta es «¿el estimador distingue lo bueno de lo malo?», que es una **separación**, y no «¿la ideal alcanza 0,9?», que depende del tamaño de muestra.
Se descartó como piso el 0,5 (sin medida que lo ancle) y una media − k·σ de 11 puntos (frágil con n = 11).

**⚠️ Límites.** (a) Con n = 11 el piso no es un intervalo de tolerancia: la ideal de las semillas declaradas ya se conoce (todas ≥ 0,821 > 0,8) porque el PRNG es determinista, de modo que P1 pasará en ellas salvo cambio de código;
para una semilla futura, la cola inferior por debajo de 0,8 no se ha medido (⚠️ sin verificar). (b) La calibración usa los 3 + 8 semillas del PRNG; sobre bits de Aer ruidoso/mitigado el 90B puede comportarse distinto: esos 90B de C.E1b/C.E1c siguen informativos (no deciden). (c) Esto fija el control, no certifica nada del pipeline.

**Consecuencia para la longitud de la clave.** La longitud segura es m = ⌊n·h_min − 2·log2(1/ε)⌋ (`dominio/extractores.longitud_segura`, Leftover Hash Lemma): lo que se pierde de h_min se pierde 1 a 1 de la clave.
Si la h_min de entrada la da el 90B en vez del MCV, el estimador conservador **reduce el rendimiento aun con una fuente perfecta**: con el 90B medio de la ideal (0,859, media de las 11) la clave sale ≈ 14 % más corta que con h = 1
(0,821 → −18 %; 0,903 → −10 %, analítico, sin el término fijo de 128 bits), y con la Markov (90B 0,17 contra h real 0,322) se entrega ≈ 47 % menos de lo que la fuente sostendría (0,17 / 0,322 ≈ 0,53), a cambio de no extraer de más. Es el precio de la cota segura (D-007, discrepancia 8) y no una avería.
Hoy los informes llevan `estimador = "mcv"` en la h_min de entrada; adoptar el 90B para dimensionar es una decisión de F5.02 aparte (⚠️ no tomada aquí), y con muestras de más de 1 M de bits el sesgo conservador podría ser menor (no medido).
