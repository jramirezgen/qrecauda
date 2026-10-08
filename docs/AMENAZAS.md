# Modelo de amenazas de QRecauda

Qué protege un QRNG y qué no. Lo marcado ⚠️ sin verificar es hipótesis (FUNDAMENTO, «Discrepancias declaradas»). Los límites declarados se nombran como tales.

## Qué se protege
Que la clave AES-256 de una transacción no sea predecible por un atacante que no ve la fuente: sesgo de lectura y
correlaciones se tratan con mitigación, Peres y Toeplitz (LHL). La longitud de la clave se dimensiona con la
min-entropía MCV (99 %) estimada a la entrada del extractor, no de la salida. El estimador 90B no-IID se reporta como
contraste informativo: no decide la longitud.

## Ataques que SÍ cubre el diseño
| ataque | cómo se mitiga | dónde |
|---|---|---|
| Sesgo del dispositivo (lectura asimétrica) | mitigación de lectura + extractor; sesgo residual medido (M1) | F4.01, F1.02 |
| Correlación entre bits | sólo parcial: el MCV dimensiona la clave y es ciego a la dependencia; el 90B se reporta pero no decide (ver «Limitaciones») | F5.02 |
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
- **Un adversario con acceso al pool** de semillas de Toeplitz (D-004: sale del mismo pool). La independencia entre
  bloques es una hipótesis del modelo de ruido, sin medir: se declara como límite.
- **Latencia de cola y red de IBM Quantum**: no incluida en M7.

## Qué certifica y qué no certifica NIST
- SP 800-22 es una batería de **pruebas estadísticas**: un PRNG las pasa. No certifica origen ni impredecibilidad
  (D-002; el control negativo de E1, D-007, lo demuestra).
- SP 800-90B estima min-entropía de una fuente no-IID con muestras ≥ 1 000 000 bits; es una cota empírica, no una
  prueba. ε = 2⁻⁶⁴ es un parámetro de diseño, no una garantía.
- Ninguna de las dos es una certificación FIPS/ISO (fuera de alcance).

## Limitaciones declaradas

- **El dimensionado supone bits IID.** La clave se dimensiona con MCV, que mira la frecuencia marginal. Con correlación
  temporal (p. ej. hardware real) la garantía de longitud no vale. Hallazgo A1 de la revisión R.01: una fuente Markov
  con permanencia 0,8 y min-entropía real de 0,322 bit/bit da `h_min` de entrada 0,997 por MCV y una clave de unos
  756 kbit, cerca de tres veces más larga de lo que la fuente sostiene. Sobre la entrada real de E1 el 90B da 0,761–0,766
  (cruda) y 0,796–0,814 (mitigada) contra 0,997 del MCV; el 90B subestima también sobre fuentes ideales, así que esa
  cifra informa poco sobre la dependencia. Mitigación futura: dimensionar con min(MCV, 90B) y añadir al pipeline un
  control negativo con fuentes dependientes. No está hecho.
- **Selección de claves con pruebas estadísticas (M-3, R.01).** En E3 una clave que falla M3, M4 o M5 se descarta y se
  regenera (hasta cinco veces); se observaron unos 4 descartes en 99 repeticiones (≈ 4 %, esperable con tres pruebas
  al 1 %). El coste en entropía es despreciable (≈ 0,04 bit), pero las claves retenidas aprueban por construcción: su
  tasa de aprobación no es evidencia de uniformidad. Práctica desaconsejada, documentada: se reporta siempre
  `claves_rechazadas` junto a cualquier tasa de aprobación.
- **Reutilización de (clave, nonce) y concurrencia (B-1, A-1 de R.01).** La guardia de nonces era por instancia y la
  reserva de trozos no tenía candado: dos servicios sobre la misma clave o varios hilos podían cifrar con el mismo
  (clave, nonce). Corregido en la revisión R.01.
- **Replay.** `descifrar` no lleva estado: una transacción cifrada válida se acepta cuantas veces se presente. El
  anti-replay es del canal o del servidor, fuera de alcance.
