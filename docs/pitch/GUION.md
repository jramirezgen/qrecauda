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
| 1:00 a 1:18 | 5 · Validación | Tres experimentos preinscritos. E1 y E2 cumplen. E3 no cumple: la tasa cumple, pero la latencia, de cinco a nueve segundos, está lejos de los quinientos milisegundos. Ese resultado está publicado y no se reabre. | La tabla, señalando la fila en negrita. |
| 1:18 a 1:26 | 6 · Caso de uso | Una transacción de Metro o de peaje consume una clave que nadie puede recalcular. Para la latencia, el rediseño en estudio genera las claves antes de usarlas. | Nada nuevo: la viñeta de la reserva. |
| 1:26 a 1:40 | 7 · Impacto | La Línea 1 del Metro de Lima movió 203,9 millones de pasajeros en 2025 (verificado). Ninguna norma que revisamos exige un QRNG; el argumento es de entropía, medida con NIST 800-90B y 90C, no con la batería 800-22. | Las tres cifras con su etiqueta. |
| 1:40 a 1:48 | 8 · Hoja de ruta | Estamos en TRL-3. Cerrar la latencia y hacer una primera corrida real en IBM nos lleva a TRL-4; repetir E1 y E2 sobre esa fuente, a TRL-5; luego, piloto con un operador. | La tabla de etapas. |
| 1:48 a 1:52 | 9 · Equipo | Soy kaitokid. El plan y el registro están abiertos. | La lámina, sin leer. |
| 1:52 a 2:00 | 10 · Cierre | Pedimos un backend de IBM Quantum para la primera corrida real, y que quien opere el cobro revise nuestros umbrales. La aleatoriedad clásica se predice. La recaudación del Perú no debería. | La frase de la tesis otra vez. |

Qué no decir: «cuántico» como adjetivo de lo que se midió, «cumple la norma», «listo para producción». Ninguna de las tres
se sostiene con lo que hay.

## Las cinco preguntas más duras

**1. «Aer es pseudoaleatorio. ¿Dónde está lo cuántico?»**
En ningún lado todavía, y lo decimos en la lámina de validación. Aer muestrea con un generador pseudoaleatorio:
con semilla es determinista y no tiene valor de seguridad. Lo que se valida hoy es el postprocesamiento y la medición que
lo juzga, no el origen. El origen cuántico depende de una corrida en hardware IBM, que no existe: la constancia fechada
está en `registro/corridas/HW.json` y el `job_id` es nulo. Por eso el sistema está en TRL-3 y no más arriba.

**2. «Su pipeline pasa NIST aunque la fuente sea mala.»**
Es cierto y es un hallazgo nuestro (R.00-1). La clave de la rama sin mitigar pasa M1 en las tres semillas, y la del PRNG
también, porque Peres y Toeplitz bastan para aprobar la batería. Por eso NIST SP 800-22 no sirve como prueba de la
fuente, y NIST mismo aclaró en 2022 que no sirve para validar generadores criptográficos. El argumento de entropía se
apoya en SP 800-90B sobre la fuente cruda y en 90C para componer fuentes. Tenemos un control: una fuente Markov que el 90B
rechaza (a lo sumo 0,17 bit por bit) y que el MCV acepta (al menos 0,99). Dos límites: el piso de ese control se calibró
con las mismas semillas, así que es una prueba de regresión y no un control con poder; y la longitud de la clave usa MCV,
que no ve dependencia, y sobrestimó una clave Markov unas tres veces. La mitigación pendiente es dimensionar con el
mínimo de MCV y 90B.

**3. «M7 falla. ¿Qué pasó y qué hacen?»**
Falló en las tres semillas: p95 de 5,5 a 9,4 s contra 500 ms. El veredicto de E3 está en el registro y no se reabre. La
tasa (M6) sí cumple, de 180 a 195 kbit/s contra 10 kbit/s. El rediseño es una reserva de claves generadas de antemano,
preinscrita como experimento nuevo (E3b) con sus propios umbrales antes de correr. Hoy no hay resultado de E3b que citar:
la corrida está en curso y el perfil B de E3, que mostró de 30 a 64 mil transacciones por segundo, no decide nada. Además,
los 500 ms y los 10 kbit/s vienen del manifiesto del equipo, no de un operador; no hay requisito de OSITRAN, del MTC ni del
Metro en el repositorio.

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
