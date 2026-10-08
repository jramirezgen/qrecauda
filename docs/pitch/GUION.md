# Guion de dos minutos

Acompaña a [`DECK.md`](DECK.md) (deck de diez láminas, `deck.pdf`). Ritmo de unas dos palabras y media por segundo: cada
bloque de abajo cabe en su tiempo hablado. Las cifras salen de las corridas del registro y de [`IMPACTO.md`](IMPACTO.md),
con la etiqueta «verificado» o «tercero» que allí figura.

Antes de empezar: el deck abierto en la lámina uno y, en otra ventana, la figura de la lámina cuatro. La demo en vivo
(`qrecauda demo`, disponible en 0.2.0) sólo se usa si ya existe en la versión instalada; si no, se enseña la figura y se
corre `uv run qrecauda juzgar E1`, que sí existe.

## Cronometraje por lámina

| t | lámina | qué se dice | qué se enseña |
|---|---|---|---|
| 0:00 a 0:10 | 1 · Problema | «La aleatoriedad clásica se predice. La recaudación del Perú no debería.» Un generador pseudoaleatorio sale de un estado: quien lo reconstruye reproduce las claves siguientes. | La frase de la tesis, sola. |
| 0:10 a 0:22 | 2 · Solución | Una cadena que va de los bits a la clave y mide cada etapa: mitigación, Peres, Toeplitz, validación y cifrado AES-GCM. Siete métricas con umbral escrito antes de correr. | El diagrama de la cadena. |
| 0:22 a 0:32 | 3 · Tecnología | La fuente es un puerto. Hoy es Qiskit Aer con un circuito de un gate; la computadora de IBM entra por el mismo puerto sin tocar el resto. | Las cuatro viñetas, sin leerlas. |
| 0:32 a 1:00 | 4 · Demo | Tres ramas: un PRNG, la fuente de Aer sin mitigar y la fuente de Aer mitigada. A la izquierda, la entrada: la muestra de Aer sin mitigar tiene un sesgo de unos tres centésimos, tres veces el umbral; la mitigación lo deja en cuatro diezmilésimas. A la derecha, la salida: las tres claves pasan. Lo digo yo antes de que lo pregunten: pasar la batería no prueba el origen de los bits. | La figura. Si hay `qrecauda demo`, correrlo aquí y dejar que imprima las tres ramas. |
| 1:00 a 1:18 | 5 · Validación | Cinco experimentos juzgados: E1, E2, E3, E3b y E5; E4, preinscrito, está bloqueado por falta de credencial. E1, E2, E3b y E5 cumplen. E3 no cumplió: la tasa cumple, pero la latencia, de cinco a nueve segundos, estaba lejos de los quinientos milisegundos. Ese resultado está publicado y no se reabre. | La tabla, señalando la fila en negrita y las dos filas nuevas. |
| 1:18 a 1:26 | 6 · Caso de uso | Una transacción de Metro o de peaje consume una clave: con una fuente real no se podría recalcular; hoy, en simulador, sí, porque la semilla es pública. La latencia baja a décimas de milisegundo cuando la clave sale de una reserva generada aparte y ya cebada (E3b), en simulador; una transacción que llega durante el arranque espera unos 6,6 s. | La viñeta de la reserva, con su p95 y el arranque informado aparte. |
| 1:26 a 1:40 | 7 · Impacto | La Línea 1 del Metro de Lima movió 203,9 millones de pasajeros en 2025 (verificado). Ninguna norma que revisamos exige un QRNG; el argumento es de entropía, medida con NIST 800-90B y 90C, no con la batería 800-22. | Las tres cifras con su etiqueta. |
| 1:40 a 1:48 | 8 · Hoja de ruta | Estamos en TRL-3. La latencia ya cerró en simulador; falta una primera corrida real en IBM, hoy bloqueada por una credencial, para llegar a TRL-4; repetir E1 y E2 sobre esa fuente, a TRL-5; luego, piloto con un operador. | La tabla de etapas. |
| 1:48 a 1:52 | 9 · Equipo | Soy kaitokid. El plan y el registro están abiertos. | La lámina, sin leer. |
| 1:52 a 2:00 | 10 · Cierre | Pedimos un backend de IBM Quantum para la primera corrida real, y que quien opere el cobro revise nuestros umbrales. La aleatoriedad clásica se predice. La recaudación del Perú no debería. | La frase de la tesis otra vez. |

Qué no decir: «cuántico» como adjetivo de lo que se midió, «cumple la norma», «listo para producción». Ninguna de las tres
se sostiene con lo que hay.

## Las cinco preguntas más duras

**1. «Aer es pseudoaleatorio. ¿Dónde está lo cuántico?»**
En ningún lado todavía, y lo decimos en la lámina de validación. Aer muestrea con un generador pseudoaleatorio:
con semilla es determinista y no tiene valor de seguridad. Lo que se valida hoy es el postprocesamiento y la medición que
lo juzga, no el origen. El origen cuántico depende de una corrida en hardware IBM, que no existe: la constancia fechada
está en `registro/corridas/HW.json` y el `job_id` es nulo. El camino a IBM está listo y ensayado contra un backend falso
(`qrecauda hardware`, preinscripción P.E4), pero la corrida real espera una credencial: ningún resultado en hardware. Por eso el sistema está en TRL-3 y no más arriba.

