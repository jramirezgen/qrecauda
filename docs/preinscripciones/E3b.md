# P.E3b — Preinscripción de E3b: la latencia de transacción cumple M7 cuando la clave sale de una reserva generada aparte

Fecha: 2026-10-08. Valores en `declaraciones/E3b.toml`; hereda `declaraciones/PARAMETROS.toml` (P.E0).
Nada de E3b se ha corrido: **ninguna cifra de este documento es un resultado ni una estimación medida**. Una cifra saldrá de `registro/corridas/C.E3b.json` o no se publica.

## Qué afirma E3b y qué no

**Pregunta.** E3 midió una transacción cuya clave se generaba *dentro* de la transacción y NO CUMPLE (M7: p95 de 5,5 a 9,4 s frente a 500 ms). E3b pregunta
otra cosa: si la clave sale de una **reserva generada aparte** —por un proceso productor que corre en paralelo a las transacciones—, ¿la latencia de la
transacción cumple M7 (< 500 ms, estricto) mientras el productor sostiene M6 (> 10 000 bit/s, estricto) y supera el consumo declarado?

**No afirma**:
- que E3 cumpla ni que se reabra: **el veredicto de E3 (NO CUMPLE) queda en el registro y no se toca**. E3b no lo rescata ni lo repite; es otra arquitectura, otra
  preinscripción y otro veredicto. El perfil B de E3 (30–63 mil tx/s con la reserva ya cargada) **no es evidencia de E3b**: era un ciclo de AES-GCM sin productor.
- nada sobre IBM real. M7 **no incluye la cola ni la red de IBM Quantum**. La demo se rotula «validación del pipeline», nunca «entropía cuántica» (D-002): el muestreo de Aer es un PRNG.
- que 500 ms, 10 kbit/s o 100 tx/s sean lo que OSITRAN, el MTC o el Metro exijan: ⚠️ sin verificar; los umbrales vienen del manifiesto del equipo y la demanda λ es **declarada por el equipo**, no medida de un operador.
- que la arquitectura sea mejor: **traslada el coste** (ver Limitaciones).

## Arquitectura bajo prueba

```
proceso PRODUCTOR (núcleo 8, un hilo)                        proceso CONSUMIDOR (núcleo 4, un hilo)
 cadena de E3: fuente Aer ruidoso medio → twirling → Peres      ReservaAsincrona
 → Toeplitz → M1–M5 + 90B; clave rechazada ⇒ se regenera        └ ReservaDeClave (registro de consumo: nunca repite (clave, nonce))
 clave aprobada ──► cola acotada (C = 2 claves) ──────────►     └ trozo de 352 bits ⇒ AES-256-GCM cifra y descifra una transacción
```

- **Productor**: un proceso aparte (`multiprocessing`, método `spawn`), fijado a su núcleo con `os.sched_setaffinity`, `OMP_NUM_THREADS=1`, BLAS a un hilo (`threadpoolctl`) y `max_parallel_threads=1` en Aer. La clave `i` usa la semilla `semilla·100 + i`; el reintento `k` suma `k·10⁹` (como E3). Se detiene bloqueado cuando la cola está llena (contrapresión).
- **Consumidor**: el proceso que ejecuta C.E3b, fijado a su núcleo. Toma trozos de 352 bits (clave 256 + nonce 96) con `ReservaDeClave` (el registro de consumo de B-1: ningún `(clave, nonce)` sale dos veces) y, al agotarse una clave, toma la siguiente de la cola. Los < 352 bits finales de cada clave se descartan.
- **La clave cruza entre procesos en memoria** (cola de `multiprocessing`, empaquetada en bytes). No se imprime, no se escribe a disco, no entra en manifiestos ni bitácora: sólo su huella corta (12 hex de sha256).
- El **cambio de clave** (sacar la siguiente de la cola, desempaquetarla, crear su reserva) ocurre dentro de la transacción que lo provoca y **cuenta en su latencia**.

## Perfiles (por semilla; 20261007, 20261008, 20261009 como E3)

| perfil | qué mide | decide |
|---|---|---|
| **R1 «arranque»** | pared desde `iniciar()` del productor (arranque del proceso, imports, primera clave aprobada) hasta tener 1 clave en la reserva | **no**: informativo. Es el cebado de R2 |
| **R2 «régimen»** | demanda declarada **λ = 100 tx/s durante 120 s de pared** (12 000 transacciones, 35,2 kbit/s de clave, alternando peaje/metro, contenido sintético sin datos personales), con la reserva cebada con 1 clave y el productor corriendo en paralelo | **sí** |

Las llegadas son **programadas** (lazo abierto): la transacción *i* llega en `t_ini + i/λ`. Si el consumidor va retrasado (p. ej. esperó una clave), el retraso **entra en la latencia** de las que se acumulan. El contenido de las 12 000 transacciones se construye antes de R2; su serialización y el cifrado sí están en la medida.

## Definiciones (fijadas antes de medir)

