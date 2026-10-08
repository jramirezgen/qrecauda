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
| lectura (TREX / mthree) | corrección del sesgo de medición. Se aplica sobre bitstrings. TREX y mthree no son equivalentes: mthree devuelve cuasi-probabilidades, no bits (S.02, D-009). |
| ZNE / PEC | técnicas de valores esperados; aquí actúan sobre ⟨Z⟩, no sobre bitstrings, y no mueven el sesgo de lectura (C.E2). |
| ⟨Z⟩ | 1 − 2·p1 promediado sobre qubits; ideal 0 tras H. El sesgo de bit M1 es \|⟨Z⟩\|/2. Positivo = más ceros. |
| `ReporteSesgo` | ⟨Z⟩ crudo y mitigado de una fuente, con error estándar, `Tecnica`, `Efecto`, ⟨Z⟩ por factor (ZNE) o γ (PEC) (`adaptadores/zne_pec.py`). |
| `Efecto.SIN_EFECTO_ESPERADO` | veredicto de ZNE/PEC cuando el ruido presente (p. ej. sólo lectura) no es el que actúan: se declara, no se oculta (D-009). |
| `RelajacionConocida` | perfil T1/T2/tiempo de puerta de la H que PEC invierte; conocido, no aprendido. |
| escala efectiva (ZNE) | variable de extrapolación s = (λ+1)/2 para H plegada λ veces; el ruido llega a ⟨Z⟩ en s de las λ puertas. Deducida a primer orden: límite declarado. |
| PNA / `Samplomatic` | No implementados en F4.02 y sin verificar: exigen ruido aprendido en el servicio de IBM. |

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
| `FuenteIbm`, `ibm_backend`, `ibm_modo` | F3.04: adaptador de `FuenteDeBits` sobre `SamplerV2` de IBM Runtime. `ibm_backend` nombra el backend (vacío = el menos ocupado); `ibm_modo` es `batch` o `session`. El token entra por la ruta `ibm_token_ruta`, la transpilación ISA la inyecta la composición y `Procedencia.job_id` es el del trabajo real. |
| `Mitigador` | puerto: reduce el sesgo de lectura y devuelve otra `Muestra`; si remuestrea, el origen se degrada a `PRNG_CLASICO`. |
| `Validador` | puerto: mide M1, M3, M4, M5 sobre unos bits. |
| `EstimadorDeEntropia` | puerto: cota de min-entropía por bit. `EstimadorMCV` es la del dominio (ciega a la dependencia); el contraste independiente es el 90B de NIST (S.04). |
| `CotaDeEntropia` | firma mínima de una cota de min-entropía (la del puerto `EstimadorDeEntropia`, que el dominio no importa); lo que `EstimadorMinimo` combina. |
| `EstimadorMinimo` | dimensionado conservador (F5.05): el mínimo de varias cotas, cada una sobre un prefijo declarado (MCV sobre todo el pool, 90B sobre 10⁶ bits). Con `h_contable` acota además la entropía total por la de la muestra cruda. |
| `EstimadorDeSesgo` | puerto: ⟨Z⟩ con y sin mitigar; ahí vivirían ZNE/PEC. |
| `FuenteDeSemilla` | puerto: bits uniformes para la semilla de Toeplitz (D-004). |
| `Cifrador` | puerto: AES-GCM con la clave del pipeline. |
| `ReservaDeClaves` | puerto: reparte la clave certificada en pares (clave, nonce) de un solo uso; agotada, `EntropiaInsuficiente`. |
| `Ejecutor` | puerto: mide UNA semilla de una eureka según su `Declaracion` y devuelve una `Medicion`; no decide nada. |
| `LaboratorioDeLectura` | puerto de E2: fabrica, para un `RuidoDeLectura` y la semilla de la celda, la fuente, el twirling, ZNE, PEC y el contraste mthree. Lo implementa la raíz de composición sobre Aer. |
| `SondaDeMaquina` | puerto de E3: carga previa, CPU del proceso (y con hijos) y descripción de la máquina. `adaptadores/sonda_local.py`. |
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
| `InformeCorrida` | artefacto versionado de una corrida; lo guarda el `Almacen`. Opcional: `reporte` (lo que la preinscripción manda reportar sin decidir: 90B, proporción NIST, huella de la mitigada). |
| `MedidaDeFuente` | C.E1d: una fuente sintética (sesgada, periódica, Markov, ideal) con M1/M3/M4/M5, la cota MCV y el 90B; con ellas el juez recalcula el control P1. |
| `ExperimentoE2` | una celda de E2: sesgo de lectura antes y después de una técnica, a un nivel de ruido, con su intervalo. Opcional: `sesgo_maximo_por_qubit` (P.E2, nivel realista). |
| `ExperimentoE3` | E3: tasa (M6) y latencia (M7) con la máquina en que se midieron. Opcional: `reporte` (lo que P.E3 manda reportar sin decidir: t_rep por repetición, etapas, CPU/pared, perfil B). |
| `RuidoDeLectura` | qué ruido de lectura pide un experimento: canal sintético `(p(1\|0), p(0\|1))`, ninguno (`sin_ruido`) o el realista. Sus valores salen de `PARAMETROS.toml`, no de constantes. |
| `EjecutorE1`, `EjecutorE2`, `EjecutorE3` | implementan el puerto `Ejecutor` para E1 (por semilla: C.E1a PRNG, C.E1b Aer sin mitigar, C.E1c con twirling y C.E1d fuentes de control; controles N1, D1, P1), E2 (celdas por semilla y nivel, IC por bootstrap, controles C1–C5) y E3 (perfil A que decide, perfil B que no, controles U1–U5 y T4). Miden; el juez decide. |
| `ErrorQRecauda` | raíz de los errores; hijas: `EntradaInvalida`, `EntropiaInsuficiente`, `FuenteNoDisponible`, `EsquemaFuturo`, `AutenticacionFallida` (cifrado o datos asociados no autentican), `NonceRepetido` (mismo nonce con la misma clave), `CorridaInvalida` (ver abajo), `CandadoOcupado` (otra corrida pesada sostiene el candado de máquina), cada una con su código de salida. |
| `Declaracion` | una eureka fijada antes de correr (`declaraciones/*.toml` fundido con `PARAMETROS.toml`): de ella salen semillas, umbrales y las rutas de su preinscripción. |
| `Medicion` | lo que el `Ejecutor` entrega por semilla: informes/experimentos tipados y el resultado de los controles. |
| `ManifiestoDeCorrida` | el registro de una corrida: artefactos con su sha256, commit de la corrida, sha de la preinscripción, entorno y controles. |
| `Criterio`, `VeredictoDeEureka` | un criterio evaluado (con su detalle, `decide` falso si sólo se reporta) y el desenlace de una eureka (`CUMPLE`, `CUMPLE_PARCIAL`, `NULO`, `INCONCLUSO`, `NO_CUMPLE`). |
| `CorrerYJuzgar` | F2.07: `correr` escribe por el `Almacen`; `juzgar` se niega si la preinscripción no precede a la corrida, cambió o falta/falla un control. |
| `CorridaInvalida` | error: la corrida no es juzgable (control faltante o fallido, preinscripción posterior o cambiada); no hay veredicto, hay incidencia. Código 9. |
| `Transaccion`, `TransaccionCifrada`, `ServicioDeTransacciones` | F6.02: el cobro de peaje/Metro, su cifrado con rótulo de origen («validación del pipeline» salvo hardware IBM con `job_id`) y el caso de uso que lo cifra con `Resultado.clave`. |
| `GeneradorDeClaves`, `ProductorDeClaves`, `Temporizador` | puertos de E3b: el generador produce una clave aprobada por índice (corre dentro del proceso productor); el productor la entrega al consumidor por una cola acotada (`tomar`, `listas`, `detener`); el temporizador espera hasta un instante monotónico para las llegadas programadas. `adaptadores/productor_en_proceso.py`, `adaptadores/temporizador_local.py`. |
| `MetaClave`, `ClaveEntregada`, `InformeDelProductor` | E3b: la meta de una clave (índice, semilla, tiempo de generación, rechazos, 90B, bloqueo por cola llena y huella corta; nunca la clave), la clave con su meta y rótulo de origen, y el informe final del productor (núcleos, pared, CPU, metas). |
| `ExperimentoE3b` | E3b: una semilla del régimen R2 (arranque R1 informativo, tasa neta del productor, consumo, p95, esperas, CPU/pared de cada proceso, máquina). Opcional: `reporte`. |
| `GeneradorDeClaveAprobada`, `ReservaAsincrona`, `ServicioDeTransaccionesAsincrono` | F6.03: la cadena de E3 con regeneración dentro del productor; el lado del consumidor que reparte trozos de 352 bits sin repetir `(clave, nonce)` y cuenta las esperas; y el caso de uso que cifra y descifra una transacción con un trozo de la reserva. |
| `EjecutorE3b` | implementa `Ejecutor` para E3b: arranque R1, régimen R2 a λ tx/s con llegadas programadas, controles U1–U5 y T4. Mide; el juez decide T1–T3. |
| `EstimacionQpu`, `PresupuestoQpuExcedido` | F3.07: estimación a priori de los segundos de QPU de un envío (disparos × (retardo + duración) + sobrecarga por trabajo, ⚠️ sin verificar contra el cargo real) y el error que aborta ANTES de enviar si pasa el tope `--max-segundos-qpu` o la cuota restante del servicio. |
| `RegistroIbm`, `CalibracionQubit` | F3.07: lo que se guarda de cada trabajo enviado a IBM (job_id, backend, versión del SDK, modo, qubits físicos, profundidad transpilada, vía de transpilación, tiempos de cola y ejecución, uso de QPU y calibración T1/T2/error de lectura por qubit). Nunca el token. |
