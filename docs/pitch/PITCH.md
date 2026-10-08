---
title: "QRecauda: claves para la recaudación peruana, con cada cifra atada a una corrida"
author: kaitokid
date: "2026-10-08"
lang: es
serie: "Pitch · Hackatón Qiskit IBM Lima · Track 4"
---

<!--
Cada cifra de resultado lleva un marcador pegado a su derecha. El test
tests/arquitectura/test_cifras_del_pitch.py lo resuelve contra registro/corridas/ y falla si la
corrida o el campo no existen, si la cifra no coincide o si queda una cifra sin marcador.
Gramática y reglas de resolución: cabecera de ese test.
-->

# Lámina 1 · Problema

Los peajes y el Metro de Lima cobran millones de transacciones pequeñas al día. Cada una se firma y se cifra con claves y *nonces* que salen de un generador.

- Un generador pseudoaleatorio calcula su salida desde un estado interno. Quien reconstruye ese estado reproduce las claves futuras.
- La tesis del equipo: la aleatoriedad clásica se predice, y la recaudación del Perú no debería depender de ella.
- Un simulador no resuelve el problema por sí solo. Aer muestrea con un generador pseudoaleatorio, así que sus bits no son cuánticos.

Esta presentación muestra qué se construyó, qué se midió y qué no se puede afirmar todavía.

# Lámina 2 · Propuesta

Un pipeline reproducible que convierte los bits de un circuito de un solo gate (Hadamard sobre ocho qubits) en una clave AES-256-GCM para cifrar una transacción de peaje o de Metro.

- Cadena de procesamiento: mitigación de lectura, extractor de Peres, hash de Toeplitz y validación con tres pruebas de NIST SP 800-22 (monobit, rachas y frecuencia por bloques, de las quince de la batería). La estimación SP 800-90B es informativa: no valida la clave.
- Siete métricas de aceptación (M1 a M7) con umbral fijado antes de correr.
- Cinco experimentos juzgados, cada uno con preinscripción anterior a la corrida: E1 (calidad de la clave), E2 (sesgo de lectura), E3 (tasa y latencia), E3b (latencia con la clave de una reserva generada aparte) y E5 (control negativo del pipeline completo). E4 (hardware IBM), preinscrito, está bloqueado por falta de credencial y no tiene veredicto.
- Hardware IBM opcional. Ni la demostración ni el release 0.1.0 dependen de él. El camino a IBM está listo y ensayado contra un backend falso (`qrecauda hardware`, `docs/HARDWARE.md`, preinscripción P.E4), pero la corrida real está bloqueada por falta de credencial: no hay ningún resultado en hardware.

# Lámina 3 · Arquitectura

Arquitectura hexagonal en cuatro macro-capas: datos, lógica, integración y transversales. Siete contratos de importación impiden que el dominio conozca a Qiskit, a NIST o a la CLI.

- La fuente de bits es un puerto. El simulador es la fuente por defecto y `FuenteIbm` entra por el mismo puerto sin tocar el resto.
- Mitigación, extractores y validación son puertos con adaptador propio. Cambiar de biblioteca no cambia el dominio.
- El plan vive como grafo dirigido acíclico que una herramienta valida. El estado vive en un registro de sólo añadir, no en el chat.

Detalle: `docs/DISENO.md`.

# Lámina 4 · Método

Cada experimento se preinscribe antes de correr, con umbral, criterio y controles.

- Los criterios se fijan en `docs/preinscripciones/` antes de la corrida registrada. Hubo enmiendas fechadas, y el informe las lista: dos pasaron M4 y M5 de la muestra mitigada de E1 a informativas, una recalibró el piso del control P1 sobre las mismas semillas, y tres de E3 se hicieron el mismo día de la corrida, tras un primer intento real sin cifras conservadas. Ninguna cambió un umbral de las siete métricas.
- Tres semillas por experimento, sin sustituir la que falla. Son identificadores de un generador determinista, no réplicas físicas.
- E1 lleva un control negativo del instrumento (D-007): un generador clásico también debe pasar la batería, y eso muestra que pasar NIST no prueba origen cuántico. El control negativo del pipeline completo llegó después, con E5 (lámina de E1 y E5).
- Una cifra sale de una corrida nombrada en `registro/corridas/`. Los marcadores de esta presentación se cruzan con ese registro en un test.

# Lámina 5 · E1 y E5: calidad de la clave y control negativo

