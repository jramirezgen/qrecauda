# GLOSARIO — vocabulario cerrado

Un término, un sentido. Si un nombre se usa con dos sentidos, uno se renombra.

## Entropía

| término | definición |
|---|---|
| `Bits` | secuencia inmutable de 0/1 (`dominio/bits.py`). |
| min-entropía `h_min` | −log₂ de la probabilidad del símbolo más probable, por bit. Aquí: cota MCV al 99 % (NIST SP 800-90B §6.3.1). |
| entropía de entrada | `h_min` del pool **antes** de Toeplitz; decide la longitud segura. |
| entropía de salida (M2) | `h_min` de la clave **después** de Toeplitz; ≈ 1 por construcción, por eso no basta como prueba. |
| sesgo (M1) | \|p(1) − 1/2\|. «Sesgo de lectura < 1 %» significa sesgo < 0,01. |
| LHL | Leftover Hash Lemma: m = ⌊n·h_min − 2·log₂(1/ε)⌋ bits a distancia ≤ ε de uniformes. |
| ε | parámetro de seguridad; por defecto 2⁻⁶⁴. |

## Fuentes

| término | definición |
|---|---|
| `Muestra` | bits crudos + `Origen` + qubits + shots + si fue mitigada. |
| `Origen.PRNG_CLASICO` | determinista dada la semilla; línea base del pitch. |
| `Origen.SIMULADOR_AER` | circuito cuántico simulado; **el muestreo es pseudoaleatorio** y no reclama origen cuántico. |
| `Origen.HARDWARE_IBM` | única fuente que puede reclamar origen cuántico. |
| PUB | tupla (circuito ISA, parámetros, shots) que consume `SamplerV2`. |

## Mitigación

| término | definición |
|---|---|
| lectura (TREX / mthree) | corrección del sesgo de medición. Se aplica sobre bitstrings. ⚠️ la equivalencia TREX = mthree no está verificada (spike S.02). |
| ZNE / PEC | técnicas de valores esperados; aquí actúan sobre ⟨Z⟩, no sobre bitstrings. ⚠️ ídem. |

## Evaluación

| término | definición |
|---|---|
| M1…M7 | las siete métricas de `dominio/metricas.py`; desigualdades estrictas. |
| veredicto | conjunción de las medidas; vacío ⇒ no aprueba. |
| «certificada» | *supera la batería de pruebas y las cotas de entropía de este repositorio*. **No** es una certificación formal (FIPS/ISO) ni prueba de origen cuántico. |
| control negativo | corrida cuyo resultado esperado es «pasa» aunque la fuente sea clásica (E1a); demuestra los límites de la batería. |
| eureka | objetivo cerrado con preinscripción, corridas que descienden de ella y veredicto. |
