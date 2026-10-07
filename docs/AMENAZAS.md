# Modelo de amenazas de QRecauda

Qué protege un QRNG y qué no. Lo marcado ⚠️ sin verificar es hipótesis (FUNDAMENTO, «Discrepancias declaradas»).

## Qué se protege
Que la clave AES-256 de una transacción no sea predecible por un atacante que no ve la fuente: sesgo de lectura y
correlaciones se tratan con mitigación, Peres y Toeplitz (LHL), y la longitud de la clave sale de la min-entropía
estimada a la entrada del extractor, no de la salida.

## Ataques que SÍ cubre el diseño
| ataque | cómo se mitiga | dónde |
|---|---|---|
| Sesgo del dispositivo (lectura asimétrica) | mitigación de lectura + extractor; sesgo residual medido (M1) | F4.01, F1.02 |
| Correlación entre bits | estimador 90B no-IID, que decide la longitud segura | F5.02 |
| Reutilización de (clave, nonce) en GCM | `ReservaDeClave` consume trozos disjuntos; repetir falla | F6.01 |
| Manipulación del texto cifrado | AES-GCM autentica; `AutenticacionFallida` | F6.01 |
| Agotamiento de entropía | `EntropiaInsuficiente`: aborta, no degrada | F6.01, F1.03 |
| Secretos en el repo | por ruta, nunca por valor; trinquete antisecretos | transversales |

## Lo que NO cubre
- **El canal**: cómo viaja la clave o el texto cifrado entre peaje, Metro y servidor (TLS, red). Fuera de alcance.
- **La implementación**: canales laterales del host, memoria, volcados, dependencias comprometidas.
- **El HSM / gestión de claves**: no hay KMS, rotación ni custodia (FUNDAMENTO, «No incluye»).
- **El hardware cuántico real**: sin pruebas de Bell o autoverificación, el origen cuántico de los bits no se certifica.
  El simulador (Aer) es pseudoaleatorio: no aporta entropía cuántica, sólo prueba el postprocesamiento.
- **Un adversario con acceso al pool** de semillas de Toeplitz (D-004: sale del mismo pool; independencia entre bloques
  es hipótesis del modelo de ruido, ⚠️ sin verificar).
- **Latencia de cola y red de IBM Quantum**: no incluida en M7.

## Qué certifica y qué no certifica NIST
- SP 800-22 es una batería de **pruebas estadísticas**: un PRNG las pasa. No certifica origen ni impredecibilidad
  (D-007; el control negativo de E1 lo demuestra).
- SP 800-90B estima min-entropía de una fuente no-IID con muestras ≥ 1 000 000 bits; es una cota empírica, no una
  prueba. ε = 2⁻⁶⁴ es un parámetro de diseño, no una garantía.
- Ninguna de las dos es una certificación FIPS/ISO (fuera de alcance).