Veredicto de E1: CUMPLE en las tres semillas preinscritas, condicionado a dos enmiendas. M4 y M5 de la muestra mitigada fallan en las tres semillas, con p de a lo sumo 0,002{{corrida:C.E1c.etapas.mitigada.3.1:max}}, y se declararon informativas antes de la corrida registrada. Sin esas enmiendas, E1 sería CUMPLE PARCIAL.

- Entrada con ruido de lectura medio: sesgo crudo entre 0,0296{{corrida:C.E1b.etapas.cruda.0.1:min}} y 0,0304{{corrida:C.E1b.etapas.cruda.0.1:max}}, sobre el umbral de M1.
- La clave final queda con sesgo de a lo sumo 0,0005{{corrida:C.E1c.etapas.clave.0.1:max}} y mide al menos 956,6{{corrida:C.E1c.bits_clave:min/1000}} mil bits.
- Hallazgo R.00-1: la clave sin mitigar también pasa M1 en 3{{corrida:C.E1b.etapas.clave.0.3:ntrue}} de 3{{corrida:C.E1b.semilla:n}} semillas. Peres y Toeplitz bastan para aprobar la batería. M1 a M5 no demuestran el valor de la mitigación ni el origen.
- Control del estimador 90B: la fuente Markov tiene una min-entropía real de 0,322{{ref:docs/preinscripciones/E1.md}} bit por bit. El estimador 90B le da a lo sumo 0,17{{corrida:C.E1d[fuente=markov].h_90b:max}} y el MCV al menos 0,99{{corrida:C.E1d[fuente=markov].mcv:min}}: el 90B la rechaza y el MCV la acepta. El piso de ese control se calibró con las mismas semillas, así que es una prueba de regresión y no un control con poder.
- El 90B de la entrada real queda por debajo de 0,9{{ref:docs/preinscripciones/E1.md}} y no decide la longitud de la clave. En 0.1.0 esa longitud usa MCV, que no ve dependencia.

Veredicto de E5: CUMPLE. Es el control negativo del pipeline completo: tres fuentes con dependencia entre bits (Markov de dos persistencias y una semiperiódica) y la fuente buena atraviesan mitigación, Peres, Toeplitz, validación y 90B, con tres semillas y tres dimensionados.

- Hallazgo R.00-1 medido en cadena completa: con el dimensionado de 0.1.0 (`mcv`), las claves de las nueve corridas con fuentes dependientes pasan M1 a M5 y salen más largas que lo que la fuente sostiene. Pasar la batería no detecta la dependencia.
- El dimensionado conservador (mínimo de MCV y 90B más la contabilidad de la entropía de la fuente) las acorta. La fuente markov_fuerte entrega de 380{{corrida:C.E5[fuente=markov_fuerte].resultados.0.bits_clave:min/1000}} a 381{{corrida:C.E5[fuente=markov_fuerte].resultados.0.bits_clave:max/1000}} mil bits con `mcv` y de 55{{corrida:C.E5[fuente=markov_fuerte].resultados.2.bits_clave:min/1000}} a 56{{corrida:C.E5[fuente=markov_fuerte].resultados.2.bits_clave:max/1000}} mil con el conservador.
- Usar `min(MCV, 90B)` por sí solo no alcanza en markov_fuerte: la clave sigue por encima de lo que la fuente sostiene (criterio HOY del veredicto de E5). Por eso el conservador suma la contabilidad de la fuente.
- La fuente buena no paga demasiado: conserva de 856{{corrida:C.E5[fuente=buena].resultados.2.bits_clave:min/1000}} a 883{{corrida:C.E5[fuente=buena].resultados.2.bits_clave:max/1000}} mil bits de clave, y la cadena entera sostiene de 133{{corrida:C.E5[fuente=buena].resultados.2.tasa_bps:min/1000}} a 158{{corrida:C.E5[fuente=buena].resultados.2.tasa_bps:max/1000}} kbit/s.
- E5 es casi un control por construcción. Las fuentes defectuosas se eligieron detectables por el 90B (control D5). El lado «rechazada» nunca se ejerce: las claves pasan M1 a M5, y el pipeline acorta la clave, no la rechaza. Los umbrales K2 y G2 se fijaron tras un diagnóstico con el mismo generador de defectos.
- El dimensionado conservador es opt-in: por defecto el pipeline sigue con `mcv`. No se re-midieron E3 ni E3b con él. ⚠️ Sin verificar su efecto sobre la latencia.

