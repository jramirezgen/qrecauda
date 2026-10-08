---
title: "QRecauda"
subtitle: "La aleatoriedad clásica se predice. La recaudación del Perú no debería."
author: kaitokid
date: "2026-10-08"
lang: es
serie: "Deck · Hackatón Qiskit IBM Lima · Track 4"
---

<!--
Deck de diez láminas, una idea por lámina. Se construye con docs/pitch/construir.sh (pandoc, beamer, xelatex).
Cada cifra de resultado lleva un marcador de llaves dobles (corrida, ref o trl) pegado a su derecha, con la misma
gramática que PITCH.md (cabecera de tests/arquitectura/test_cifras_del_pitch.py). Las cifras de contexto (Metro, peajes)
se atan con un ref a docs/pitch/IMPACTO.md, donde figuran con su fuente y su etiqueta. El script de construcción quita
los marcadores de la copia que compila. La figura de la lámina 4 sale de presentacion/figura_demo.py.
-->

# Lámina 1 · Problema

**Una clave que se puede recalcular no protege un cobro.**

- Peajes y Metro cobran millones de transacciones pequeñas.
- Cada una se cifra con una clave y un *nonce* que salen de un generador.
- Un generador pseudoaleatorio calcula su salida desde un estado. Quien lo reconstruye reproduce las claves siguientes.

# Lámina 2 · Solución

**Una cadena que mide cada etapa, de los bits a la clave.**

```
Fuente de bits -> Mitigación -> Peres -> Toeplitz -> Validación -> Clave -> AES-GCM
```

- La fuente es un circuito cuántico: hoy en simulador, mañana en una computadora de IBM.
- Siete métricas de aceptación (M1 a M7), con umbral escrito antes de correr.
- Toda cifra sale de una corrida con nombre.

# Lámina 3 · Tecnología

**La fuente es un puerto: cambiarla no toca el resto.**

- Qiskit: un solo gate (Hadamard) sobre ocho qubits. Aer simula; IBM Runtime entra por el mismo puerto.
- Mitigación propia de lectura (*twirling*), extractor de Peres y hash de Toeplitz.
- Validación con NIST SP 800-22 y estimación SP 800-90B; cifrado AES-256-GCM.
- Arquitectura hexagonal con contratos de importación que protegen el dominio.

# Lámina 4 · Demo: PRNG, sin mitigar, mitigado

**La mitigación limpia la entrada. La clave pasa en las tres ramas.**

![Sesgo de la muestra y de la clave en las tres ramas](fig/demo_tres_ramas.pdf){.fig}

- Sesgo de la muestra: PRNG a lo sumo 0,0002{{corrida:C.E1a.etapas.cruda.0.1:max}}; Aer sin mitigar entre 0,0296{{corrida:C.E1b.etapas.cruda.0.1:min}} y 0,0304{{corrida:C.E1b.etapas.cruda.0.1:max}} (umbral 0,01{{ref:docs/preinscripciones/E1.md}}); Aer mitigado a lo sumo 0,0004{{corrida:C.E1c.etapas.mitigada.0.1:max}}.
- Aun sin mitigar, la clave pasa M1 en 3{{corrida:C.E1b.etapas.clave.0.3:ntrue}} de 3{{corrida:C.E1b.semilla:n}} semillas: pasar la batería no prueba el origen.

# Lámina 5 · Validación

**Cinco juzgados, un NO CUMPLE publicado.** E4, preinscrito, bloqueado: sin credencial.

| experimento | veredicto | qué dice |
|-----|-----|-------------|
| E1, calidad | CUMPLE, condicionado | la clave mide al menos 956,6{{corrida:C.E1c.bits_clave:min/1000}} mil bits; condicionado a dos enmiendas |
| E2, sesgo | CUMPLE | el twirling baja el sesgo de 0,030{{corrida:C.E2[nivel=medio,tecnica=ninguna].sesgo_crudo:max}} a casi cero |
| E3, latencia | **NO CUMPLE** | M6 cumple (de 180{{corrida:C.E3.m6_bits_por_s:min/1000}} a 195{{corrida:C.E3.m6_bits_por_s:max/1000}} kbit/s); M7 falla (de 5,5{{corrida:C.E3.m7_p95_ms:min/1000}} a 9,4{{corrida:C.E3.m7_p95_ms:max/1000}} s frente a 500{{ref:docs/preinscripciones/E3.md}} ms) |
| E3b, reserva de claves | CUMPLE | no comparable con E3: M7 de 0,17{{corrida:C.E3b.p95_ms:min}} a 0,18{{corrida:C.E3b.p95_ms:max}} ms (reserva cebada); capacidad 177{{corrida:C.E3b.tasa_neta_bps:min/1000}} a 199{{corrida:C.E3b.tasa_neta_bps:max/1000}}, entregado 47,8{{corrida:C.E3b.reporte.tasa_entregada_ventana_bps:min/1000}} kbit/s |
| E5, control negativo | CUMPLE (casi por construcción) | `mcv` deja pasar hasta 381{{corrida:C.E5[fuente=markov_fuerte].resultados.0.bits_clave:max/1000}} mil bits; el conservador, 56{{corrida:C.E5[fuente=markov_fuerte].resultados.2.bits_clave:max/1000}} mil. Fuentes detectables por el 90B |