| métrica | definición | reloj |
|---|---|---|
| `latencia_i` | pared desde la **llegada programada** de la transacción *i* hasta que el descifrado verifica (`descifrada == original`); incluye cualquier espera por reserva vacía y el cambio de clave | `time.perf_counter_ns` |
| **M7** (ms) | **p95** de `latencia_i` sobre las 12 000 de R2; `numpy.percentile(..., 95, method="higher")` | ídem |
| **tasa neta del productor** (bit/s) | `Σ bits(clave aprobada) / Σ t_gen` sobre las claves cuya generación **termina dentro de la ventana de R2** `[t_ini, t_fin]`. `t_gen` es la pared de **todos los intentos** de esa clave (los rechazados suman, como en E3) y **no** incluye el tiempo bloqueado por cola llena | ídem |
| **consumo** (bit/s) | `λ · 352 = 35 200` | |
| **esperas** | nº de veces que `siguiente()` necesitó clave nueva y la reserva no la tenía lista (tomarla sin esperar no devuelve nada); además se suma el tiempo esperado | |
| cpu/pared | productor: (CPU propia + hijos esperados, p. ej. el binario del 90B) / pared del proceso desde que entra su función hasta que sale; consumidor: CPU propia / pared de R2 | `os.times`, `time.process_time_ns` |

`perf_counter_ns` es `CLOCK_MONOTONIC` en Linux, común a los dos procesos; se usa para asignar cada clave a la ventana de R2. ⚠️ sin verificar que WSL2 lo cumpla idéntico entre procesos (si no, la asignación de claves a la ventana podría correrse unos µs; no afecta a la latencia, que se mide en un solo proceso).

Se reportan además, **sin decidir**: R1 (ms), mediana/p99/máximo de la latencia, tiempo de cada cambio de clave, claves rechazadas por clave, tiempo bloqueado por cola llena, tasa entregada en la ventana (limitada por la contrapresión), tamaño de la cola en cada cambio de clave, CPU de cada proceso y afinidad efectiva.

## Criterios de E3b

Veredicto **conjuntivo**, por semilla y en las tres:

| id | criterio | umbral |
|---|---|---|
| T1 | sostenibilidad: tasa neta del productor en R2 **> 10 000 bit/s** (M6, estricto, `medir(TASA)`) **y > consumo 35 200 bit/s** (estricto) | R2, por semilla |
| T2 | latencia: **p95 < 500 ms** (M7, estricto, `medir(LATENCIA)`) | R2, por semilla |
| T3 | sin esperas: contador de esperas **= 0** y reserva no agotada | R2, por semilla |
| T4 | un hilo por proceso: cpu/pared **≤ 1,10** en productor y en consumidor | **control de validez** (como T4 de E3): falla ⇒ INVÁLIDA |
| U1 | ida y vuelta: toda transacción realizada descifra a su original | control |
| U2 | nonces distintos en toda la corrida | control |
| U3 | trozos distintos: ningún `(clave, nonce)` repetido y ninguna clave repetida | control |
| U4 | ninguna clave en la bitácora ni en el informe (ni su hex ni sus bits); sólo huellas de 12 hex | control |
| U5 | rótulo: todas las claves «validación del pipeline», origen `simulador_aer`, ninguna reclama origen cuántico | control (heredado de E3) |

Los umbrales numéricos de T1–T4 están **repetidos** en `E3b.toml` y el juez comprueba que coinciden con `dominio/metricas.py` y con λ·352; si no coinciden, no se juzga. El juez **recalcula** p95, tasa neta y esperas a partir de los datos crudos del informe (latencias, claves con su ventana), no de los resúmenes del ejecutor.

Una semilla que falla no se repite ni se sustituye. Si T1, T2 o T3 fallan, el veredicto dice **cuál y por cuánto** (cociente a umbral). **Ningún umbral, λ, duración ni capacidad se mueve a posteriori**; cambiarlos es otra preinscripción.

## Desenlaces

| desenlace | condición | qué se escribe |
|---|---|---|
| **CUMPLE** | T1–T3 en las tres semillas, T4 y U1–U5 pasan | veredicto aprobado, con M7 p95, tasa neta, esperas y R1 por semilla |
| **NO CUMPLE** | T1, T2 o T3 falla en alguna semilla | el veredicto nombra el criterio, la semilla y el cociente a umbral. Es un resultado, no una avería |
| **INVÁLIDA** | T4 o algún U falla; carga previa ≥ 3,0 tras el reposo; núcleos declarados no disponibles; el productor muere o no logra una clave tras 5 intentos seguidos; el candado de máquina está ocupado | incidencia con la causa; no hay veredicto; se repite la **misma** declaración con las mismas semillas tras corregir el entorno |

## Configuración fija

Lote por clave, backend, ruido, mitigación, validador, semillas y 90B: los de E3 (8 qubits × 400 000 shots, `aer_ruidoso` nivel medio (0,02; 0,08), `twirling_propio` bloque 200, M1–M5 con `nistrng` y 90B sobre 10⁶ bits crudos). Una clave rechazada por M1–M5 se regenera con la semilla `semilla_i + k·10⁹` (k = 1…4) y su tiempo suma a `t_gen`; 5 rechazos seguidos ⇒ INVÁLIDA. En el punto «mitigada» la validación es informativa (enmienda 2026-10-07 de E3); decide la clave.