# Lámina 6 · E2: sesgo de lectura

Veredicto de E2: CUMPLE en las tres semillas y en todos los niveles de ruido sintético. Es una propiedad algebraica: el XOR con una máscara aleatoria anula el sesgo global por construcción.

- Sin mitigar, el nivel medio deja un sesgo de 0,030{{corrida:C.E2[nivel=medio,tecnica=ninguna].sesgo_crudo:max}}. El umbral de M1 es 0,01{{ref:docs/preinscripciones/E2.md}}.
- El twirling propio (XOR clásico) deja un residuo agregado entre 0,0007{{corrida:C.E2[nivel=bajo,tecnica=twirling_propio].sesgo_residual:min}} y 0,0013{{corrida:C.E2[nivel=alto,tecnica=twirling_propio].sesgo_residual:max}} en los niveles sintéticos. El agregado no mide el sesgo local por bloque, que sigue ahí y es lo que detectan M4 y M5 en E1.
- ZNE y PEC no corrigen el ruido de lectura: en el nivel medio el residuo queda entre 0,030{{corrida:C.E2[nivel=medio,tecnica=zne].sesgo_residual:min}} y 0,032{{corrida:C.E2[nivel=medio,tecnica=zne].sesgo_residual:max}}. Se definen sobre valores esperados, no sobre bitstrings.
- El nivel realista no pone a prueba la mitigación: el modelo de ruido del backend falso simetriza la lectura y su sesgo crudo ya queda bajo el umbral. Eso describe al modelo, no a los dispositivos reales.

# Lámina 7 · E3 y E3b: tasa y latencia

Veredicto de E3 (0.1.0): NO CUMPLE, por M7. Es un resultado, no una avería, y sigue en el registro sin reabrirse.

- M6 (tasa sostenida) cumple: entre 180{{corrida:C.E3.m6_bits_por_s:min/1000}} y 195{{corrida:C.E3.m6_bits_por_s:max/1000}} kbit/s, frente a un umbral de 10 000{{ref:docs/preinscripciones/E3.md}} bit/s.
- M7 (latencia, p95) falla en las 3{{corrida:C.E3.semilla:n}} semillas: entre 5,5{{corrida:C.E3.m7_p95_ms:min/1000}} y 9,4{{corrida:C.E3.m7_p95_ms:max/1000}} s, frente a un umbral de 500{{ref:docs/preinscripciones/E3.md}} ms. Esa clave se generaba dentro de la transacción.
- El perfil B de E3 (reserva ya cargada) no decidió nada. El diseño con reserva se preinscribió aparte como E3b, con umbrales propios fijados antes de correr. Es otro diseño con otro veredicto, no una corrección de E3.

Veredicto de E3b: CUMPLE en las 3{{corrida:C.E3b.semilla:n}} semillas. Un proceso productor genera las claves en paralelo y la transacción sólo consume la de la reserva.

- M7 (latencia, p95), con la reserva cebada: entre 0,17{{corrida:C.E3b.p95_ms:min}} y 0,18{{corrida:C.E3b.p95_ms:max}} ms sobre 12 000{{corrida:C.E3b.transacciones:min}} transacciones por semilla, frente a un umbral de 500{{ref:docs/preinscripciones/E3b.md}} ms. No es comparable con el p95 de E3: E3 mide generar y cifrar la clave dentro de la transacción; E3b mide sólo cifrar con una clave ya generada. Una transacción que llegue durante el arranque espera unos 6,6{{corrida:C.E3b.arranque_ms:min/1000}} s, y eso incumpliría M7.
- Sostenibilidad: capacidad del productor de 177{{corrida:C.E3b.tasa_neta_bps:min/1000}} a 199{{corrida:C.E3b.tasa_neta_bps:max/1000}} kbit/s; lo entregado en régimen es 47,8{{corrida:C.E3b.reporte.tasa_entregada_ventana_bps:min/1000}} kbit/s. Se compara con un umbral de 10 000{{ref:docs/preinscripciones/E3b.md}} bit/s y con un consumo declarado de 35,2{{ref:docs/preinscripciones/E3b.md}} kbit/s, con una demanda de 100{{ref:docs/preinscripciones/E3b.md}} transacciones por segundo declarada por el equipo.
- T2 (M7) era casi trivial por la baja utilización del consumidor; el riesgo del experimento estaba en T1 y T3. Sin esperas: 0{{corrida:C.E3b.esperas:max}} esperas por reserva vacía en las tres semillas, y la reserva no se agotó.
- El costo se trasladó al arranque, que se informa aparte y no decide: de 6,6{{corrida:C.E3b.arranque_ms:min/1000}} a 6,7{{corrida:C.E3b.arranque_ms:max/1000}} s hasta tener la primera clave en la reserva.
- Limitación: las claves de E3b se generan con el dimensionado `mcv` de 0.1.0, el que E5 mostró que sobrestima con fuentes dependientes. No se re-midió E3b con el dimensionado conservador. ⚠️ Sin verificar el efecto de ese cambio sobre la latencia. La medición es en simulador, sin cola ni red de IBM.

