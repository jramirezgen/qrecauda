---
title: "QRecauda: un pipeline QRNG planificado como contrato verificable, preinscrito y acotado en sus afirmaciones"
subtitle: "Planeación, metodología y resultados de los experimentos E1 y E2 (E3 pendiente)"
author: kaitokid
date: "2026-10-07"
lang: es
serie: "Informe técnico · QRecauda"
keywords: [generador cuántico de números aleatorios (QRNG), preinscripción, DAG verificable, mitigación de lectura, extracción de aleatoriedad, reproducibilidad]
licencia: "Licencia Apache-2.0 · Repositorio público del proyecto (enlace en la ficha del repositorio) · Estado: informe vivo; E1 y E2 con veredicto CUMPLE, E3 pendiente"
subject: "Pipeline QRNG para recaudación: planeación, método preinscrito y resultados"
abstract: |
  QRecauda genera claves AES-256-GCM a partir de los bits de un circuito de un solo gate (Hadamard sobre 8 qubits, medido en la base computacional) y las destina a cifrar transacciones de peaje y de Metro. La cadena de procesamiento es clásica y conocida: mitigación de lectura, extractor de Peres, hash de Toeplitz dimensionado con el *Leftover Hash Lemma*, y validación con NIST SP 800-22 y SP 800-90B. El aporte principal es metodológico. El plan se formaliza como un grafo dirigido acíclico de 59 nodos que una herramienta valida; cada experimento se preinscribe antes de correr, con controles positivos y negativos obligatorios y enmiendas fechadas; la arquitectura hexagonal de cuatro macro-capas se impone con seis contratos de importación; y toda cifra procede de una corrida nombrada.

  El experimento E1 (calidad de la clave) obtiene el veredicto CUMPLE en las tres semillas preinscritas, con claves de unos 955 000 bits. La clave sin mitigar también pasa M1 a M5 en las tres semillas (hallazgo R.00-1): Peres y Toeplitz bastan para aprobar la batería, y la mitigación reduce el sesgo crudo de 0,030 a un máximo de 0,0004 sin ser necesaria para aprobar. El experimento E2 (sesgo de lectura) obtiene CUMPLE en las nueve celdas sintéticas: el *twirling* propio lleva el sesgo medio por qubit de 0,0098–0,0505 a 0,00074–0,00131, mientras que ZNE y PEC dejan el sesgo de lectura sin cambio apreciable (hasta 6,6 %). El nivel realista no pone a prueba la mitigación y el nivel bajo coincide con el umbral de M1. El experimento E3 (tasa y latencia), la corrida en hardware IBM, la derivación del TRL y la revisión adversarial del release están pendientes y no se reportan cifras de ellos; el incumplimiento de M7 es una hipótesis sin verificar. El simulador no aporta entropía cuántica, «certificada» significa «supera esta batería», la calibración del control P1 se hizo con conocimiento de las semillas y la estimación 90B es una cota conservadora que acortaría la clave en torno a 14 %.
---

# Introducción {#sec:intro}

## Problemática {#sec:problema}

Los sistemas de cobro automático de peajes y del Metro de Lima firman, autentican y cifran millones de transacciones pequeñas al día. La seguridad de ese cifrado depende de un supuesto poco visible: las claves y los *nonces* provienen de una fuente que un atacante no puede predecir. Un generador pseudoaleatorio (PRNG) calcula su salida como función determinista de un estado interno. Quien reconstruye o roba ese estado reproduce las claves futuras y, si no hay renovación, también las pasadas. El equipo fundador lo resumió en una tesis: la aleatoriedad clásica se predice, y la recaudación del Perú no debería depender de ella.

El proyecto surgió en el *Track 4* de la Hackatón Qiskit IBM Lima, dedicado a criptoseguridad para recaudación mediante QRNG. El caso de uso consiste en cifrar con AES-256-GCM una transacción de peaje o de Metro con una clave producida por el pipeline. El repositorio no contiene ningún requisito formal de OSITRAN, del MTC ni del Metro (⚠️ sin verificar su existencia en otra fuente); los umbrales de tasa y latencia proceden del manifiesto del equipo.

Tres dificultades hacen que esta aplicación exija más que ejecutar un circuito y calcular estadísticos.

El primer problema es que un QRNG en simulador no produce entropía cuántica. El simulador de Qiskit Aer muestrea con un generador pseudoaleatorio: con la misma semilla reproduce los bitstrings disparo a disparo. Inyectarle ruido de lectura asimétrico crea sesgo realista en los bits, y ese sesgo permite someter a prueba el postprocesamiento (mitigación, extracción y validación). La fuente cuántica queda sin evaluar. Una demostración sobre simulador valida, por tanto, la cadena de procesamiento y no el origen de la aleatoriedad.

El segundo es que una batería estadística no certifica una clave. NIST SP 800-22 mide propiedades de una secuencia. Un PRNG clásico las cumple, de modo que aprobar la batería no distingue una fuente cuántica de una determinista. Hay un segundo problema de medición: los estadísticos se calculan casi siempre sobre la salida de un extractor, y un extractor bien dimensionado devuelve bits casi uniformes incluso a partir de una fuente defectuosa. Si la batería sólo mira la clave, cualquier entrada la supera.

El tercero es que el estimador de min-entropía por valor más común (MCV) no ve la dependencia. El MCV considera únicamente la frecuencia marginal del símbolo más probable. Una cadena de Markov con permanencia 0,8 tiene una entropía real de 0,322 bit por bit y un MCV de 0,992, de modo que el estimador la acepta. El estimador no-IID de SP 800-90B la rechaza, pero devuelve el mínimo de diez estimadores, una cota conservadora que subestima también a las fuentes ideales y que impide fijar un umbral absoluto razonable.

## Objetivos e hipótesis {#sec:objetivos}