- Validación del pipeline: sin hardware IBM no se afirma origen cuántico.

# Lámina 6 · Caso de uso

**Una transacción, una clave. Con una fuente real no se podría recalcular; hoy, en simulador, sí (la semilla es pública).**

- Un pasaje en el Metro o un cobro de peaje es una transacción pequeña que se firma y se cifra.
- La clave AES-256-GCM sale de la cadena medida; el *nonce* no se repite.
- El cuello de botella medido era la latencia (M7). El rediseño genera las claves aparte, en un proceso productor, y la transacción consume una ya lista (experimento E3b, versión 0.2.0 en preparación): p95 de 0,17{{corrida:C.E3b.p95_ms:min}} a 0,18{{corrida:C.E3b.p95_ms:max}} ms en simulador, con la reserva cebada; una transacción durante el arranque espera unos 6,6{{corrida:C.E3b.arranque_ms:min/1000}} s (el arranque llega a 6,7{{corrida:C.E3b.arranque_ms:max/1000}} s), y eso incumpliría M7. No es comparable con E3, que mide generar y cifrar.
- Las claves de E3b usan el dimensionado `mcv` de 0.1.0. Sin verificar (no medido) el efecto del dimensionado conservador de E5 sobre la latencia.

# Lámina 7 · Impacto

**El volumen es real. La exigencia legal de un QRNG, no.**

- Metro de Lima, L1: 203,9{{ref:docs/pitch/IMPACTO.md}} millones de pasajeros en 2025{{ref:docs/pitch/IMPACTO.md}}, récord (verificado). Más de 600 000{{ref:docs/pitch/IMPACTO.md}} usuarios por día (tercero).
- Peajes: 24,6{{ref:docs/pitch/IMPACTO.md}} millones de vehículos en el primer cuatrimestre de 2021{{ref:docs/pitch/IMPACTO.md}}, único dato nacional hallado (tercero, desactualizado).
- Ninguna norma revisada exige un QRNG. El argumento es de ingeniería: la entropía de la fuente se mide con NIST SP 800-90B y 800-90C, no con SP 800-22, que NIST declaró en 2022{{ref:docs/pitch/IMPACTO.md}} inadecuada para validar generadores criptográficos.

Fuentes y etiquetas: `docs/pitch/IMPACTO.md`.

# Lámina 8 · Hoja de ruta

**De TRL-3 a un piloto, con un paso medible por vez.**

| etapa | qué la cierra |
|----|-----------|
| Hoy: TRL-3{{trl:sistema}} | simulador; M7 cumple con reserva (E3b); sin hardware |
| TRL-4 | una primera corrida real en IBM con `job_id` (C.E4, preinscrita, bloqueada por credencial); M7 con cola y red de IBM |
| TRL-5 | E1 y E2 repetidos sobre la fuente real, con el modelo de ruido contrastado |
| Piloto | umbrales validados con quien opere el cobro |
| Producción | custodia de claves (KMS o HSM) y certificación de la fuente |

Detalle: `docs/ROADMAP.md`.

# Lámina 9 · Equipo

**kaitokid, autor del repositorio, con el plan y el registro abiertos.**

<!-- completar con los demás integrantes del equipo, si los hay -->

- Alias: kaitokid. Licencia Apache-2.0.
- Plan como grafo verificable; estado en un registro de sólo añadir, no en el chat.
- Regla de trabajo: lo que no tiene una corrida detrás no se afirma.

# Lámina 10 · Cierre

**La aleatoriedad clásica se predice. La recaudación del Perú no debería.**

- Se lleva el jurado: un pipeline que corre de punta a punta en una PC, con control negativo del pipeline completo y razones medidas de lo que aún no cumple.
- Pedimos acceso a un backend de IBM Quantum para la primera corrida real, con la credencial entregada por ruta.
- Pedimos que quien opere el cobro revise los umbrales de tasa y latencia, que hoy vienen del manifiesto del equipo.