# Lámina 8 · Límites

Lo que esta demostración valida es la validación del pipeline: la cadena de procesamiento y la medición que la juzga.

- Sin hardware IBM. Hay una constancia fechada de no acceso (`registro/corridas/HW.json`, D-010) y ningún `job_id`. El camino está listo y ensayado contra un backend falso (`qrecauda hardware`, P.E4), pero C.E4 espera una credencial: no hay ningún resultado en hardware real.
- El origen cuántico no se afirma. El simulador no lo aporta y una batería estadística no lo distingue de un generador clásico.
- El control negativo del pipeline completo (E5) cubre tres defectos de dependencia con respuesta analítica conocida. Un defecto que imite a una fuente independiente ante los estimadores no se probó. El dimensionado conservador es opt-in y no se re-midió E3b con él.
- Tres semillas de un generador pseudoaleatorio no son réplicas físicas, y la batería tiene unos treinta valores p decisivos sin corrección por comparaciones múltiples.
- Una revisión adversarial independiente (tres informes, notas de seis, seis y cinco y medio sobre diez) encontró un fallo bloqueante de reutilización de nonce, ya corregido, y las limitaciones que esta presentación declara.
- El modelo de ruido es propio. ⚠️ Sin verificar que reproduzca el ruido físico de un backend real.
- TRL del sistema 3{{trl:sistema}}, derivado de la evidencia en `docs/TRL.md`. La latencia con reserva (E3b) sube de nivel como componente, sobre simulador y con protocolo preinscrito; el sistema lo sigue fijando la fuente real, sin hardware. El rótulo de TRL más alto que trae el manifiesto no se hereda.
- No hay requisito de OSITRAN, del MTC ni del Metro en el repositorio. ⚠️ Sin verificar los umbrales de 10 000{{ref:docs/preinscripciones/E3.md}} bit/s y 500{{ref:docs/preinscripciones/E3.md}} ms frente a la operación real.

# Lámina 9 · Hoja de ruta

El plan completo está en `docs/ROADMAP.md`. Lo que sube el TRL del sistema:

- Una corrida real con la fuente `ibm` y un token pasado por ruta (C.E4, con la preinscripción P.E4 ya escrita), que produzca `HW.json` con `job_id`, backend y versión del SDK. Hoy está bloqueada por falta de credencial.
- Contrastar el modelo de ruido con el de un backend real y repetir E1 y E2 sobre esa fuente.
- Medir la latencia con la cola y la red de IBM dentro: E3b cerró M7 sólo en simulador.
- Re-medir E3b con el dimensionado conservador de E5 y decidir en el release si pasa a ser el predeterminado.

Cada paso entra al plan como nodo nuevo, con preinscripción anterior a la corrida.

# Lámina 10 · Pedido y cierre

Qué pedimos:

- Acceso a un backend de IBM Quantum para producir la primera corrida real, con la credencial entregada por ruta.
- Revisión de los umbrales de tasa y latencia por quien opere el cobro, porque hoy vienen del manifiesto del equipo.

Qué se lleva el jurado:

- Un pipeline que corre de punta a punta en una PC, con el repositorio, el plan y los registros abiertos.
- Cuatro experimentos que cumplen y uno que no. E1 y E2 con poder limitado para fallar (E1 condicionado a dos enmiendas); E3b con T2 casi trivial por la baja utilización (el riesgo estaba en T1 y T3) y E5 casi por construcción (fuentes detectables por el 90B, lado «rechazada» no ejercido). E3 no cumple y las razones están medidas.
- Una regla de trabajo: lo que no tiene corrida detrás no se afirma.