El objetivo general es construir un pipeline QRNG reproducible y medir, con criterios fijados de antemano, siete métricas de aceptación (M1 a M7, [Tabla](#tbl:metricas)). Los objetivos específicos son tres: demostrar que la cadena entrega claves que superan la batería con entrada ruidosa y que el instrumento de medida distingue fuentes defectuosas de fuentes buenas; cuantificar cuánto reduce una mitigación de lectura el sesgo de los bits; y medir la tasa y la latencia del conjunto en una PC. A cada uno corresponde una hipótesis y un experimento preinscrito ([Tabla](#tbl:hipotesis)).

| hipótesis | enunciado | experimento | criterios preinscritos que la deciden |
|:----------|:-----------------------------------------|:-----------|:-----------------------------------------|
| H1 | Con entrada ruidosa (nivel medio de ruido de lectura, sesgo analítico 0,030), la cadena entrega una clave que cumple M1 a M5, y la medición separa fuentes defectuosas de fuentes buenas | E1 | La mitigada cumple M1 y M3 (M-1); la clave cumple M1 a M5 (M-2); la cruda sin mitigar falla M1 o M3 (B1); el detector ve el sesgo inyectado (D1); el PRNG clásico pasa la batería (control negativo); el instrumento 90B separa las fuentes sintéticas (P1) |
| H2 | La mitigación de lectura reduce el sesgo de los bits por debajo del umbral de M1 | E2 | Por celda de nivel y semilla: residuo menor que 0,01 (K1), límite superior del IC95 menor que 0,01 (K2), residuo máximo 0,003 (K3), factor crudo/residuo mínimo 5 (K4) |
| H3 | El conjunto completo entrega más de 10 000 bit/s (M6) con latencia de extremo a extremo inferior a 500 ms (M7) | E3 | Perfil A con lote completo; percentil 95 de 30 repeticiones; controles de integridad U1 a U5 |

: Hipótesis, experimentos y criterios preinscritos. []{#tbl:hipotesis}

Se espera que H1 y H2 se sostengan en el modelo sintético, con las salvedades que el propio diseño anticipa, y que H3 sea la más expuesta al resultado negativo. Los resultados están en la [sección](#sec:resultados).

## Alcance {#sec:alcance}

Este trabajo es de ingeniería y de método experimental. No afirma entropía cuántica en simulación, ni certificación FIPS o ISO, ni prueba de origen cuántico (que exigiría pruebas de Bell o autoverificación [8]), ni aptitud de las claves para producción. Tampoco incluye integración con los sistemas de OSITRAN, MTC o Metro, módulos de seguridad (HSM), distribución de claves ni multiplexado de backends. El hardware IBM real es opcional: ni la demostración ni la versión 0.1.0 dependen de él.

## Contribuciones {#sec:contribuciones}

Cada contribución se verifica en el repositorio mediante el nodo del plan o la corrida que se indica ([Tabla](#tbl:aportes)).

| \# | contribución | evidencia en el repositorio | sección |
|:-----|:------------------------------------|:------------------------------------|:--------------------------|
| 1 | Plan como DAG de 59 nodos con registro de sólo añadir y preinscripción anterior a la corrida; un juez que se niega a veredictar si falta el orden o un control | F0.05, F2.07; verificación `dag.py validar`; error de salida 9 | [4](#sec:plan), [5](#sec:preinscripcion) |
| 2 | Mitigación de lectura propia por *twirling* con XOR clásico, y el análisis de que ZNE y PEC no actúan sobre el ruido de lectura, con escala efectiva $s=(\lambda+1)/2$ en el plegado de la puerta H | F4.01, F4.02; spike S.02; corrida C.E2 | [7](#sec:mitigacion), [8](#sec:e2) |
| 3 | Control positivo del estimador 90B con fuentes sintéticas, que muestra la ceguera del MCV a la dependencia | spike S.04; corrida C.E1d | [7](#sec:entropia), [8](#sec:e1) |
| 4 | Hallazgo R.00-1: Peres y Toeplitz bastan para que la clave pase M1 a M5, con la fuente cruda fuera de umbral | revisión R.00; corrida C.E1b; veredicto de E1 | [8](#sec:e1) |
| 5 | Arquitectura hexagonal en cuatro macro-capas con seis contratos de importación ejecutables, trinquetes por AST y 346 pruebas | F0.04; pruebas de arquitectura; CI local | [6](#sec:arquitectura) |
| 6 | Protocolo de reproducibilidad: semillas declaradas, manifiestos con commit y entorno, y figuras regeneradas desde el registro | manifiestos de `registro/corridas/`; `docs/paper/figuras.py` | [11](#sec:repro) |

: Contribuciones y su evidencia verificable. []{#tbl:aportes}

# Trabajos relacionados {#sec:relacionados}

Esta sección cita únicamente fuentes cuyos datos bibliográficos se contrastaron con el registro de DOI (Crossref) o con el repositorio de preprints el 2026-10-07.

Herrero-Collantes y García-Escartín [1] revisan los generadores cuánticos de números aleatorios y el modelado de sus fuentes y extractores. Un QRNG con circuito de Hadamard sobre qubits físicos es la versión más simple; certificar su origen requiere pruebas de Bell en el estilo de Pironio *et al.* [8], que este trabajo no realiza.

NIST SP 800-22 Rev. 1a [2] define una batería de pruebas estadísticas (monobit, rachas, frecuencia por bloques, entre otras) y el criterio de proporción de secuencias aprobadas. NIST SP 800-90B [3] especifica la estimación de min-entropía de fuentes de ruido, con el estimador de valor más común (MCV) y la batería no-IID, de la que se toma el mínimo de diez estimadores.

El procedimiento de von Neumann elimina el sesgo de bits independientes, y Peres [4] lo itera para reciclar la información descartada. Para convertir una fuente de min-entropía conocida en bits casi uniformes se emplean un hash universal y el *Leftover Hash Lemma* de Impagliazzo, Levin y Luby [5], con versión de revista en Håstad *et al.* [6]. Las matrices de Toeplitz forman una familia universal eficiente cuyo uso en hashing se remonta a Krawczyk [7].

AES-GCM fue presentado por McGrew y Viega [9] y estandarizado en NIST SP 800-38D [10]. Su seguridad exige que el par (clave, nonce) no se repita; el pipeline lo garantiza con una reserva de claves de uso único.

Qiskit [11] y su simulador Aer proveen el muestreador, el simulador y los modelos de ruido. La mitigación sobre valores esperados incluye la extrapolación a ruido cero (ZNE) y la cancelación probabilística de errores (PEC) de Temme, Bravyi y Gambetta [12], con ZNE también en Li y Benjamin [13]. La mitigación de lectura incluye TREX, que aplica *twirling* a la medición [14], y mthree [15]. ZNE y PEC se definen sobre valores esperados, y TREX y mthree corrigen distribuciones o valores esperados; ninguna produce un flujo de bits por disparo. De ahí la mitigación propia de este trabajo.

El *twirling* de lectura propuesto es una variante de la idea de TREX [14] adaptada para conservar los bitstrings. El trabajo añade la integración reproducible de punta a punta con límites declarados, un método experimental preinscrito y auditable, y un registro de los puntos en que el método del manifiesto choca con lo que permiten la estadística y las bibliotecas.

# Amenazas y alcance de seguridad {#sec:amenazas}

## Qué se protege {#sec:proteger}

Se protege que la clave AES-256 de una transacción no sea predecible por un atacante que no observa la fuente. El sesgo de lectura y las correlaciones se tratan con mitigación, extractor de Peres y hash de Toeplitz. La longitud de la clave se calcula con la min-entropía estimada a la entrada del extractor, porque la de salida vale casi 1 por construcción y no informa.

## Amenazas cubiertas y no cubiertas {#sec:cubiertas}

| amenaza | tratamiento | estado |
|:-----------------------------------|:-----------------------------------|:---------------------------------|
| Sesgo del dispositivo (lectura asimétrica) | Mitigación de lectura, extractor y sesgo residual medido (M1) en tres puntos | cubierta (E1, E2) |
| Correlación entre bits | Estimador SP 800-90B no-IID; el MCV se declara ciego a la dependencia | cubierta con límites |
| Reutilización de (clave, nonce) en GCM | `ReservaDeClave` reparte trozos disjuntos de 352 bits y repetir falla | cubierta por pruebas; control U2 de E3 pendiente |
| Manipulación del texto cifrado | AES-GCM autentica; error `AutenticacionFallida` | cubierta por pruebas |
| Agotamiento de entropía | `EntropiaInsuficiente` aborta sin degradar | cubierta |
| Secretos en el repositorio | Secretos por ruta y trinquete antisecretos | cubierta |
| Origen no cuántico de la fuente | Rótulo `Origen` y control negativo con PRNG (C.E1a) | declarada, no certificable sin hardware y pruebas de Bell |
| Canal (TLS, red) | n. a. | fuera de alcance |
| Canales laterales, volcados de memoria, dependencias comprometidas | n. a. | fuera de alcance |
| Gestión de claves (KMS, HSM) | n. a. | fuera de alcance |
| Adversario con acceso al *pool* de semillas de Toeplitz | n. a. | fuera de alcance (D-004) |
| Latencia de cola y red de IBM Quantum | n. a. | fuera de M7 |

: Amenazas que el diseño cubre y las que no. []{#tbl:amenazas}

## Discrepancias con el manifiesto fundacional {#sec:discrepancias}

El manifiesto del equipo gobierna el objetivo del proyecto. Su método choca en nueve puntos con lo que permiten las bibliotecas o la estadística. Cada punto se declaró antes de actuar, y una décima discrepancia surgió de la revisión adversarial del diseño ([Tabla](#tbl:discrepancias)).

| \# | El manifiesto dice | Lo que se encontró o decidió | Estado |
|:-----|:-------------------------------------|:-------------------------------------|:--------------------------|
| 1 | «No dependemos de hardware real» y, a la vez, «procesadores físicos de IBM» | Son dos alcances: el backend es un puerto (D-001), con simulador por defecto y hardware opcional | decidido |
| 2 | Aer con ruido produce «entropía cuántica» | El muestreo de Aer es un PRNG; `Origen.SIMULADOR_AER` no reclama origen cuántico (D-002; S.03) | demostrado |
| 3 | TREX + ZNE + PEC mitigan el *bitstream* del muestreador | ZNE y PEC se definen sobre valores esperados; `resilience_level` es opción del estimador (S.02) | verificado |
| 4 | «TREX vía mthree» | Son técnicas distintas; mthree entrega cuasi-probabilidades, no bits (D-009) | verificado |
| 5 | Min-entropía > 0,9 prueba la calidad | Tras Toeplitz vale casi 1 por construcción; la informativa es la de entrada | decidido |
| 6 | «Claves certificadas» | SP 800-22 no certifica origen ni impredecibilidad; hay control negativo (D-007) | decidido |
| 7 | «TRL 4» | La rúbrica exige $n\ge3$, protocolo preinscrito y auditable; el TRL real es el de la afirmación más débil (fuente en simulador: TRL 3) | declarado; lo cierra T.TRL (pendiente) |
| 8 | El MCV decide la longitud y la «certifica» | El MCV es ciego a la dependencia: Markov con permanencia 0,8 (real 0,322 bit/bit, analítico) da MCV 0,992 (S.04, C.E1d) | demostrado |
| 9 | M1 < 1 % y M2 > 0,9 como umbrales | Con $N=800\,000$ el monobit exige sesgo menor que 0,0014 (siete veces más estricto que M1) y M2 sobre 256 bits no supera 0,785 (analítico, P.E0) | decidido |
| 10 | (revisión R.00) | Medir M1 a M5 sólo sobre la salida de Toeplitz haría pasar a cualquier fuente; se miden en tres puntos (cruda, mitigada y clave); hallazgo R.00-1 | decidido y confirmado en E1 |

: Discrepancias con el manifiesto fundacional. []{#tbl:discrepancias}

# El plan como contrato verificable {#sec:plan}

La planeación es la parte más desarrollada del trabajo. El plan es un grafo dirigido acíclico generado por un script. El estado de cada nodo vive aparte, en un registro de sólo añadir, y una herramienta de validación rechaza cualquier estado que contradiga las reglas. El plan no se edita a mano: se regenera, y una prueba comprueba que el fichero versionado coincide con la regeneración. Así, la pregunta «¿se hizo?» tiene una respuesta mecánica.

## Estructura del DAG {#sec:dag-estructura}

El plan tiene 59 nodos y 132 aristas, con una única hoja (la versión 0.1.0 del producto) y una profundidad máxima de 15 niveles. Se organiza en ocho fases más la revisión final ([Tabla](#tbl:fases)). Cada nodo declara su tipo ([Tabla](#tbl:tipos)), sus dependencias, su entrega (rutas del repositorio), el criterio de cierre y los requisitos que cubre. La [Figura](#fig:dag) muestra el estado real a la fecha: 48 nodos hechos, 2 juzgados (E1 y E2), 2 listos y 7 pendientes bloqueados.

![El plan como DAG, por fases y coloreado por el estado real (plan de 59 nodos y registro de estado). Borde grueso: eureka; discontinuo: preinscripción; punteado: corrida o medición. Verde: hecho; azul: juzgado; naranja: listo; blanco: pendiente.](fig/dag.pdf){#fig:dag}

| fase | contenido | nodos |
|:----------|:---------------------------------------------------------------------------------|------------:|
| F0 | Fundación: repositorio, decisiones, contratos de importación, DAG, hooks, CI local, revisión adversarial R.00 | 11 |
| F1 | Dominio: bits, extractores (von Neumann, Peres, Toeplitz con LHL), entropía y métricas | 3 |
| F2 | Puertos, bala trazadora, transversales, presentación, almacén, correr y juzgar | 7 |
| F3 | Fuente y ruido: spikes S.01 a S.04, circuito sobre Aer, modelo de ruido, transpilación, IBM opcional | 10 |
| F4 | Mitigación: *twirling* de lectura (F4.01) y ZNE/PEC sobre ⟨Z⟩ (F4.02) | 2 |
| F5 | Validación: batería NIST SP 800-22 y min-entropía SP 800-90B | 2 |
| F6 | Cifrado AES-256-GCM y transacción de peaje o Metro | 2 |
| E | Experimentos: parámetros P.E0, preinscripciones P.E1 a P.E3, corridas, veredictos E1 a E3 | 13 |
| F7 | Difusión: amenazas, integración, TRL, wiki, informe | 7 |
| R | Revisión adversarial del release (R.01) y release 0.1.0 | 2 |

: Fases del plan y número de nodos de cada una. []{#tbl:fases}

| tipo | nodos | uso |
|:---------------------------|----------:|:------------------------------------------------------------------|
| infra | 13 | repositorio, contratos, CI, hooks, transversales, integración |
| adaptador | 11 | un sistema externo detrás de un puerto (Aer, IBM, mthree, nistrng, cifrado, disco) |
| doc | 7 | documentos con entrega comprobable (amenazas, TRL, informe) |
| corrida | 5 | ejecución preinscrita cuyo artefacto entra al registro |
| insumo | 4 | spikes de viabilidad (S.01 a S.04) |
| decision | 3 | decisión con consecuencia en el plan (parámetros P.E0, hardware) |
| dominio, aplicacion | 3 + 3 | lógica pura y casos de uso |
| preinscripcion | 3 | fija umbrales, controles y desenlaces antes de correr |
| eureka | 3 | veredicto de un experimento; depende de sus corridas |
| revision | 2 | revisión adversarial independiente |
| medicion | 1 | medición de tiempos con candado de máquina (C.E3) |
| release | 1 | versión 0.1.0; exige revisión propia |

: Tipos de nodo. []{#tbl:tipos}

## Reglas que la herramienta hace cumplir {#sec:reglas-dag}

La validación del plan comprueba once reglas ([Tabla](#tbl:reglas-dag)). Las más relevantes para la credibilidad de los resultados son cuatro: el cierre de un nodo exige un commit que modifique su entrega; el registro de estado sólo admite añadidos; cada experimento tiene exactamente una preinscripción de la que descienden sus corridas; y cada release exige una revisión adversarial propia.

| regla | efecto |
|:---------------------------------------------------|:---------------------------------------------------|
| Acíclico, con dependencias existentes y una sola hoja | Impide ciclos, nodos huérfanos y destinos ambiguos |
| Monotonía: un nodo no puede estar avanzado sobre dependencias abiertas | Impide declarar un resultado antes que sus insumos |
| Cerrar exige un commit que toque la entrega del nodo | La evidencia es un commit verificable y no una declaración |
| Registro de sólo añadir: cada versión de `registro/*.jsonl` extiende a la anterior y el estado de un nodo es su última línea | El pasado no se reescribe; un resultado negativo no se borra |
| Eureka con una sola preinscripción; sus corridas descienden de ella; el eureka depende de al menos una | Impide veredictos sin preinscripción o con varias a elegir |
| Revisión adversarial propia por release (no vale la que ya sirvió a una release anterior) | Impide reutilizar una revisión vieja |
| Nodos protegidos: no se borran, no cambian de tipo, no dejan de cubrir un eureka sin declararlo | Impide «resolver» un problema quitando el nodo que lo prueba |
| `juzgado` sólo para eurekas y con veredicto en el registro | Todo veredicto deja rastro |
| Los nodos abiertos no citan decisiones congeladas ni frases de alarma; el criterio de cierre tiene longitud acotada | Impide reabrir lo decidido y criterios vagos |
| Cobertura: todo requisito del manifiesto lo cubre algún nodo | Impide requisitos olvidados |
| El plan versionado es la regeneración del script y cada versión se valida contra la anterior | Impide eludir las reglas commiteando generador y plan a la vez |

: Reglas del DAG que `dag.py validar` y la CI local comprueban. []{#tbl:reglas-dag}

Cada experimento tiene así tres nodos encadenados: una preinscripción, una o varias corridas que descienden de ella y un nodo de veredicto que depende de las corridas. El documento de estado legible se genera desde el plan y el registro y nunca se edita.

## Ejecución paralela con revisión {#sec:paralela}

Las tareas independientes del DAG (adaptadores distintos, los cuatro spikes) avanzaron en paralelo. Cada entrega pasó por la CI local antes de empujarse, y el plan exige revisiones adversariales independientes. La primera, sobre el diseño y anterior a la construcción, puntuó la arquitectura de capas con 6/10 y el DAG hacia TRL 4 con 3,5/10. Los hallazgos aceptados entraron al tablero de incidencias antes que al DAG. La segunda revisión corresponde al release y está pendiente: hasta que se realice, la calidad del diseño es una afirmación de papel y no una demostración.

# Preinscripción y método experimental {#sec:preinscripcion}

## Protocolo de preinscripción {#sec:que-preinscribir}

La regla 5 del documento de fundamento obliga a fijar el umbral y el criterio de cada experimento antes de la corrida. El protocolo opera en cinco pasos.

1. La preinscripción en prosa y su declaración legible por máquina entran en un commit.
2. La corrida registra en su manifiesto el commit de la preinscripción y el del código.
3. El juez se niega a veredictar si ese commit no precede a la corrida, si el documento cambió después o si falta o falla un control (error de salida 9).
4. Un control fallido significa que la medición no es válida: no se emite veredicto y se abre una incidencia.
5. Un resultado negativo cierra el experimento como negativo; reintentar exige una preinscripción nueva y el veredicto anterior se conserva.

Un error detectado antes de correr se corrige con una enmienda fechada, en commit propio y anterior a la corrida; después de correr, el documento no se modifica. Las semillas (20261007, 20261008 y 20261009) se declaran de antemano, y elegir una semilla está prohibido: el veredicto se emite sobre las tres.

![Cronología de preinscripciones, enmiendas, código del ejecutor y corridas con veredicto (hora de commit del 2026-10-07; eje cortado entre 19:30 y 21:30). Cada preinscripción precede a su corrida; E3 queda pendiente.](fig/cronologia.pdf){#fig:cronologia}

La [Figura](#fig:cronologia) muestra el orden real, leído de los commits. El juez comprueba por máquina que el commit de la preinscripción es ancestro de la corrida.

## Controles positivos y negativos {#sec:controles}

Cada experimento tiene controles sin los cuales no hay veredicto. Un control negativo comprueba que la batería acepta lo que debe aceptar, incluido un PRNG clásico. Un control positivo comprueba que el detector reconoce lo que se inyecta ([Tabla](#tbl:controles)).

| experimento | control | tipo | qué comprueba |
|:---------------|:--------------|:----------------------|:------------------------------------------------------|
| E1 | N1 (C.E1a) | negativo | El PRNG clásico sin sesgo y sin mitigación pasa M1 a M5: la batería no prueba origen cuántico (D-007) |
| E1 | D1 | positivo | El detector ve el sesgo inyectado: $\lvert$M1 cruda $-\,0{,}030\rvert\le0{,}002$ |
| E1 | P1 (C.E1d) | positivo | El instrumento separa lo bueno de lo malo: sesgada, periódica y Markov bajo el techo 0,5 del 90B, ideal sobre el piso 0,8, MCV de la Markov $\ge0{,}9$ |
| E1 | B1 | positivo | La cruda de Aer ruidoso debe fallar M1 o M3 con el ruido declarado |
| E2 | C1 | positivo | $\lvert$crudo $-$ analítico$\rvert\le0{,}002$ en los niveles medio y alto |
| E2 | C2 | negativo | *Twirling* sin ruido: residuo $\le0{,}003$ |
| E2 | C3 | negativo | *Twirling* con canal simétrico (0,05; 0,05): residuo $\le0{,}003$ |
| E2 | C4 | puerta | ZNE o PEC «sin efecto» si mueven $\langle Z\rangle$ menos de 10 % |
| E2 | C5 | contraste | mthree como cifra de contraste, sin decidir |
| E3 | U1 a U5 | positivo y negativo | Ida y vuelta 1 000/1 000; alteración de 1 bit detectada al 100 %; clave ajena falla al 100 %; ningún par (clave, nonce) repetido; rótulos «validación del pipeline» |

: Controles de los experimentos. Un control fallido invalida la corrida. []{#tbl:controles}

La tasa de falsa alarma del control negativo es $1-0{,}99^{18}\approx0{,}165$ por las 18 pruebas a $\alpha=0{,}01$ (analítico, con supuesto de independencia ⚠️). Se aceptó a priori. Si ocurre, la corrida es inválida y no se repite con otra semilla.

## Criterios por experimento {#sec:criterios}

| experimento | afirma | criterios que deciden | informativos |
|:---------|:--------------------------------|:--------------------------------|:--------------------------------|
| E1 | Con entrada ruidosa (Aer, nivel medio, sesgo analítico 0,030) la cadena entrega una clave que cumple M1 a M5 y la medición distingue fuentes malas de buenas | C.E1a, D1, P1, B1; M-1: la mitigada pasa M1 y M3; M-2: la clave pasa M1 a M5 | M4 y M5 de la mitigada, 90B de la cruda y la mitigada, proporción NIST de la clave, resultado de la clave sin mitigar |
| E2 | Con ruido de lectura asimétrico inyectado, la mitigación baja el sesgo bajo M1 | Por celda (9 celdas sintéticas de nivel y semilla): K1 residuo $<0{,}01$; K2 IC95 superior $<0{,}01$; K3 residuo $\le0{,}003$; K4 crudo/residuo $\ge5$ si crudo $\ge0{,}01$ | Nivel realista (veredicto propio, fuera de la conjunción); mthree; ZNE y PEC |
| E3 | El conjunto en una PC con Aer entrega M6 $>10\,000$ bit/s y M7 $<500$ ms, con una transacción cifrada | Perfil A (lote completo de 3,2 M de bits): M6 y M7 (percentil 95 de 30 repeticiones), U1 a U5 | Perfil B (reserva ya generada, 1 000 transacciones); no puede rescatar un perfil A fallido |

: Criterios preinscritos de cada experimento. []{#tbl:criterios}

Tras ver un resultado, ningún experimento puede relajar un umbral, repetirse con otra semilla ni mover una métrica a informativa. Los desenlaces posibles son CUMPLE, NO CUMPLE, NULO, CUMPLE PARCIAL e INVÁLIDA, y esta última corresponde al error de corrida inválida.

## Enmiendas fechadas y desviaciones del protocolo {#sec:enmiendas}

Todas las enmiendas son anteriores a la corrida a la que afectan, y ninguna cambia un umbral de M1 a M7. Cada una abre una oportunidad de sesgo del investigador y por eso se documenta ([Tabla](#tbl:enmiendas)).

| fecha | doc. | enmienda | commit | motivo y alcance |
|:---------|:------|:----------------------------------|:---------------------|:----------------------------------|
| 2026-10-07 | E3 | El guard de cifrado juzga sólo M1 a M5; M6 y M7 las juzga C.E3 de extremo a extremo | `8984147`, `09da88c`, `5a72939` | Las M6 y M7 internas se miden hasta Toeplitz y podrían impedir cifrar; no se salta el guard ni se relaja un umbral |
| 2026-10-07 | E3 | M1 a M5 en el punto «mitigada» pasan a informativas | `5a72939` | Misma causa que en E1; los criterios T1 a T4 no leen M1 a M5 |
| 2026-10-07 | E1 | M5 sobre la mitigada pasa a informativa | `dae22a6` | Diagnóstico de escritorio sin corrida registrada ⚠️ |
| 2026-10-07 | E1 (1) | M4 sobre la mitigada pasa a informativa; M-1 decide con M1 y M3 | `1a06602` | Misma causa; la clave sigue decidiendo con M1 a M5 |
| 2026-10-07 | E1 (2) | P1 cambia de «ideal con 90B $>0{,}9$» a separación del instrumento: piso 0,8 y techo 0,5 | `37b89ca`, `447c907` | Desviación declarada, descrita a continuación |

: Enmiendas fechadas, todas anteriores a la corrida. []{#tbl:enmiendas}

La enmienda del control P1 constituye una desviación del protocolo que debe declararse con detalle. El 90B de la fuente ideal se midió antes de correr E1, pero sobre las semillas declaradas (20261007, 20261008 y 20261009) y ocho más (20261010 a 20261017), con $10^6$ bits por fuente y semilla. La fuente ideal dio 90B entre 0,821 y 0,903 (sólo 2 de 11 superan 0,9), la Markov entre 0,170 y 0,172, la sesgada entre 0,321 y 0,324, y la periódica 0. El criterio original (ideal con 90B mayor que 0,9) fallaba en 9 de 11 fuentes ideales. El instrumento resultaba inválido por una propiedad suya, ya que el mínimo de diez estimadores es una cota conservadora incluso con $h=1$, y no por la fuente. Además, el 0,9 de M2 corresponde a la clave de salida tras Toeplitz, otra magnitud. El piso 0,8 es el mínimo observado (0,821) redondeado hacia abajo a la décima; el techo 0,5 deja un hueco de 0,3.

Quien fijó el piso conocía los valores de las tres semillas declaradas (0,821; 0,902 y 0,832). En consecuencia, P1 pasaría en ellas salvo cambio de código, la calibración no fue ciega, y la cola por debajo de 0,8 en una semilla futura no está medida (⚠️ sin verificar). La pregunta que P1 responde pasa a ser una separación (¿distingue el estimador lo bueno de lo malo?) y deja de ser si la ideal alcanza 0,9.

# Arquitectura y calidad del código {#sec:arquitectura}

## Cuatro macro-capas {#sec:capas}

La arquitectura es hexagonal. El núcleo no importa ningún SDK y todo lo que comunica con un sistema externo vive detrás de un puerto ([Figura](#fig:capas)). Hay cuatro macro-capas ([Tabla](#tbl:capas)); la presentación y la interfaz de línea de comandos son bordes de la lógica y no una quinta capa.

![Arquitectura en cuatro macro-capas y dependencias permitidas (flechas). La lógica no depende de la integración, lo transversal es hoja y cada adaptador es independiente de los demás.](fig/capas.pdf){#fig:capas}

| macro-capa | contenido | paquetes |
|:----------------|:----------------------------------------------------|:-----------------------------------|
| Datos | Lo que persiste y cruza fronteras: esquemas versionados, informes, serialización canónica, almacén de sólo añadir | `datos/`, puerto `Almacen` |
| Lógica | Matemática de la entropía, métricas, casos de uso y orquestador | `dominio/` (puro), `aplicacion/` |
| Integración | Todo lo que comunica con un sistema externo, uno por puerto, con su SDK confinado | `adaptadores/`, `composicion.py` |
| Transversales | Configuración, errores, observabilidad, reproducibilidad, seguridad, concurrencia, empaquetado | `transversal/`, `dominio/errores.py` |

: Macro-capas de la arquitectura. []{#tbl:capas}

La fuente de bits es un puerto (D-001) con tres adaptadores: PRNG clásico, Aer e IBM Runtime. La mitigación es otro puerto. El validador y el estimador de entropía tienen cada uno dos implementaciones independientes que se contrastan entre sí (D-006): el validador propio frente a nistrng, y la cota MCV del dominio frente al estimador oficial no-IID. Un adaptador cambia sin tocar a otro, y los SDK pesados son extras opcionales.

## Contratos de importación y trinquetes {#sec:contratos}

| contrato | regla | qué previene |
|:-----------|:-----------------------------------------------------|:--------------------------------------|
| C1 | Las capas sólo se importan en el sentido permitido | Que la lógica dependa de la integración |
| C2 | Los adaptadores son independientes entre sí | Acoplar Aer con IBM o con mthree |
| C3 | El núcleo y la presentación no importan transversal, adaptadores ni entrada | Un núcleo con efectos laterales |
| C4 | El dominio es puro: sin E/S, reloj, aleatoriedad global ni SDK | Resultados no reproducibles |
| C5 | Los SDK sólo se importan en adaptadores | Fuga de dependencias pesadas al núcleo |
| C6 | Lo transversal es hoja | Ciclos con configuración y errores |

: Contratos de importación (C1 a C6) verificados con import-linter. []{#tbl:contratos}

Sobre los seis contratos operan trinquetes por AST: ninguna captura silenciosa de excepciones genéricas, lectura del entorno sólo en configuración, ninguna credencial en el código, ninguna aleatoriedad global en el dominio, y lo vendorizado sin divergencias. Un trinquete sólo puede apretarse, de modo que un caso nuevo que lo viole rompe la CI. Una prueba siembra un import prohibido para comprobar que el contrato falla cuando debe, porque un contrato que nunca falla no demuestra nada. Un hook de commit rechaza mensajes con atribución automática de autoría.

## Desarrollo guiado por pruebas y CI local {#sec:tdd}

La prueba precede a la implementación, y cada decisión de diseño con consecuencia verificable tiene una prueba que la fija. El repositorio contiene 346 funciones de prueba (conteo estático, sin casos parametrizados) repartidas por capa: dominio, adaptadores, aplicación, arquitectura, transversales, integración y datos. Entre ellas figuran: Toeplitz por FFT exacto a $n\ge2\cdot10^5$ y coincidente con la matriz densa módulo 2; los validadores NIST propio y de nistrng contrastados entre sí y con los vectores publicados; el cifrador contra el vector oficial de GCM; la aritmética de ZNE sobre la escala efectiva; y el control negativo de la propia arquitectura. La CI local (ruff, mypy en modo estricto, import-linter, comprobaciones del DAG y pytest) se ejecuta antes de empujar, y un hook de push la exige.

# Pipeline y métodos {#sec:metodos}

![Pipeline: fuente de bits, mitigación, Peres, Toeplitz con LHL, validación y clave AES-256-GCM. Las métricas se miden en tres puntos (cruda, mitigada y clave). ZNE y PEC actúan sobre el valor esperado y no sobre los bits.](fig/pipeline.pdf){#fig:pipeline}

## Fuente de bits y origen declarado {#sec:fuente}

El circuito aplica $H^{\otimes n}$ y mide en la base computacional, con $n=8$ qubits y 400 000 disparos (3,2 M de bits crudos). La salida se ordena por qubit. La independencia entre qubits y entre disparos es una hipótesis del modelo (⚠️ sin verificar), y el *cross-talk* no está modelado. Con semilla explícita la salida de Aer es función determinista de la semilla y del circuito (S.03).

Cada muestra lleva un rótulo de origen: PRNG clásico, simulador Aer o hardware IBM. Sólo el último puede reclamar origen cuántico, y no puede construirse sin identificador de trabajo. La transacción cifrada se rotula «validación del pipeline» salvo que provenga de hardware IBM con identificador de trabajo (D-002).

## Modelo de ruido {#sec:ruido}

El modelo de lectura asimétrica usa una matriz de confusión por qubit, con $p_{10}\equiv p(1\mid0)$ y $p_{01}\equiv p(0\mid1)$. Para $H|0\rangle$ la probabilidad de leer 1 es

$$p(1)=\tfrac12+\tfrac{p(1\mid0)-p(0\mid1)}{2},\qquad \text{sesgo analítico}=\left|\tfrac{p(1\mid0)-p(0\mid1)}{2}\right|.$$

| nivel | $(p(1\mid0),\,p(0\mid1))$ | sesgo analítico |
|:-------------|:-------------------------------------------------------------|-----------------------------:|
| bajo | (0,01; 0,03) | 0,010 (el umbral de M1) |
| medio | (0,02; 0,08) | 0,030 |
| alto | (0,05; 0,15) | 0,050 |
| realista | `NoiseModel.from_backend(FakeSherbrooke())`, calibración congelada | no fijado a priori |

: Niveles de ruido de lectura, sintéticos (no medidos en hardware) y fijados antes de medir. []{#tbl:niveles}

El *cross-talk* no se modela: sin un acoplamiento medido habría que inventar parámetros. Se aceptó una consecuencia: en el nivel bajo el sesgo analítico coincide con el umbral de M1, de modo que ese nivel es un empate con el umbral y no un caso favorable.

## Mitigación de lectura propia por *twirling* {#sec:mitigacion}

Por bloque de 200 disparos y por qubit, una máscara aleatoria $m\in\{0,1\}$ decide si se aplica una puerta $X$ justo antes de medir. Tras la medición, el resultado se combina con la misma máscara mediante XOR clásico. El estado $|+\rangle$ es invariante bajo $X$, así que la distribución ideal no cambia, y el canal de lectura queda simetrizado: promediado sobre la máscara, el canal efectivo es simétrico con probabilidad de error

$$p_{\text{ef}}=\tfrac{p(1\mid0)+p(0\mid1)}{2},$$

y su sesgo para un bit uniforme vale 0 a primer orden (analítico). El canal se simetriza y persiste como ruido simétrico. El efecto sobre estados no uniformes está sin verificar (⚠️).

Como el *twirling* aplica $X$ antes de medir, la función de mitigación vuelve a ejecutar el circuito con las máscaras y marca como mitigada la muestra que devuelve. Sólo funciona sobre Aer. Un QRNG consume bits y no distribuciones, y mthree devuelve cuasi-probabilidades sin método por disparo; por eso entra únicamente como cifra de contraste (D-009). Las opciones de *twirling* y de desacoplamiento dinámico del muestreador se ejecutan en el servicio de IBM y no pueden verificarse en local (S.02). Queda sin verificar si conservan bits y cuánto mueven el sesgo (⚠️).

El *twirling* por bloques de 200 deja un sesgo local de signo aleatorio entre bloques. El sesgo global se cancela, pero las pruebas que miran estructura local (frecuencia por bloques, M5; rachas, M4) pueden detectarlo. Esta consecuencia se declaró antes de correr, motivó las enmiendas de M4 y M5 y se confirmó en E1: en la muestra mitigada, las $p$ de M4 oscilan entre $10^{-15}$ y $10^{-11}$, y las de M5 entre $10^{-8}$ y 0,002.

## ZNE y PEC frente al ruido de lectura {#sec:zne}

ZNE y PEC se definen sobre valores esperados de observables, no sobre el flujo de bits del muestreador; S.02 comprobó que las opciones del muestreador rechazan el nivel de resiliencia y las de ZNE. Aquí se aplican al observable $\langle Z\rangle=1-2p_1$ promediado sobre los qubits (ideal 0 tras H), con sesgo de bit $\lvert\langle Z\rangle\rvert/2$. Además, ambas técnicas actúan sobre ruido de puerta y no de lectura.

ZNE pliega cada $H$ en $H(HH)^k$ (factor $\lambda=1+2k$) y extrapola a ruido de puerta cero. El plegado no altera el error de medición, que ocurre una vez al final: $\langle Z\rangle$ resulta igual para todo $\lambda$ y no hay nada que extrapolar. En S.02, $\lvert\langle Z\rangle\rvert$ vale 0,0600 en los tres factores y tras extrapolar. PEC descompone la inversa del canal de puerta en operaciones base, con coste de muestreo $\gamma=\sum_k\lvert q_k\rvert>1$. Con perfil de puerta trivial, $\gamma=1$ y no hay nada que invertir. PNA y Samplomatic exigen un modelo aprendido en el servicio de IBM y no están implementados (⚠️ sin verificar).

La afirmación se prueba en lugar de asumirse: el control C4 de E2 mide si ambas técnicas mueven $\langle Z\rangle$. Las pruebas de unidad con ruido de puerta (relajación $T_1/T_2$ en la H) confirman que sí corrigen ahí, aunque no son corridas del registro y no aportan cifras.

A primer orden, el ruido de cada $H$ sólo llega a $\langle Z\rangle$ si tras él quedan un número par de $H$, porque cada $H$ intercambia $Z$ y $X$. De las $\lambda$ puertas, esto ocurre en $(\lambda+1)/2$, de modo que la escala efectiva es $s=(\lambda+1)/2$ y el cero ideal está en $s=0$ ($\lambda=-1$) y no en $\lambda=0$. Extrapolar a $\lambda=0$ deja la mitad del sesgo, lo que una prueba verifica. La relación $s(\lambda)$ se dedujo a primer orden y se contrastó con Aer para este circuito; fuera de él queda sin verificar (⚠️).

| técnica | actúa sobre | bits por disparo | corre en local | sesgo de lectura medido | papel en el pipeline |
|:-------------------------|:------------|:---------:|:----------------:|:----------------------------|:-------------|
| *Twirling* propio (X + XOR) | bitstrings | sí | sí | de 0,0299 a 0,0020 (S.02); de 0,0098–0,0505 a 0,00074–0,00131 (C.E2) | mitigador del pipeline |
| *Twirling* y desacoplamiento dinámico del muestreador | bitstrings | ⚠️ sin verificar | no (servicio IBM) | ⚠️ sin verificar | no usado |
| mthree | cuasi-probabilidades | no | sí | 0,00047–0,00192 (C.E2) | contraste, no decide |
| ZNE | valores esperados | no | implementación propia sobre ⟨Z⟩ | sin efecto, hasta 6,6 % (C.E2) | observable aparte |
| PEC / PNA | valores esperados | no | PEC con perfil conocido; PNA no | sin efecto, hasta 1,3 % (C.E2) | observable aparte |

: Comparación de técnicas de mitigación. []{#tbl:tecnicas}

## Extractor de Peres {#sec:peres}

El procedimiento de von Neumann toma pares no solapados (01 da 0, 10 da 1, y se descartan 00 y 11) y es exacto para bits IID de cualquier sesgo. Peres [4] lo itera: además de los pares distintos, recicla la secuencia de paridades ($x_{2i}\oplus x_{2i+1}$) y la de valores de los pares iguales, y aplica el procedimiento recursivamente hasta una profundidad $d$ (aquí $d=8$). La exactitud sigue requiriendo bits IID. Con dependencia, por ejemplo el sesgo local del *twirling* por bloques, la garantía no es válida de por sí, y su efecto cuantitativo queda sin verificar (⚠️).

## Hash de Toeplitz y longitud segura por LHL {#sec:toeplitz}

Dado un *pool* tras Peres y una min-entropía por bit $h_{\min}$, la longitud segura es

$$m=\left\lfloor n\,h_{\min}-2\log_2\tfrac1\varepsilon\right\rfloor,\qquad \varepsilon=2^{-64},$$

según el LHL [5,6]: al aplicar un hash universal a $n$ bits con min-entropía mayor o igual que $n h_{\min}$, los $m$ bits de salida quedan a distancia estadística menor o igual que $\varepsilon$ de la uniformidad. La pérdida fija es de 128 bits. El valor $\varepsilon=2^{-64}$ es un parámetro de diseño y no una garantía. Si $m<1$ la función aborta, de modo que no sale ni un bit y no se degrada en silencio.

El hash es $T\cdot x \bmod 2$, con $T$ de Toeplitz definida por una semilla de $n+m-1$ bits. Se calcula por FFT con redondeo, y una prueba comprueba la exactitud del redondeo a $n$ grande. La semilla sale del mismo *pool* (D-004): datos y semilla son segmentos disjuntos, con $n(2+h)\le\lvert\text{pool}\rvert$. La independencia entre ambos segmentos es una hipótesis del modelo de ruido (⚠️ sin verificar), y un adversario con acceso al *pool* queda fuera de alcance.

## Estimación de min-entropía: MCV y SP 800-90B {#sec:entropia}

El estimador MCV calcula $H_{\min}=-\log_2 p_u$ con $p_u=\min\!\big(1,\ \hat p+z\sqrt{\hat p(1-\hat p)/(n-1)}\big)$, donde $\hat p$ es la frecuencia del símbolo más común y $z=2{,}5758$ [3]. Coincide con la implementación de NIST a 6 decimales en las tres señales de S.04. Como mira sólo la frecuencia marginal, no ve la dependencia: una cadena de Markov con permanencia 0,8 (entropía real 0,322 bit/bit, analítico) da MCV 0,992 y pasa, y una secuencia periódica de ocho bits (cuatro ceros y cuatro unos) da MCV 0,996 con entropía real 0. S.04 lo mostró y C.E1d lo reprodujo en las tres semillas.

El estimador SP 800-90B (versión no-IID) se usa en su versión oficial 1.1.8, compilada fuera del repositorio y llamada como subproceso. Exige al menos $10^6$ muestras y devuelve el mínimo de diez estimadores, una cota inferior conservadora. En S.04, una fuente IID con $p(1)=0{,}7$ da 0,322 frente a 0,515 teórico (analítico). Un umbral absoluto contra este estimador resulta inválido por una propiedad del instrumento, de ahí que el control P1 sea una separación. Hoy la $h_{\min}$ de entrada que dimensiona la clave es la del MCV. Adoptar el 90B para dimensionar acortaría la clave de una fuente ideal en torno a 14 % (analítico, enmienda 2 de E1).

## Validación estadística NIST SP 800-22 {#sec:nist}

Dos validadores independientes, uno propio y nistrng 1.2.3, deben coincidir según una prueba de contrato (D-006). Las pruebas son monobit (M3), rachas (M4) y frecuencia por bloques (M5), verificadas contra los ejemplos publicados de NIST y entre sí. Una sola $p$ no constituye el criterio de SP 800-22, que es la proporción de secuencias aprobadas sobre $N$ secuencias, $1-\alpha\pm3\sqrt{\alpha(1-\alpha)/N}$ [2].

## Cifrado AES-256-GCM y reserva de claves {#sec:cifrado}

El cifrador usa clave de 256 bits y nonce de 96, y recuerda los pares (clave, nonce) para rechazar su repetición. La reserva reparte la clave en trozos consecutivos de 352 bits (256 más 96) que salen una sola vez; agotada, aborta por entropía insuficiente. Una manipulación del texto o del dato asociado produce un fallo de autenticación. El servicio de transacciones se niega a cifrar si la clave no pasa M1 a M5. La transacción (estación, tarifa, tarjeta pseudónima) es sintética y no contiene datos personales reales.

## Métricas de aceptación y aritmética de la cadena {#sec:metricas}

Los umbrales se definen en un solo lugar (D-005) con desigualdad estricta. El veredicto es conjuntivo y un veredicto vacío no aprueba. M1 a M5 se miden en tres puntos (cruda, mitigada y clave) para que Toeplitz no oculte una fuente defectuosa.

| métrica | definición | umbral |
|:-------------|:-------------------------------------------------------------------|------------------------:|
| M1 | sesgo $\lvert\hat p(1)-\tfrac12\rvert$ | $<0{,}01$ |
| M2 | min-entropía de la clave (cota MCV al 99 %), sobre bloques de 4096 bits | $>0{,}9$ bit/bit |
| M3 | NIST monobit, valor $p$ | $>0{,}01$ |
| M4 | NIST rachas, valor $p$ | $>0{,}01$ |
| M5 | NIST frecuencia por bloques, valor $p$ | $>0{,}01$ |
| M6 | tasa: bits de clave por segundo | $>10\,000$ bit/s |
| M7 | latencia de extremo a extremo (percentil 95) | $<500$ ms |

: Métricas de aceptación y umbrales (desigualdad estricta). []{#tbl:metricas}

| concepto | cuenta | resultado |
|:-------------------------|:---------------------------------------------|---------------------------------:|
| bits crudos | 8 qubits × 400 000 disparos | 3 200 000 |
| rendimiento clave/crudo | medido en la bala trazadora (Peres + Toeplitz, $h\approx0{,}995$) | ≈ 0,2988 |
| clave esperada | $3{,}2\,\text{M}\times0{,}2988$ | ≈ 956 000 bits |
| M2 por bloques | la cota MCV al 99 % exige $n\ge1288$ para superar 0,9 | bloques de 4096 |
| sesgo máximo que pasa monobit | $2{,}5758\cdot0{,}5/\sqrt N$, $N=800\,000$ | 0,00144 |
| 90B | mínimo de la herramienta | $10^6$ bits crudos |
| secuencias NIST | $956\,000/10\,240$ | 93 secuencias; proporción mínima ≈ 0,958 |

: Aritmética fijada en P.E0 antes de medir (analítico). []{#tbl:aritmetica}

Con $\hat p=0{,}5$ y $n=256$, $p_u\approx0{,}581$ y $H_{\min}\approx0{,}785$: M2 sobre una clave de 256 bits no puede superar 0,785, y por eso se mide sobre bloques de 4096. Las reglas de P.E0 establecen que, si falta muestra para una prueba, se suben los disparos sin relajar umbrales, y que M1 sobre la clave es informativo porque el monobit es más estricto a esta escala.

# Resultados {#sec:resultados}

Cada cifra procede de una corrida o de un spike nombrado, y los veredictos proceden del registro de veredictos. Lo no corrido se marca PENDIENTE y no lleva cifras ni estimaciones.

| experimento | corrida | desenlace | celdas que decidieron | observación |
|:------------|:-------------|:----------|:-------------------------|:--------------------------------------------|
| E1 | C.E1 (a a d) | CUMPLE | 3 semillas × 6 criterios | Hallazgo R.00-1: la clave sin mitigar también pasa M1 a M5 en 3/3; M4 y M5 de la mitigada fallan (informativas) |
| E2 | C.E2 | CUMPLE | 9 celdas sintéticas (K1 a K4) | ZNE y PEC sin efecto; el nivel realista no pone a prueba la mitigación; el nivel bajo coincide con el umbral de M1 |
| E3 | C.E3 | PENDIENTE | n. a. | La máquina tenía carga mayor que 1 por otros trabajos y P.E3 exige menos de 1,0 |

: Resumen de veredictos (fuente: `registro/veredictos.jsonl`). []{#tbl:veredictos}

## Spikes de viabilidad {#sec:spikes}

Los cuatro spikes son sondas de viabilidad, no experimentos preinscritos, y sostienen decisiones de diseño.

El primero (S.01) comprobó que conviven en un mismo entorno Python 3.13.14 qiskit 2.5.2, qiskit-aer 0.17.2, qiskit-ibm-runtime 0.50.0, mthree 3.0.0, nistrng 1.2.3 y cryptography 50.0.2. El segundo (S.02) midió el alcance de la mitigación con ruido (0,02; 0,08), 100 000 disparos y tres semillas: mthree pasó de 0,0299 a 0,0016 sin producir bits, el *twirling* propio de 0,0299 a 0,0020 con bits, y ZNE dejó $\lvert\langle Z\rangle\rvert$ en 0,0600; el muestreador rechaza el nivel de resiliencia.

El tercero (S.03) comprobó que Aer es pseudoaleatorio. Con la misma semilla dos corridas dan bitstrings idénticos disparo a disparo, con semillas distintas difieren, y con modelo de ruido y semilla fija la salida sigue siendo determinista. Queda sin verificar que la semilla por defecto proceda de la fuente de entropía del sistema, porque no se leyó el código fuente de C++ (⚠️). La demostración valida el pipeline y no establece entropía cuántica. El cuarto (S.04) evaluó el estimador 90B con $10^6$ bits: una fuente IID con $p(1)=0{,}7$ da 0,322 (esperado 0,515); la Markov de permanencia 0,8 da 0,170 (esperado 0,322, con MCV 0,992); la periódica de ocho bits da 0 (con MCV 0,996).

## E1: calidad de la clave con entrada ruidosa {#sec:e1}

Aer se configuró en el nivel medio (sesgo analítico 0,030), con 8 qubits y 400 000 disparos, es decir 3,2 M de bits crudos por semilla, tres semillas, $\varepsilon=2^{-64}$ y Peres de profundidad 8. Se ejecutaron cuatro corridas por semilla: PRNG clásico como control negativo (C.E1a), Aer sin mitigar (C.E1b), Aer con *twirling* (C.E1c) y fuentes sintéticas de $10^6$ bits como control positivo (C.E1d). La corrida registra como preinscripción el commit `37b89ca`, que corresponde a la última enmienda de E1.

El veredicto de E1 es CUMPLE en las tres semillas: los seis criterios que deciden (control negativo, D1, P1, B1, M-1 y M-2) se aprueban. La clave de C.E1c mide entre 956 560 y 956 905 bits (≈ 0,299 de los bits crudos), la de C.E1a entre 956 832 y 958 257, y la de C.E1b entre 954 102 y 955 434. Se sostiene la hipótesis H1.

| semilla | punto | M1 | M3 (p) | M4 (p) | M5 (p) | pasa M1 a M5 |
|:------------|:-----------------------------|------------:|----------:|-----------:|------------:|:--------------------:|
| 20261007 | C.E1b cruda | 0,0296 ✗ | 0 ✗ | 0 ✗ | 0 ✗ | no |
| 20261007 | C.E1c mitigada | 0,0004 | 0,118 | 3e-15 ✗ | 7e-5 ✗ | no (informativas) |
| 20261007 | C.E1b clave (sin mitigar) | 0,0007 | 0,165 | 0,545 | 0,610 | sí |
| 20261007 | C.E1c clave | 2e-5 | 0,965 | 0,877 | 0,522 | sí |
| 20261008 | C.E1b cruda | 0,0304 ✗ | 0 ✗ | 0 ✗ | 0 ✗ | no |
| 20261008 | C.E1c mitigada | 4e-5 | 0,896 | 6e-11 ✗ | 6e-8 ✗ | no (informativas) |
| 20261008 | C.E1b clave (sin mitigar) | 0,0003 | 0,589 | 0,698 | 0,278 | sí |
| 20261008 | C.E1c clave | 0,0005 | 0,303 | 0,097 | 0,184 | sí |
| 20261009 | C.E1b cruda | 0,0300 ✗ | 0 ✗ | 0 ✗ | 0 ✗ | no |
| 20261009 | C.E1c mitigada | 2e-5 | 0,950 | 7e-12 ✗ | 0,0020 ✗ | no (informativas) |
| 20261009 | C.E1b clave (sin mitigar) | 0,0004 | 0,490 | 0,026 | 0,958 | sí |
| 20261009 | C.E1c clave | 0,0002 | 0,753 | 0,218 | 0,590 | sí |

: E1: M1 a M5 en tres puntos por semilla (C.E1b y C.E1c). El símbolo ✗ marca un umbral incumplido (M1 menor que 0,01; $p$ mayor que 0,01). []{#tbl:e1}

![E1: M1, M3, M4 y M5 por semilla y punto de medida (C.E1a a C.E1c). Símbolo lleno: decide; hueco: informativo. Verde: pasa; bermellón: no pasa.](fig/e1_metricas.pdf){#fig:e1}

### Hallazgo R.00-1 {#sec:r001}

La clave de la corrida sin mitigación alguna también pasa M1 a M5 en las tres semillas, aunque su muestra cruda incumple las cuatro métricas por un amplio margen (M1 en 0,030 y $p=0$ en M3, M4 y M5). Peres y Toeplitz bastan para aprobar la batería. La mitigación reduce el sesgo crudo, de 0,030 a un máximo de 0,0004 en la mitigada, y no es necesaria para que la clave apruebe. Es el riesgo que la revisión R.00 había señalado: medir sólo la salida de Toeplitz haría pasar cualquier fuente. El diseño permitió observarlo porque M1 a M5 se miden en tres puntos y B1 exige que la cruda falle. Como hallazgo negativo para el papel de la mitigación, no se rechaza la hipótesis nula de que, con este ruido, la clave de la cadena mitigada y la de la cadena sin mitigar resultan indistinguibles para la batería.

### Controles y resultados informativos {#sec:e1-controles}

El PRNG clásico sin sesgo pasa M1 a M5 en la cruda y en la clave en las tres semillas, como anticipaba la decisión D-007: la batería no prueba origen cuántico. El detector D1 da diferencias $\lvert$M1 cruda $-\,0{,}030\rvert$ de 0,0004, 0,0004 y 0,00003, por debajo de 0,002. La cruda de Aer sin mitigar incumple M1 y M3 en las tres semillas, como exige B1.

M4 y M5 de la mitigada fallan en las tres semillas ($p$ entre $10^{-15}$ y $10^{-11}$ en M4, y entre $10^{-8}$ y 0,002 en M5), en coherencia con el sesgo local del *twirling* por bloques. Las enmiendas las habían declarado informativas antes de correr, a partir de un diagnóstico de escritorio. El diagnóstico se confirmó, aunque esa decisión se tomó sin una corrida registrada y la clave, no la mitigada, fue lo que decidió. La clave de C.E1c sigue pasando M1 a M5 porque Toeplitz elimina la estructura local. La proporción NIST de esa clave sobre 93 secuencias, con mínimo exigible 0,959, es M3 93/93, 92/93 y 93/93; M4 93/93, 91/93 y 92/93; M5 93/93, 90/93 y 91/93. Todas superan el mínimo y son informativas.

El 90B de la cruda (idéntica en C.E1b y C.E1c) vale 0,765, 0,766 y 0,761; el de la mitigada, 0,797, 0,796 y 0,814. La $h_{\min}$ de entrada con el estimador MCV es 0,997. El 90B decide únicamente en el control positivo.

### Control positivo con fuentes sintéticas {#sec:e1d}

Con fuentes de $10^6$ bits ([Figura](#fig:e1d)), la sesgada ($p(1)=0{,}7$) tiene 90B de 0,322 a 0,323 y falla M1, M3, M4 y M5. La periódica tiene 90B 0 y falla M4. La Markov tiene 90B de 0,170 a 0,171 y MCV de 0,992 a 0,994, y falla M4 y M5, además de M3 en la semilla 20261009. La ideal tiene 90B 0,821, 0,902 y 0,832 y pasa M1, M3, M4 y M5. El MCV de la Markov y de la periódica supera 0,99, de modo que el MCV las deja pasar y el 90B las rechaza. Que la ideal supere el piso 0,8 en las tres semillas no constituye una medida ciega (sección [5.4](#sec:enmiendas)).

![Control positivo: 90B frente a MCV para cada fuente sintética y semilla, con la entropía real analítica. Bandas: techo 0,5 (rechazo) y piso 0,8 (aceptación) del control P1.](fig/e1d_90b_vs_mcv.pdf){#fig:e1d}

## E2: mitigación y sesgo de lectura {#sec:e2}

Cada celda usa 400 000 disparos y 8 qubits, con los niveles sintéticos bajo, medio y alto más el realista (FakeSherbrooke) y tres semillas. Las técnicas son el *twirling* propio (bloque 200), mthree como contraste y, en el nivel medio, ZNE y PEC sobre ⟨Z⟩. La corrida registra como preinscripción el commit `43e2649` y 48 artefactos (16 por semilla). El veredicto es CUMPLE: K1 a K4 y los controles C1 a C5 se satisfacen en las nueve celdas sintéticas, y se sostiene la hipótesis H2 en el modelo sintético. El estadístico es la media por qubit de $\lvert\hat p_q-\tfrac12\rvert$. Su piso analítico a 400 000 disparos es $E\lvert N(0,\,0{,}5/\sqrt{400\,000})\rvert\approx0{,}0006$, y el IC95 se obtiene por bootstrap paramétrico con $B=10\,000$. El IC supone disparos independientes y puede subestimar la varianza que añade el *twirling* por bloques (⚠️).

| nivel | crudo | residuo (*twirling*) | IC95 superior | factor crudo/residuo | veredicto |
|:-------------|:--------------|:-----------------|:--------------|:-------------------------------|:----------------|
| bajo | 0,00978–0,01039 | 0,00074–0,00089 | 0,00143–0,00151 | 11,1–13,9 (K4 no aplica en 2 de 3 semillas) | decide: cumple |
| medio | 0,02958–0,03036 | 0,00086–0,00098 | 0,00153–0,00168 | 30,5–35,2 | decide: cumple |
| alto | 0,04953–0,05046 | 0,00103–0,00131 | 0,00163–0,00194 | 37,8–49,1 | decide: cumple |
| realista | 0,00046–0,00099 | 0,00036–0,00075 | 0,00113–0,00143 | 0,6–2,3 (K4 no aplica) | no decide (propio) |
| sin ruido (C2) | n. a. | 0,00078–0,00089 | hasta 0,00153 | n. a. | control: pasa |
| simétrico (C3) | n. a. | 0,00066–0,00092 | hasta 0,00155 | n. a. | control: pasa |

: E2: rango sobre las tres semillas del sesgo medio por qubit (crudo y tras el *twirling*). []{#tbl:e2}

![E2: (a) sesgo medio por qubit, crudo frente a residuo tras el *twirling*, por nivel de ruido y semilla, con IC95 y el umbral M1 (escala logarítmica); (b) cambio relativo del sesgo con ZNE y PEC en el nivel medio.](fig/e2_sesgo.pdf){#fig:e2}

En los niveles sintéticos, el *twirling* lleva el sesgo medio por qubit de 0,0098–0,0505 a 0,00074–0,00131, entre 1,2 y 2,2 veces el piso analítico de 0,0006, es decir, a la altura del ruido de muestreo. K1, K2, K3 y K4 se cumplen en las nueve celdas.

El nivel bajo coincide con el umbral. Su sesgo crudo (0,00978, 0,01039 y 0,00990) ya cumple M1 en dos de las tres semillas sin mitigar, así que dice poco sobre la mitigación. El nivel realista tampoco la pone a prueba: su sesgo crudo (0,00046–0,00099) ya está en el piso, porque el modelo de lectura del backend falso casi carece de asimetría, y el factor de 0,6 a 2,3 refleja que no hay sesgo que reducir. Ese resultado es coherente con CUMPLE y no constituye evidencia de que la mitigación funcione en el realista. Queda sin verificar que el modelo del backend aplique al circuito del *twirling* el error de puerta de la H (⚠️).

El máximo por qubit llega a 0,00336 y 0,00333 en el nivel alto (semillas 20261007 y 20261009), por encima de 0,003. El criterio K3 juzga la media y no el máximo, por lo que un qubit concreto puede quedar peor que la media. Los controles C2 (0,00078–0,00089) y C3 (0,00066–0,00092) quedan bajo 0,003, y el *twirling* no introduce sesgo; en C1, el crudo de los niveles medio y alto coincide con el analítico con diferencias de hasta 0,0005.

| técnica | semilla | crudo | tras la técnica | cambio relativo |
|:----------------|:-----------------|----------------:|----------------------------:|----------------------------:|
| ZNE | 20261007 | 0,02958 | 0,03029 | +2,4 % |
| ZNE | 20261008 | 0,03036 | 0,03054 | +0,6 % |
| ZNE | 20261009 | 0,02997 | 0,03194 | +6,6 % |
| PEC | 20261007 | 0,02958 | 0,02956 | −0,1 % |
| PEC | 20261008 | 0,03036 | 0,03077 | +1,3 % |
| PEC | 20261009 | 0,02997 | 0,02971 | −0,9 % |

: E2: ZNE y PEC sobre el sesgo de lectura (nivel medio; el estadístico es $\lvert\langle Z\rangle\rvert/2$ agregado y carece de IC). []{#tbl:zne}

ZNE y PEC no mueven el sesgo de lectura. El cambio relativo llega como máximo a 6,6 %, bajo el umbral de 10 % del control C4, y en ZNE el signo indica algo más de sesgo. El resultado coincide con lo que la preinscripción anticipó y con lo que S.02 ya había mostrado, y se reporta como «sin efecto esperado» y no como fallo. Queda sin verificar que PEC corriera con un perfil de puerta no trivial; con sólo ruido de lectura, el perfil es trivial (⚠️). Por último, mthree, que sirve de contraste y no decide, deja 0,00047–0,00192 en los niveles sintéticos. Esa cifra corresponde a cuasi-probabilidades y no se compara término a término con la del *twirling*, que conserva bits.

## E3: tasa, latencia y ciclo de cifrado {#sec:e3}

PENDIENTE: la corrida C.E3 y el veredicto de E3. La corrida no se ejecutó porque la máquina tenía carga mayor que 1 por otros trabajos, y la preinscripción exige carga previa menor que 1,0 para medir tiempos. No se reporta ninguna cifra de M6, de M7, de su desglose por etapa ni del coeficiente de variación, y tampoco se estiman. La hipótesis H3 queda sin evaluar.

Se formula una hipótesis, sin verificar (⚠️): M7 probablemente no se cumple en el perfil A, porque un lote de 3,2 M de bits con NIST y 90B sobre al menos $10^6$ bits no parece caber en 500 ms. Si ocurre, será un veredicto válido y se reportará como resultado negativo con el desglose por etapa. El lote y el perfil no se modificarán tras medir, y una optimización constituirá un experimento nuevo con preinscripción propia. Los valores de M6 y M7 que aparecen dentro de los informes de E1 son medidas internas del ejecutor y no se reportan aquí, para no confundirlos con los de E3.

## Estado de la evidencia {#sec:estado}

| bloque | corrida o nodo | estado a 2026-10-07 |
|:--------------------------------------|:----------------------------------|:-------------------------------|
| Versiones, mitigación, Aer, 90B | S.01 a S.04 (con calibración de P1) | hecho |
| E1 | C.E1a a C.E1d, E1 | juzgado: CUMPLE |
| E2 | C.E2, E2 | juzgado: CUMPLE |
| E3 | C.E3, E3 | PENDIENTE (carga de la máquina) |
| Hardware IBM real | F3.06 (F3.04 hecho) | PENDIENTE (opcional) |
| TRL por componente | T.TRL | PENDIENTE |
| Revisión adversarial del release | R.01 | PENDIENTE |
| Difusión (informe, integración, amenazas) | F7.01, F7.02, F7.04 | PENDIENTE |
| Release 0.1.0 | REL-0.1.0 | PENDIENTE |

: Estado de las evidencias. []{#tbl:estado}

# Discusión {#sec:discusion}

La evidencia reunida respalda tres afirmaciones. Primera, Aer es pseudoaleatorio (S.03), de modo que atribuirle entropía cuántica sería falso, y el diseño lo impide mediante el rótulo de origen. Segunda, ZNE y PEC no actúan sobre el error de lectura (S.02 y E2), y la mitigación del flujo de bits de un QRNG exige una técnica que conserve bits; el *twirling* con XOR clásico la proporciona. Tercera, el MCV es ciego a la dependencia y el mínimo del 90B es conservador (S.04 y control positivo de E1), por lo que ni la longitud de la clave ni los controles pueden depender de un único estimador o de un umbral absoluto.

El veredicto CUMPLE de E1 indica que la cadena entrega claves que pasan la batería con entrada ruidosa. No atribuye ese resultado a la mitigación, porque el hallazgo R.00-1 muestra que Peres y Toeplitz ya bastan. Si el objetivo es aprobar M1 a M5 con este ruido, la mitigación es prescindible. Su aporte es una muestra cruda mitigada con sesgo cercano a cero (E2) y una $h_{\min}$ de entrada algo más alta en el 90B (0,797 frente a 0,765). Dicho aporte no convierte una clave reprobada en aprobada.

SP 800-22 es una batería estadística y un PRNG la pasa, como demuestra el control negativo en el propio registro. Por eso «certificada» se define como «supera la batería y las cotas de entropía de este repositorio» y no equivale a una certificación formal ni a una prueba de origen. Medir sólo la salida tiene el mismo defecto: Toeplitz elimina lo que el ruido ensució, y por eso las métricas se toman en tres puntos y B1 exige que la cruda falle.

La mitigación por bloques resulta contraproducente para las pruebas locales. El *twirling* simetriza en media pero deja estructura local que M4 y M5 detectan, y las tres semillas lo confirman. Esta es la parte menos satisfactoria del diseño: la decisión de declarar informativas esas pruebas se tomó antes de correr y con un diagnóstico de escritorio, y marcar informativa una prueba que podía fallar admite objeciones. La decisión se atenúa porque la clave, que es lo que se cifra, se juzga con M1 a M5 completas. Queda abierto si el sesgo local degrada también a Peres, que exige independencia (⚠️ sin verificar).

El criterio de E2 se diseñó para que una celda fallida no pudiera absolverse con otras semillas, y ninguna falla. Tres hechos moderan esa lectura: el nivel bajo coincide con el umbral por construcción, el realista casi no tiene asimetría de lectura, y el piso del estadístico (≈ 0,0006) es del mismo orden que el residuo, de modo que el residuo máximo de 0,003 informa más sobre la precisión del instrumento que sobre la potencia de la técnica. La conclusión que sostienen los datos es la que la preinscripción afirma: en el modelo sintético, el *twirling* reduce el sesgo de lectura bajo M1 con holgura, sin afirmación sobre hardware real.

Los dos resultados cerrados podían haber sido negativos, y el registro los habría conservado. Esa propiedad del método, junto con el orden verificable entre preinscripción y corrida, los controles obligatorios y las desviaciones declaradas, es lo que sobrevive a cualquier resultado futuro.

# Amenazas a la validez y limitaciones {#sec:limitaciones}

## Validez de constructo {#sec:val-constructo}

El simulador no aporta entropía cuántica. Sólo el hardware puede aportarla, y aun así su origen cuántico no se certifica sin pruebas de Bell o autoverificación. «Certificada» significa «supera esta batería». El nivel de madurez tecnológica real corresponde a la afirmación más débil: la fuente cuántica en simulador es TRL 3, y subir exige una corrida en hardware IBM con identificador de trabajo. El rótulo definitivo lo derivará el nodo T.TRL, y este informe no emite ninguno.

El parámetro $\varepsilon=2^{-64}$ es una decisión de diseño y no una garantía. SP 800-90B ofrece una cota empírica, y ninguna batería equivale a una certificación FIPS o ISO.

## Validez interna {#sec:val-interna}

La calibración del control P1 se hizo con conocimiento de las semillas y con $n=11$ fuentes, tamaño que no constituye un intervalo de tolerancia; se declara como desviación del protocolo ([sección](#sec:enmiendas)). M4 y M5 de la mitigada son informativas por decisión previa a la corrida, y fallan en las tres semillas. La enmienda se apoyó en un diagnóstico de escritorio sin corrida registrada. El IC95 del sesgo supone disparos independientes y puede subestimar la varianza del *twirling* por bloques.

## Validez externa {#sec:val-externa}

Los resultados de E1 y E2 valen para el modelo de ruido sintético. E1 usa un solo nivel de ruido (el medio). El nivel realista casi carece de asimetría de lectura y no pone a prueba la mitigación, y el nivel bajo coincide con el umbral. El *cross-talk* no está modelado. Sobre hardware real no se afirma nada.

## Validez de conclusión {#sec:val-conclusion}

El hallazgo R.00-1 impide atribuir a la mitigación la aprobación de la clave. El 90B, con valores menores que el MCV, es una cota conservadora, y adoptarlo para dimensionar acortaría la clave en torno a 14 %. Con 3 semillas y 9 celdas por experimento, los veredictos son conjuntivos y no se promedian, pero el tamaño muestral no permite afirmar potencia estadística sobre el rango de ruido real.

## Alcance y limitaciones {#sec:alcance-limitaciones}

1. E3 está pendiente y no hay cifras de tasa ni de latencia. Las cifras futuras valdrán para una máquina, un hilo y un reloj, sin cola ni red de IBM Quantum, y ningún requisito externo ancla 500 ms ni 10 kbit/s.
2. La peor amenaza sin cubrir es un adversario con acceso al *pool* de semillas; también quedan fuera el canal, los canales laterales y la gestión de claves ([Tabla](#tbl:amenazas)).
3. Peres exige independencia, y el LHL aplica $n\cdot h_{\min}$ como min-entropía del bloque, una heurística estándar que con dependencia no se sigue de una estimación por muestra. La semilla de Toeplitz sale del mismo *pool*.
4. PNA y Samplomatic no están implementados; PEC corre con perfil de puerta conocido y no aprendido.
5. Las dependencias son frágiles: el binario 90B se compila fuera del repositorio (requiere red y compilador, y la optimización nativa impide portarlo entre CPU), y mthree y nistrng se fijan por versión exacta.
6. El diseño se revisó una vez de forma adversarial; la revisión del release permanece pendiente.

# Reproducibilidad {#sec:repro}

## Qué es reproducible {#sec:repro-que}

Son reproducibles el pipeline completo con semillas fijas (determinista, porque el muestreo de Aer es un PRNG), las tablas y figuras de este informe (se regeneran desde el plan, el registro de estado, el registro de veredictos y los artefactos de las corridas con un único script) y el orden de preinscripción, verificable en el historial de commits. La entropía no es reproducible por definición: en simulación, lo reproducible es lo contrario de lo que un QRNG real debe dar. Los tiempos de E3 corresponderán a una máquina y un reloj, y el binario 90B depende de la CPU.

## Entorno {#sec:repro-entorno}

Python 3.13.14 (requisito mínimo 3.11). El entorno de la corrida de E2 usó qiskit 2.5.2, qiskit-aer 0.17.2, qiskit-ibm-runtime 0.50.0, mthree 3.0.0, nistrng 1.2.3, cryptography 50.0.2, numpy 2.5.3 y scipy 1.18.1. Las versiones exactas se fijan en el fichero de bloqueo del repositorio (168 paquetes). SP 800-90B corresponde a la etiqueta v1.1.8 del repositorio de referencia de NIST.

## Disponibilidad del código y comandos {#sec:repro-comandos}

El código está en el repositorio público del proyecto (enlace en la ficha del repositorio). Desde su raíz:

```bash
uv sync --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado
bash spikes/S04_90b/build_nist.sh        # compila ea_non_iid fuera del repo (red y compilador)
./scripts/ci_local.sh                    # ruff, mypy, lint-imports, DAG y pytest

uv run --no-sync qrecauda correr declaraciones/E1.toml && uv run --no-sync qrecauda juzgar E1
uv run --no-sync qrecauda correr declaraciones/E2.toml && uv run --no-sync qrecauda juzgar E2
uv run --no-sync qrecauda correr declaraciones/E3.toml && uv run --no-sync qrecauda juzgar E3   # pendiente

.venv/bin/python docs/paper/figuras.py   # regenera docs/paper/fig/ desde plan/ y registro/
bash docs/paper/construir.sh             # regenera paper.pdf
```

Las corridas pesadas toman un candado de máquina, fuerzan BLAS a un hilo y registran el entorno en su manifiesto. E3 mide tiempo y exige una máquina libre. Dentro de una corrida, cada celda es determinista dada su semilla. Los comandos de E3 completan la cadena y no tienen resultados registrados.

## Procedencia de cifras y figuras {#sec:repro-cifras}

| cifra o figura | procede de |
|:-------------------------------------------------|:-----------------------------------------------------|
| [Figura](#fig:dag) | `plan/plan.json` y `registro/nodos.jsonl` |
| [Figura](#fig:cronologia) | historial de git; `preinscripcion_sha` en el manifiesto de cada corrida |
| [Figura](#fig:e1), [Tabla](#tbl:e1) | `registro/corridas/C.E1_<semilla>_informe_NNN.json` y `registro/veredictos.jsonl` |
| [Figura](#fig:e1d) | `registro/corridas/C.E1_<semilla>_fuente_NNN.json` |
| [Figura](#fig:e2), [Tabla](#tbl:e2), [Tabla](#tbl:zne) | `registro/corridas/C.E2_<semilla>_e2_NNN.json`, `registro/corridas/C.E2.json` |
| [Tabla](#tbl:veredictos) | `registro/veredictos.jsonl` |
| Calibración de P1 | `spikes/S04_90b/calibracion_p1.json` |
| Preinscripciones y enmiendas | `docs/preinscripciones/` y `declaraciones/` |

: Procedencia de cifras y figuras (rutas relativas a la raíz del repositorio). []{#tbl:procedencia}

# Conclusiones {#sec:conclusiones}

1. Se construyó un pipeline QRNG de punta a punta con límites declarados: el simulador valida el postprocesamiento y no aporta entropía cuántica, y «certificada» significa «supera esta batería».
2. El plan es un DAG de 59 nodos verificable por máquina. A la fecha hay 50 nodos cerrados (48 hechos y 2 juzgados), 2 listos y 7 pendientes.
3. E1 obtiene CUMPLE en las tres semillas y se sostiene H1. El hallazgo R.00-1 muestra que la clave sin mitigar también pasa M1 a M5: la mitigación mejora el sesgo crudo y no es necesaria para aprobar la batería.
4. E2 obtiene CUMPLE en las nueve celdas sintéticas y se sostiene H2 en el modelo sintético. El *twirling* propio reduce el sesgo de lectura bajo M1 con holgura, ZNE y PEC no lo modifican, el nivel realista no pone a prueba la mitigación y el nivel bajo coincide con el umbral.
5. E3, la corrida en hardware IBM, la derivación del TRL, la revisión adversarial del release y el release 0.1.0 están pendientes. H3 queda sin evaluar, y el incumplimiento de M7 es una hipótesis sin verificar (⚠️).
6. La contribución que persiste ante cualquier resultado es el método: preinscripción anterior a la corrida, controles obligatorios, enmiendas fechadas y desviaciones declaradas.

El trabajo siguiente, en este orden, consiste en correr E3 con la máquina libre y juzgarlo, derivar el TRL, realizar la revisión adversarial del release y, si hay acceso, correr en hardware IBM y comparar la mitigación del muestreador de IBM con el *twirling* propio.

# Referencias {.unnumbered}

::: refs
[1] M. Herrero-Collantes y J. C. García-Escartín, «Quantum random number generators», *Reviews of Modern Physics* **89**, 015004 (2017). DOI 10.1103/RevModPhys.89.015004.

[2] L. E. Bassham III, A. L. Rukhin, J. Soto, J. R. Nechvatal *et al.*, «A Statistical Test Suite for Random and Pseudorandom Number Generators for Cryptographic Applications», NIST Special Publication 800-22 Rev. 1a (2010). DOI 10.6028/NIST.SP.800-22r1a.

[3] M. S. Turan, E. Barker, J. Kelsey, K. A. McKay *et al.*, «Recommendation for the Entropy Sources Used for Random Bit Generation», NIST Special Publication 800-90B (2018). DOI 10.6028/NIST.SP.800-90B.

[4] Y. Peres, «Iterating von Neumann's procedure for extracting random bits», *The Annals of Statistics* **20**(1), 590–597 (1992). DOI 10.1214/aos/1176348543.

[5] R. Impagliazzo, L. A. Levin y M. Luby, «Pseudo-random generation from one-way functions», *Proc. 21st ACM STOC*, 12–24 (1989). DOI 10.1145/73007.73009.

[6] J. Håstad, R. Impagliazzo, L. A. Levin y M. Luby, «A pseudorandom generator from any one-way function», *SIAM Journal on Computing* **28**(4), 1364–1396 (1999). DOI 10.1137/S0097539793244708.

[7] H. Krawczyk, «LFSR-based hashing and authentication», en *Advances in Cryptology (CRYPTO '94)*, LNCS, 129–139. DOI 10.1007/3-540-48658-5_15.

[8] S. Pironio, A. Acín, S. Massar, A. Boyer de la Giroday *et al.*, «Random numbers certified by Bell's theorem», *Nature* **464**, 1021–1024 (2010). DOI 10.1038/nature09008.

[9] D. A. McGrew y J. Viega, «The Security and Performance of the Galois/Counter Mode (GCM) of Operation», en *Progress in Cryptology (INDOCRYPT 2004)*, LNCS, 343–355 (2004). DOI 10.1007/978-3-540-30556-9_27.

[10] M. Dworkin, «Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC», NIST Special Publication 800-38D (2007). DOI 10.6028/NIST.SP.800-38D.

[11] A. Javadi-Abhari *et al.*, «Quantum computing with Qiskit», arXiv:2405.08810 (2024). El simulador Aer se cita por su software y versión (0.17.2); no se cita un artículo propio.

[12] K. Temme, S. Bravyi y J. M. Gambetta, «Error mitigation for short-depth quantum circuits», *Physical Review Letters* **119**, 180509 (2017). DOI 10.1103/PhysRevLett.119.180509.

[13] Y. Li y S. C. Benjamin, «Efficient variational quantum simulator incorporating active error minimization», *Physical Review X* **7**, 021050 (2017). DOI 10.1103/PhysRevX.7.021050.

[14] E. van den Berg, Z. K. Minev y K. Temme, «Model-free readout-error mitigation for quantum expectation values», *Physical Review A* **105**, 032620 (2022). DOI 10.1103/PhysRevA.105.032620.

[15] P. D. Nation, H. Kang, N. Sundaresan y J. M. Gambetta, «Scalable mitigation of measurement errors on quantum computers», *PRX Quantum* **2**, 040326 (2021). DOI 10.1103/PRXQuantum.2.040326.
:::

Las referencias omitidas son el procedimiento original de von Neumann (1951) y los resultados clásicos sobre la universalidad de las matrices de Toeplitz (distintos de [7]), porque sus datos bibliográficos no pudieron contrastarse. La caracterización de Qiskit Aer como PRNG se apoya en el spike S.03 y no en una referencia externa.

# Apéndice A. Decisiones de diseño {.unnumbered}

| id | decisión |
|:-------------|:-----------------------------------------------------------------------------------------|
| D-001 | El backend es un puerto: simulador por defecto, hardware opcional |
| D-002 | El simulador no reclama origen cuántico; sólo el hardware IBM lo reclama |
| D-003 | La mitigación se aplica donde su definición tiene sentido (lectura sobre bitstrings, ZNE y PEC sobre ⟨Z⟩) |
| D-004 | Peres + Toeplitz con la semilla del mismo *pool* ($\varepsilon=2^{-64}$) |
| D-005 | M1 a M7 en un solo lugar, con desigualdad estricta; «certificada» = supera esta batería |
| D-006 | Dos validadores independientes que se contrastan |
| D-007 | Cada experimento lleva un control negativo |
| D-008 | Secretos por ruta, nunca por valor |
| D-009 | F4.01 es *twirling* de lectura propio; mthree sólo de contraste; ZNE y PEC fuera del bitstream |

: Decisiones de diseño D-001 a D-009 (`docs/decisiones/`). []{#tbl:decisiones}

# Apéndice B. Mapa de fuentes del repositorio {.unnumbered}

| tema | fuente (relativa a la raíz del repositorio) |
|:-------------------------------------------|:-----------------------------------------------------------|
| Objetivo, alcance, discrepancias | `docs/FUNDAMENTO.md` |
| Arquitectura | `docs/DISENO.md` |
| Amenazas | `docs/AMENAZAS.md` |
| Decisiones D-001 a D-009 | `docs/decisiones/` |
| Preinscripciones P.E0 a P.E3 | `docs/preinscripciones/` y `declaraciones/*.toml` |
| Spikes S.01 a S.04 | `spikes/` |
| Revisión adversarial R.00 | `docs/informes/REVISION_DISENO_R00.md` |
| Plan (DAG) | `plan/construir_dag.py` y `plan/plan.json` |
| Corridas y veredictos | `registro/corridas/`, `registro/veredictos.jsonl` |
| Estado generado | `ESTADO.md`, `registro/nodos.jsonl` |
| Figuras de este informe | `docs/paper/figuras.py` y `docs/paper/fig/` |

: Mapa de fuentes. []{#tbl:fuentes}
