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
| ⟨Z⟩ | 1 − 2·p1 promediado sobre qubits; ideal 0 tras H. El sesgo de bit M1 es \|⟨Z⟩\|/2. Positivo = más ceros. |
| `ReporteSesgo` | ⟨Z⟩ crudo y mitigado de una fuente, con error estándar, `Tecnica`, `Efecto`, ⟨Z⟩ por factor (ZNE) o γ (PEC) (`adaptadores/zne_pec.py`). |
| `Efecto.SIN_EFECTO_ESPERADO` | veredicto de ZNE/PEC cuando el ruido presente (p. ej. sólo lectura) no es el que actúan: se declara, no se oculta (D-009). |
| `RelajacionConocida` | perfil T1/T2/tiempo de puerta de la H que PEC invierte; conocido, no aprendido. |
| escala efectiva (ZNE) | variable de extrapolación s = (λ+1)/2 para H plegada λ veces; el ruido llega a ⟨Z⟩ en s de las λ puertas. ⚠️ deducida a primer orden. |
| PNA / `Samplomatic` | ⚠️ sin verificar y NO implementados en F4.02: exigen ruido aprendido en el servicio de IBM. |

## Evaluación

| término | definición |
|---|---|
| M1…M7 | las siete métricas de `dominio/metricas.py`; desigualdades estrictas. |
| veredicto | conjunción de las medidas; vacío ⇒ no aprueba. |
| «certificada» | *supera la batería de pruebas y las cotas de entropía de este repositorio*. **No** es una certificación formal (FIPS/ISO) ni prueba de origen cuántico. |
| control negativo | corrida cuyo resultado esperado es «pasa» aunque la fuente sea clásica (E1a); demuestra los límites de la batería. |
| eureka | objetivo cerrado con preinscripción, corridas que descienden de ella y veredicto. |

## Puertos (`puertos/__init__.py`)

| término | definición |
|---|---|
| `FuenteDeBits` | puerto: da una `Muestra` de `qubits` × `shots`. Adaptadores: PRNG, Aer, IBM. |
| `Mitigador` | puerto: reduce el sesgo de lectura y devuelve otra `Muestra`; si remuestrea, el origen se degrada a `PRNG_CLASICO`. |
| `Validador` | puerto: mide M1, M3, M4, M5 sobre unos bits. |
| `EstimadorDeEntropia` | puerto: cota de min-entropía por bit. `EstimadorMCV` es la del dominio (ciega a la dependencia); el contraste independiente es el 90B de NIST (S.04). |
| `EstimadorDeSesgo` | puerto: ⟨Z⟩ con y sin mitigar; ahí vivirían ZNE/PEC. |
| `FuenteDeSemilla` | puerto: bits uniformes para la semilla de Toeplitz (D-004). |
| `Cifrador` | puerto: AES-GCM con la clave del pipeline. |
| `ReservaDeClaves` | puerto: reparte la clave certificada en pares (clave, nonce) de un solo uso; agotada, `EntropiaInsuficiente`. |
| `Ejecutor` | puerto: mide UNA semilla de una eureka según su `Declaracion` y devuelve una `Medicion`; no decide nada. |
| `Historial` | puerto: el historial git como testigo de que la preinscripción va antes de la corrida (`ultimo_commit`, `modificado`, `precede`). |
| `LibroDeVeredictos` | puerto: `registro/veredictos.jsonl`, una línea por veredicto, sólo se añade. |
| `Almacen` | puerto: guardar artefactos canónicos, append-only; devuelve el sha256. |
| `Reloj`, `Bitacora` | puertos de tiempo monotónico y de registro de eventos. |

## Tipos de dominio, datos y aplicación

| término | definición |
|---|---|
| `Procedencia` | backend, `job_id` y versión del SDK de una `Muestra`; `HARDWARE_IBM` sin `job_id` no se construye. |
| `Metrica`, `Umbral` | M1…M7 y su cota; `Medida` es un valor medido contra su umbral. |
| `Veredicto` | conjunción de `Medida`; vacío no aprueba. `calidad_de_clave_aprobada` juzga sólo M1–M5 (`METRICAS_DE_CLAVE`): es lo que exige cifrar; M6/M7 las juzga E3. |
| `ParametrosPipeline`, `Resultado` | entrada y salida del orquestador; `Resultado.etapas` lleva las medidas en la muestra cruda, la mitigada y la clave. |
| `InformeCorrida` | artefacto versionado de una corrida; lo guarda el `Almacen`. |
| `ExperimentoE2` | una celda de E2: sesgo de lectura antes y después de una técnica, a un nivel de ruido, con su intervalo. |
| `ExperimentoE3` | E3: tasa (M6) y latencia (M7) con la máquina en que se midieron. |
| `ErrorQRecauda` | raíz de los errores; hijas: `EntradaInvalida`, `EntropiaInsuficiente`, `FuenteNoDisponible`, `EsquemaFuturo`, `AutenticacionFallida` (cifrado o datos asociados no autentican), `NonceRepetido` (mismo nonce con la misma clave), `CorridaInvalida` (ver abajo), `CandadoOcupado` (otra corrida pesada sostiene el candado de máquina), cada una con su código de salida. |
| `Declaracion` | una eureka fijada antes de correr (`declaraciones/*.toml` fundido con `PARAMETROS.toml`): de ella salen semillas, umbrales y las rutas de su preinscripción. |
| `Medicion` | lo que el `Ejecutor` entrega por semilla: informes/experimentos tipados y el resultado de los controles. |
| `ManifiestoDeCorrida` | el registro de una corrida: artefactos con su sha256, commit de la corrida, sha de la preinscripción, entorno y controles. |
| `Criterio`, `VeredictoDeEureka` | un criterio evaluado (con su detalle, `decide` falso si sólo se reporta) y el desenlace de una eureka (`CUMPLE`, `CUMPLE_PARCIAL`, `NULO`, `INCONCLUSO`, `NO_CUMPLE`). |
| `CorrerYJuzgar` | F2.07: `correr` escribe por el `Almacen`; `juzgar` se niega si la preinscripción no precede a la corrida, cambió o falta/falla un control. |
| `CorridaInvalida` | error: la corrida no es juzgable (control faltante o fallido, preinscripción posterior o cambiada); no hay veredicto, hay incidencia. Código 9. |
| `Transaccion`, `TransaccionCifrada`, `ServicioDeTransacciones` | F6.02: el cobro de peaje/Metro, su cifrado con rótulo de origen («validación del pipeline» salvo hardware IBM con `job_id`) y el caso de uso que lo cifra con `Resultado.clave`. |