**2. «Su pipeline pasa NIST aunque la fuente sea mala.»**
Es cierto y es un hallazgo nuestro (R.00-1). La clave de la rama sin mitigar pasa M1 en las tres semillas, y la del PRNG
también, porque Peres y Toeplitz bastan para aprobar la batería. Por eso NIST SP 800-22 no sirve como prueba de la
fuente, y NIST mismo aclaró en 2022 que no sirve para validar generadores criptográficos. Ahora hay un control negativo
del pipeline completo, E5, con veredicto CUMPLE: tres fuentes con dependencia entre bits (dos Markov y una semiperiódica)
atravesaron la cadena entera, con tres semillas. Medido ahí, R.00-1 se confirma: con el dimensionado de 0.1.0 las nueve
claves defectuosas pasan M1 a M5 y salen entre 1,2 y 2,5 veces más largas que lo que la fuente sostiene (veredicto de E5,
criterio HOY). El dimensionado conservador (el mínimo de MCV y 90B más la contabilidad de la entropía de la fuente) las
acorta: la fuente markov_fuerte pasa de 380 a 381 mil bits a 55 a 56 mil, y la fuente buena conserva de 856 a 883 mil.
Dos límites: `min(MCV, 90B)` por sí solo no alcanza en markov_fuerte, y el conservador es opt-in (por defecto sigue `mcv`).
Además, E3 y E3b no se re-midieron con él, así que ⚠️ sin verificar cómo cambia la latencia. Cubre tres defectos de
dependencia con respuesta analítica; un defecto que imite a una fuente independiente ante los estimadores no se probó. Y hay que decirlo: E5 es casi un control por
construcción. Las fuentes defectuosas se eligieron detectables por el 90B (control D5), el lado «rechazada» nunca se ejerce (las
36 claves pasan M1 a M5; el pipeline acorta la clave, no la rechaza) y los umbrales K2 y G2 se fijaron tras un diagnóstico con el
mismo generador de defectos.

**3. «M7 falla. ¿Qué pasó y qué hacen?»**
En E3 falló en las tres semillas: p95 de 5,5 a 9,4 s contra 500 ms. El veredicto de E3 está en el registro y no se
reabre. La tasa (M6) sí cumple, de 180 a 195 kbit/s contra 10 kbit/s. El rediseño es una reserva de claves que un proceso
productor genera aparte, preinscrita como experimento nuevo (E3b) con sus propios umbrales antes de correr. E3b cumple en
las tres semillas: p95 de 0,17 a 0,18 ms con 12 000 transacciones por semilla, capacidad del productor de 177 a 199 kbit/s (entregado en régimen, 47,8 kbit/s, 1,36 veces el
consumo de 35,2 kbit/s), y cero esperas. No es una corrección de E3: E3 mide generar y cifrar, E3b sólo cifrar con la reserva
cebada, así que las dos latencias no son comparables. Es otro diseño con otro veredicto, y el costo se
trasladó al arranque: de 6,6 a 6,7 s hasta la primera clave en la reserva, que se informa aparte y no decide. Límites: se
midió en simulador, sin la cola ni la red de IBM; las claves se generan con el dimensionado `mcv` de 0.1.0 (que E5 mostró
que sobrestima con fuentes dependientes); y la demanda de 100 transacciones por segundo es declarada por el equipo.
Además, los 500 ms y los 10 kbit/s vienen del manifiesto del equipo, no de un operador; no hay requisito de OSITRAN, del
MTC ni del Metro en el repositorio.

**4. «¿Por qué una mitigación propia y no TREX de IBM?»**
Porque la nuestra opera sobre cadenas de bits y la necesitamos para dimensionar la clave; la medimos sobre ruido modelado y
no sobre ruido real. Es twirling clásico: un XOR con una máscara aleatoria que anula el sesgo global por construcción. Baja
el sesgo de lectura entre 11 y 32 veces sobre ese ruido, pero deja intacto el sesgo local por bloque, que es lo que M4 y M5
detectan en la muestra mitigada. ZNE y PEC no movieron el sesgo de lectura. No hicimos una comparación contra TREX ni contra
`mthree` sobre hardware: ⚠️ sin verificar cuál corrige mejor la lectura real. La comparación entra en el plan junto con la
primera corrida en IBM.

**5. «¿Qué cambia cuando corran en hardware?»**
Cuatro cosas, y ninguna es una garantía. Primero, el ruido real no es simétrico ni estable: puede haber correlación entre
qubits y deriva en el tiempo, y el modelo de ruido propio podría no reproducirlo (⚠️ sin verificar). Segundo, E1 y E2 se
repiten sobre esa fuente con tres semillas y un `job_id`. Tercero, el 90B se corre sobre los bits crudos del dispositivo,
que es la medición que sí informa sobre la fuente. Cuarto, M7 sumará latencia de cola y de red, que hoy no está incluida.
Aun con todo eso no diremos «entropía cuántica certificada»: no hallamos un QRNG certificado de IBM, y los resultados de
aleatoriedad certificada con hardware que conocemos (Quantinuum, Nature 2025, tercero) usan otro protocolo.
