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

- Cadena de procesamiento: mitigación de lectura, extractor de Peres, hash de Toeplitz, validación NIST SP 800-22 y SP 800-90B.
- Siete métricas de aceptación (M1 a M7) con umbral fijado antes de correr.
- Tres experimentos preinscritos: E1 (calidad de la clave), E2 (sesgo de lectura) y E3 (tasa y latencia).
- Hardware IBM opcional. Ni la demostración ni el release 0.1.0 dependen de él.

# Lámina 3 · Arquitectura

Arquitectura hexagonal en cuatro macro-capas: dominio puro, aplicación, adaptadores y presentación. Seis contratos de importación impiden que el dominio conozca a Qiskit, a NIST o a la CLI.

- La fuente de bits es un puerto. El simulador es la fuente por defecto y `FuenteIbm` entra por el mismo puerto sin tocar el resto.
- Mitigación, extractores y validación son puertos con adaptador propio. Cambiar de biblioteca no cambia el dominio.
- El plan vive como grafo dirigido acíclico que una herramienta valida. El estado vive en un registro de sólo añadir, no en el chat.

Detalle: `docs/DISENO.md`.

# Lámina 4 · Método

Cada experimento se preinscribe antes de correr, con umbral, criterio y controles.

- Los criterios se fijan en `docs/preinscripciones/` antes de la corrida. Ninguna cifra se mueve después.
- Tres semillas por experimento, sin repetir ni sustituir la que falla.
- Cada experimento lleva un control negativo: un generador clásico también debe pasar la batería (D-007). Pasar NIST no prueba origen cuántico, y el informe lo dice.
- Una cifra sale de una corrida nombrada en `registro/corridas/`. Los marcadores de esta presentación se cruzan con ese registro en un test.

# Lámina 5 · E1: calidad de la clave

Veredicto de E1: CUMPLE en las tres semillas preinscritas.

- Entrada con ruido de lectura medio: sesgo crudo entre 0,0296{{corrida:C.E1b.etapas.cruda.0.1:min}} y 0,0304{{corrida:C.E1b.etapas.cruda.0.1:max}}, sobre el umbral de M1.
- La clave final queda con sesgo de a lo sumo 0,0005{{corrida:C.E1c.etapas.clave.0.1:max}} y mide al menos 956,6{{corrida:C.E1c.bits_clave:min/1000}} mil bits.
- Hallazgo R.00-1: la clave sin mitigar también pasa M1 en 3{{corrida:C.E1b.etapas.clave.0.3:ntrue}} de 3{{corrida:C.E1b.semilla:n}} semillas. Peres y Toeplitz bastan para aprobar la batería. M1 a M5 no demuestran el valor de la mitigación ni el origen.
- Control positivo del estimador 90B: la fuente Markov tiene entropía real de 0,17{{corrida:C.E1d[fuente=markov].h_90b:max}} bit por bit y el estimador MCV le da al menos 0,99{{corrida:C.E1d[fuente=markov].mcv:min}}. El 90B la rechaza y el MCV la acepta.

# Lámina 6 · E2: sesgo de lectura

Veredicto de E2: CUMPLE en las tres semillas y en todos los niveles de ruido sintético.

- Sin mitigar, el nivel medio deja un sesgo de 0,030{{corrida:C.E2[nivel=medio,tecnica=ninguna].sesgo_crudo:max}}. El umbral de M1 es 0,01{{ref:docs/preinscripciones/E2.md}}.
- El twirling propio (XOR clásico) deja un residuo entre 0,0004{{corrida:C.E2[tecnica=twirling_propio].sesgo_residual:min}} y 0,0013{{corrida:C.E2[tecnica=twirling_propio].sesgo_residual:max}} en todos los niveles.
- ZNE y PEC no corrigen el ruido de lectura: en el nivel medio el residuo queda entre 0,030{{corrida:C.E2[nivel=medio,tecnica=zne].sesgo_residual:min}} y 0,032{{corrida:C.E2[nivel=medio,tecnica=zne].sesgo_residual:max}}. Se definen sobre valores esperados, no sobre bitstrings.
- El nivel realista no pone a prueba la mitigación: su sesgo crudo ya queda bajo el umbral.

# Lámina 7 · E3: tasa y latencia

Veredicto de E3: NO CUMPLE, por M7. Es un resultado, no una avería.

- M6 (tasa sostenida) cumple: entre 180{{corrida:C.E3.m6_bits_por_s:min/1000}} y 195{{corrida:C.E3.m6_bits_por_s:max/1000}} kbit/s, frente a un umbral de 10 000{{ref:docs/preinscripciones/E3.md}} bit/s.
- M7 (latencia, p95) falla en las 3{{corrida:C.E3.semilla:n}} semillas: entre 5,5{{corrida:C.E3.m7_p95_ms:min/1000}} y 9,4{{corrida:C.E3.m7_p95_ms:max/1000}} s, frente a un umbral de 500{{ref:docs/preinscripciones/E3.md}} ms.
- Perfil B, que no decide: con reserva de claves, el ciclo de cifrado va de 30,7{{corrida:C.E3.reporte.perfil_b.tx_por_s:min/1000}} a 63,6{{corrida:C.E3.reporte.perfil_b.tx_por_s:max/1000}} mil transacciones por segundo. Es un diseño a validar con una preinscripción nueva, no un cierre de M7.

# Lámina 8 · Límites

Lo que esta demostración valida es la validación del pipeline: la cadena de procesamiento y la medición que la juzga.

- Sin hardware IBM. Hay una constancia fechada de no acceso (`registro/corridas/HW.json`, D-010) y ningún `job_id`.
- El origen cuántico no se afirma. El simulador no lo aporta y una batería estadística no lo distingue de un generador clásico.
- El modelo de ruido es propio. ⚠️ Sin verificar que reproduzca el ruido físico de un backend real.
- TRL del sistema 3{{trl:sistema}}, derivado de la evidencia en `docs/TRL.md`. Lo fijan dos filas: la latencia (M7) y la fuente real. El rótulo de TRL más alto que trae el manifiesto no se hereda.
- No hay requisito de OSITRAN, del MTC ni del Metro en el repositorio. ⚠️ Sin verificar los umbrales de 10 000{{ref:docs/preinscripciones/E3.md}} bit/s y 500{{ref:docs/preinscripciones/E3.md}} ms frente a la operación real.

# Lámina 9 · Hoja de ruta

El plan completo está en `docs/ROADMAP.md`. Lo que sube el TRL del sistema:

- Cerrar M7 con un diseño preinscrito de nuevo, por ejemplo la reserva de claves como arquitectura y no como perfil B, con tres semillas y un veredicto que CUMPLA.
- Una corrida real con la fuente `ibm` y un token pasado por ruta, que produzca `HW.json` con `job_id`, backend y versión del SDK.
- Contrastar el modelo de ruido con el de un backend real y repetir E1 y E2 sobre esa fuente.

Cada paso entra al plan como nodo nuevo, con preinscripción anterior a la corrida.

# Lámina 10 · Pedido y cierre

Qué pedimos:

- Acceso a un backend de IBM Quantum para producir la primera corrida real, con la credencial entregada por ruta.
- Revisión de los umbrales de tasa y latencia por quien opere el cobro, porque hoy vienen del manifiesto del equipo.

Qué se lleva el jurado:

- Un pipeline que corre de punta a punta en una PC, con el repositorio, el plan y los registros abiertos.
- Dos experimentos que cumplen, uno que no cumple y las razones medidas.
- Una regla de trabajo: lo que no tiene corrida detrás no se afirma.