**Máquina.** La PC de desarrollo (WSL2, 20 núcleos lógicos) con candado de máquina. Núcleos declarados: **consumidor 4, productor 8** (pares SMT distintos 4-5 y 8-9 según el kernel de WSL2; ⚠️ la topología que ve WSL2 puede no ser la del anfitrión). Carga previa: `os.getloadavg()[0] < 3,0` al arrancar cada semilla, con reposo de hasta 900 s entre semillas (mismo mecanismo que la enmienda de E3; el umbral sube de 2,0 a 3,0 porque ahora hay **dos** procesos propios). Se lanza con la máquina quieta; un proceso ajeno que ocupe esos núcleos delata su efecto en T4 o en el tiempo de pared.

## Limitaciones declaradas (⚠️ y alcance)

1. **La arquitectura traslada el coste, no lo elimina.** El arranque en frío sigue costando segundos (R1, informativo); un servicio real pagaría ese arranque una vez y tendría que decidir qué hace una transacción que llega durante él. E3b no mide esa transacción: R2 empieza con la reserva ya cebada.
2. **La reserva es un depósito de claves en memoria con exposición mayor.** Hasta ~3 claves de ≈ 10⁶ bits (la que se consume, dos en cola) más la que se genera viven en memoria y cruzan un pipe entre procesos. No hay KMS/HSM, custodia, rotación ni borrado seguro de memoria (AMENAZAS, ROADMAP). El salto 1 del ROADMAP ya lo anticipa: **aumenta** la exigencia de custodia.
3. **La latencia se mide en simulador.** Sin hardware IBM (D-010): no incluye cola, red ni la latencia real de un QPU, que haría el productor mucho más lento que Aer; T1 con Aer **no** dice que una fuente real sostenga el consumo.
4. **No repite E3 ni lo rescata.** Las claves y la cadena son las mismas, pero lo que se mide es otro: la latencia de la transacción con la clave ya disponible, y la capacidad del productor para reponerla.
5. **El dimensionado de la clave con MCV bajo supuesto IID sigue vigente** (R.01, A-3): una fuente con dependencia daría claves más cortas de lo que sostiene el 90B. No se cambia aquí (cambiarlo mueve las claves y exigiría repetir E1–E3).
6. **Ventana finita.** 120 s con ≈ 4–5 cambios de clave por semilla: el p95 de 12 000 transacciones **no ve** eventos que afecten a < 5 % de ellas. Un cambio de clave afecta a una sola transacción; por eso existe T3 (cero esperas) y por eso el máximo y el tiempo de cada cambio se reportan. E3b no dice nada de horas de operación continua.
7. **λ = 100 tx/s es una demanda declarada**, no un requisito de operador; el cociente entre producción y consumo (≈ 5×, ⚠️ hipótesis a partir de los 180–195 kbit/s de E3, **no medida aquí**) es lo que T1 comprueba.
8. **Dos procesos propios y un proceso ajeno posible.** WSL2 programa los hilos de Windows por debajo; núcleos y SMT declarados no son garantía. T4 y el tiempo de pared delatan la contaminación, no la impiden.
9. **El filtrado por pruebas estadísticas** (regenerar claves rechazadas, ≈ 4 %) es una práctica desaconsejada (R.01, M-3) que E3b hereda de E3 para ser comparable; se cuenta cuántas se rechazan.
10. **Contenido sintético**: ningún dato personal; la tarjeta es pseudónima.

## Hipótesis esperada ⚠️ (hipótesis, no medida)

**CUMPLE.** Razonamiento, no resultado: el ciclo AES-GCM de una transacción cuesta decenas de µs (el perfil B de E3 no decide, pero el orden de magnitud es el de la primitiva); el productor produjo 180–195 kbit/s a un hilo en E3 (≈ 5× el consumo); una clave de ≈ 10⁶ bits alimenta ≈ 2 700 transacciones (≈ 27 s a λ = 100), mucho más que los 5,5–9,4 s de generar la siguiente. Riesgos que pueden refutarla: contención entre los dos procesos (ancho de banda de memoria, SMT), gestión de memoria de Python en el cambio de clave, jitter del planificador de WSL2 y que el productor, al compartir máquina con el consumidor, baje su tasa. Si la hipótesis falla, el veredicto es NO CUMPLE y se publica.

## Trazabilidad

- C.E3b cita el sha del commit de esta preinscripción (`preinscripcion_sha`); `juzgar` se niega si ese commit no precede a la corrida o si estos ficheros cambiaron después.
- La implementación (`aplicacion/reserva_asincrona.py`, `aplicacion/ejecutor_e3b.py`, `adaptadores/productor_en_proceso.py`) se prueba con dobles; **ninguna corrida real de E3b existe** al momento de preinscribir.
- Las cifras de E3b salen de `registro/corridas/C.E3b.json`; las de E3 siguen saliendo de `C.E3.json`.

## Cómo se revertiría

Un error en esta tabla antes de correr se corrige por **enmienda fechada** al final de este documento, en commit propio y anterior a C.E3b. Después de correr, no se toca.
