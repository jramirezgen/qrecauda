---
title: "QRecauda: un pipeline de claves AES-256 sobre un generador cuántico de números aleatorios simulado, medido de extremo a extremo"
subtitle: "Mitigación de lectura, extracción, dimensionado por entropía y latencia, evaluados con cinco experimentos preinscritos"
author: kaitokid
date: "2026-10-08"
lang: es
serie: "Informe técnico · QRecauda · versión 0.2.0"
keywords: [generador cuántico de números aleatorios (QRNG), mitigación de lectura, extracción de aleatoriedad, min-entropía, NIST SP 800-90B, AES-GCM, latencia, preinscripción]
licencia: "Licencia Apache-2.0 · Código, registro de corridas y documentación públicos · Resultados obtenidos en simulador; sin corrida en hardware de IBM"
subject: "Pipeline QRNG para recaudación: método, calidad medida y resultados"
abstract: |
  Los sistemas de cobro de peajes y del Metro de Lima cifran millones de transacciones pequeñas cada día, y su seguridad exige claves que un atacante no pueda predecir. Un generador pseudoaleatorio queda determinado por su estado interno. Un generador cuántico de números aleatorios (QRNG) evita esa dependencia, pero uno simulado no aporta entropía cuántica, y una batería estadística no certifica una clave. QRecauda convierte los bits de un circuito de Hadamard sobre 8 qubits en claves AES-256-GCM mediante mitigación de lectura por *twirling*, extractor de Peres, hash de Toeplitz dimensionado con el *Leftover Hash Lemma* y validación con tres pruebas de NIST SP 800-22 y una estimación de min-entropía de SP 800-90B. Este informe mide la calidad de esa cadena de extremo a extremo sobre un simulador con ruido de lectura asimétrico, con cinco experimentos preinscritos de tres semillas cada uno.

  El *twirling* de lectura reduce el sesgo medio por qubit de 0,0098–0,0505 a 0,00074–0,00131, mientras que ZNE y PEC no modifican el sesgo de lectura (cambio máximo de 6,6 %). La clave supera las pruebas M1 a M5 en las tres semillas, pero también las supera la clave obtenida sin mitigar. Además, una fuente de Markov con min-entropía real de 0,322 bit por bit produce claves que la batería aprueba y que son de 1,2 a 2,5 veces más largas de lo que la fuente sostiene: la batería aplicada a la salida no distingue fuentes defectuosas de buenas, y el estimador de valor más común (MCV) no ve la dependencia. Un dimensionado conservador, que toma el mínimo de MCV y SP 800-90B y contabiliza la entropía de la fuente, acorta esas claves por debajo del techo teórico y conserva del 89,5 al 92,3 % de la clave de una fuente buena. Generar una clave nueva por transacción incumple el requisito de latencia (percentil 95 de 5,5 a 9,4 s frente a 500 ms). Una reserva de claves producida por un proceso aparte lo cumple: 0,17 a 0,18 ms con la reserva cebada, con una capacidad del productor de 177 a 199 kbit/s y un arranque de 6,6 s.

  Todo se midió en simulador. No hay corrida en hardware, no se afirma origen cuántico y el nivel de madurez tecnológica (TRL) del sistema es 3. Tres de los cinco experimentos tienen un poder limitado para fallar, y el informe indica por qué. Cada criterio, control y desviación se fijó o se fechó antes de la corrida, de modo que el resultado negativo de la latencia permanece en el registro. La corrida en hardware de IBM está preinscrita y pendiente de una credencial.
---

# Introducción {#sec:intro}

## Problemática {#sec:problema}

Los sistemas de cobro automático de peajes y del Metro de Lima firman, autentican y cifran millones de transacciones pequeñas al día. La seguridad de ese cifrado depende de un supuesto poco visible: las claves y los *nonces* provienen de una fuente que un atacante no puede predecir. Un generador pseudoaleatorio (PRNG) calcula su salida como función determinista de un estado interno. Quien reconstruye o roba ese estado reproduce las claves futuras y, si no hay renovación, también las pasadas. El equipo fundador lo resumió en una tesis: la aleatoriedad clásica se predice, y la recaudación del Perú no debería depender de ella.

El proyecto surgió en el *Track 4* de la Hackatón Qiskit IBM Lima, dedicado a criptoseguridad para recaudación mediante QRNG. El caso de uso consiste en cifrar con AES-256-GCM una transacción de peaje o de Metro con una clave producida por el pipeline. El repositorio no contiene ningún requisito formal de OSITRAN, del MTC ni del Metro (⚠️ sin verificar su existencia en otra fuente); los umbrales de tasa y latencia proceden del manifiesto del equipo.

Tres dificultades hacen que esta aplicación exija más que ejecutar un circuito y calcular estadísticos.

El primer problema es que un QRNG en simulador no produce entropía cuántica. El simulador de Qiskit Aer muestrea con un generador pseudoaleatorio: con la misma semilla reproduce los bitstrings disparo a disparo. Inyectarle ruido de lectura asimétrico crea sesgo realista en los bits, y ese sesgo permite someter a prueba el postprocesamiento (mitigación, extracción y validación). La fuente cuántica queda sin evaluar. Una demostración sobre simulador valida, por tanto, la cadena de procesamiento y no el origen de la aleatoriedad.

El segundo es que una batería estadística no certifica una clave. NIST SP 800-22 mide propiedades de una secuencia. Un PRNG clásico las cumple, de modo que aprobar la batería no distingue una fuente cuántica de una determinista. Hay un segundo problema de medición: los estadísticos se calculan casi siempre sobre la salida de un extractor, y un extractor bien dimensionado devuelve bits casi uniformes incluso a partir de una fuente defectuosa. Si la batería sólo mira la clave, cualquier entrada la supera.

El tercero es que el estimador de min-entropía por valor más común (MCV) no ve la dependencia. El MCV considera únicamente la frecuencia marginal del símbolo más probable. Una cadena de Markov con permanencia 0,8 tiene una min-entropía real de 0,322 bit por bit (su entropía de Shannon es 0,722) y un MCV de 0,992, de modo que el estimador la acepta. El estimador no-IID de SP 800-90B la rechaza, pero devuelve el mínimo de diez estimadores, una cota conservadora que subestima también a las fuentes ideales y que impide fijar un umbral absoluto razonable.

## Objetivos e hipótesis {#sec:objetivos}

El objetivo general es construir un pipeline QRNG reproducible y medir, con criterios fijados de antemano, siete métricas de aceptación (M1 a M7, [Tabla](#tbl:metricas)). Los objetivos específicos son tres: demostrar que la cadena entrega claves que superan la batería con entrada ruidosa y que el instrumento de medida distingue fuentes defectuosas de fuentes buenas; cuantificar cuánto reduce una mitigación de lectura el sesgo de los bits; y medir la tasa y la latencia del conjunto en una PC. A cada uno corresponde una hipótesis y un experimento preinscrito ([Tabla](#tbl:hipotesis)).

| hipótesis | enunciado | experimento | criterios preinscritos que la deciden |
|:----------|:-----------------------------------------|:-----------|:-----------------------------------------|
| H1 | Con entrada ruidosa (nivel medio de ruido de lectura, sesgo analítico 0,030), la cadena entrega una clave que cumple M1 a M5, y la medición separa fuentes defectuosas de fuentes buenas | E1 | La mitigada cumple M1 y M3 (M-1); la clave cumple M1 a M5 (M-2); la cruda sin mitigar falla M1 o M3 (B1); el detector ve el sesgo inyectado (D1); el PRNG clásico pasa la batería (control negativo del instrumento); el instrumento 90B separa las fuentes sintéticas (P1, prueba de regresión) |
| H2 | La mitigación de lectura reduce el sesgo de los bits por debajo del umbral de M1 | E2 | Por celda de nivel y semilla: residuo menor que 0,01 (K1), límite superior del IC95 menor que 0,01 (K2), residuo máximo 0,003 (K3), factor crudo/residuo mínimo 5 (K4) |
| H3 | El conjunto completo entrega más de 10 000 bit/s (M6) con latencia de extremo a extremo inferior a 500 ms (M7) | E3 | Perfil A con lote completo; percentil 95 de 30 repeticiones; controles de integridad U1 a U5 |

: Hipótesis, experimentos y criterios preinscritos. []{#tbl:hipotesis}

Antes de medir se esperaba que H1 y H2 se sostuvieran en el modelo sintético, con las salvedades que el propio diseño anticipa, y que H3 fuera la más expuesta al resultado negativo. El resultado coincide en la dirección: H1 y H2 se sostienen en lo que los criterios podían refutar (véase la [sección](#sec:discusion) sobre qué podía fallar), y H3 se sostiene sólo en la tasa (M6) y no en la latencia (M7). Los resultados están en la [sección](#sec:resultados).

## Alcance {#sec:alcance}

Este trabajo es de ingeniería y de método experimental. No afirma entropía cuántica en simulación, ni certificación FIPS o ISO, ni prueba de origen cuántico (que exigiría pruebas de Bell o autoverificación [8]), ni aptitud de las claves para producción. Tampoco incluye integración con los sistemas de OSITRAN, MTC o Metro, módulos de seguridad (HSM), distribución de claves ni multiplexado de backends. El hardware IBM real es opcional: ni la demostración ni la versión 0.1.0 dependen de él, y no hay ninguna corrida en hardware (constancia fechada en D-010: no se dispuso de credenciales de IBM Quantum).

## Contribuciones {#sec:contribuciones}

El trabajo aporta seis resultados sobre la calidad de un pipeline QRNG. Cada uno remite al experimento que lo sostiene ([Tabla](#tbl:aportes)). El símbolo ⚠ marca en el texto lo que no se ha verificado y se usa sólo como hipótesis.

| \# | contribución | experimento | sección |
|:-----|:------------------------------------|:------------------|:--------------------------|
| 1 | Mitigación de lectura que conserva los bits por disparo (*twirling* con XOR clásico), y el análisis de por qué ZNE, PEC y mthree no actúan sobre un flujo de bits | E2, spike S.02 | [N](#sec:mitigacion), [N](#sec:e2) |
| 2 | Medición de M1 a M5 en tres puntos (cruda, mitigada y clave), que muestra que la clave aprueba la batería aun sin mitigar y que la batería sobre la salida no discrimina entre fuentes | E1 | [N](#sec:e1) |
| 3 | Control negativo del pipeline completo: con el dimensionado por MCV, claves aprobadas son de 1,2 a 2,5 veces más largas de lo que la fuente sostiene; un dimensionado conservador las acorta | E5 | [N](#sec:e5) |
| 4 | Medición de latencia de extremo a extremo con desglose por etapa: el resultado negativo de generar una clave por transacción, y una arquitectura con reserva de claves que lo resuelve en simulador | E3, E3b | [N](#sec:e3), [N](#sec:e3b) |
| 5 | Calidad verificable del software: arquitectura hexagonal con siete contratos de importación ejecutables, 883 casos de prueba, dos validadores independientes que se contrastan y cifras que se regeneran desde el registro | todos | [N](#sec:calidad) |
| 6 | Un diseño experimental con preinscripción anterior a la corrida, controles obligatorios, enmiendas fechadas y revisión adversarial independiente por versión | todos | [N](#sec:preinscripcion) |

: Contribuciones y su evidencia. []{#tbl:aportes}
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

Se protege que la clave AES-256 de una transacción no sea predecible por un atacante que no observa la fuente. El sesgo de lectura y las correlaciones se tratan con mitigación, extractor de Peres y hash de Toeplitz. La longitud de la clave se calcula con la min-entropía que el estimador MCV mide sobre el *pool* que sale de Peres, porque la de salida vale casi 1 por construcción y no informa. Ese dimensionado supone bits independientes y el MCV no ve dependencia (véase [Limitaciones](#sec:limitaciones)).

## Amenazas cubiertas y no cubiertas {#sec:cubiertas}

| amenaza | tratamiento | estado |
|:-----------------------------------|:-----------------------------------|:---------------------------------|
| Sesgo del dispositivo (lectura asimétrica) | Mitigación de lectura, extractor y sesgo residual medido (M1) en tres puntos | cubierta (E1, E2) |
| Correlación entre bits | El estimador SP 800-90B no-IID mide pero no dimensiona la clave; el MCV, que sí la dimensiona, es ciego a la dependencia | no cubierta en el dimensionado por defecto; el dimensionado conservador (opt-in, E5) la cubre para tres defectos de prueba |
| Reutilización de (clave, nonce) en GCM | `ReservaDeClave` reparte trozos disjuntos de 352 bits y repetir falla | cubierta por pruebas; los controles U1 a U5 de E3 pasan en las tres semillas |
| Manipulación del texto cifrado | AES-GCM autentica; error `AutenticacionFallida` | cubierta por pruebas |
| Agotamiento de entropía | `EntropiaInsuficiente` aborta sin degradar | cubierta |
| Secretos en el repositorio | Secretos por ruta y trinquete antisecretos | cubierta |
| Origen no cuántico de la fuente | Rótulo `Origen` y control negativo con PRNG (C.E1a, sólo del instrumento) | declarada, no certificable sin hardware y pruebas de Bell |
| Canal (TLS, red) | n. a. | fuera de alcance |
| Canales laterales, volcados de memoria, dependencias comprometidas | n. a. | fuera de alcance |
| Gestión de claves (KMS, HSM) | n. a. | fuera de alcance |
| Adversario con acceso al *pool* de semillas de Toeplitz | n. a. | fuera de alcance (D-004) |
| Latencia de cola y red de IBM Quantum | n. a. | fuera de M7 |

: Amenazas que el diseño cubre y las que no. []{#tbl:amenazas}

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

El estimador MCV calcula $H_{\min}=-\log_2 p_u$ con $p_u=\min\!\big(1,\ \hat p+z\sqrt{\hat p(1-\hat p)/(n-1)}\big)$, donde $\hat p$ es la frecuencia del símbolo más común y $z=2{,}5758$ [3]. Coincide con la implementación de NIST a 6 decimales en las tres señales de S.04. Como mira sólo la frecuencia marginal, no ve la dependencia: una cadena de Markov con permanencia 0,8 (min-entropía real 0,322 bit/bit, analítico) da MCV 0,992 y pasa, y una secuencia periódica de ocho bits (cuatro ceros y cuatro unos) da MCV 0,996 con entropía real 0. S.04 lo mostró y C.E1d lo reprodujo en las tres semillas.

El estimador SP 800-90B (versión no-IID) se usa en su versión oficial 1.1.8, compilada fuera del repositorio y llamada como subproceso. Exige al menos $10^6$ muestras y devuelve el mínimo de diez estimadores, una cota inferior conservadora. En S.04, una fuente IID con $p(1)=0{,}7$ da 0,322 frente a 0,515 teórico (analítico). Un umbral absoluto contra este estimador resulta inválido por una propiedad del instrumento, de ahí que el control P1 sea una separación. Hoy la $h_{\min}$ que dimensiona la clave es la del MCV, medida sobre el *pool* que sale de Peres y no sobre la entrada. Un extractor se mide así a sí mismo, y el MCV no ve la dependencia. Adoptar el 90B para dimensionar acortaría la clave en torno a 20 a 26 % con las entradas reales (cruda 0,761–0,766 y mitigada 0,796–0,814 en E1, hasta 0,737 en E3, frente a 0,997 del MCV), y no cambia M6 (analítico). La cifra de 14 % de la enmienda 2 de E1 se calculó con la fuente ideal sintética y se sustituye por ésta.

## Validación estadística NIST SP 800-22 {#sec:nist}

Dos validadores independientes, uno propio y nistrng 1.2.3, deben coincidir según una prueba de contrato (D-006). Las pruebas son monobit (M3), rachas (M4) y frecuencia por bloques (M5), tres de las 15 de SP 800-22, verificadas contra los ejemplos publicados de NIST y entre sí. Faltan, entre otras, las pruebas espectrales, la entropía aproximada y las seriales, que verían estructura periódica o local; por eso la expresión «validación NIST SP 800-22» se refiere a este subconjunto. M1 y M3 son esencialmente el mismo estadístico (la frecuencia de unos). La frecuencia por bloques de nistrng usa unos 99 bloques, de unos 32 000 bits sobre la muestra cruda de 3,2 M, muy lejos de los 200 bits del *twirling*. Con unos 30 valores $p$ decisivos a $\alpha=0{,}01$ en E1 y sin corrección por comparaciones múltiples, y con una proporción de secuencias de la que sólo se evalúa la cota inferior, el resultado de la batería no es una validación de la clave. El estimador 90B no la valida: sus valores (0,74 a 0,81) quedan por debajo de 0,9 y el criterio informativo 90B figura como no cumplido (`cumple: false`) en los tres veredictos de E1. Una sola $p$ no constituye el criterio de SP 800-22, que es la proporción de secuencias aprobadas sobre $N$ secuencias, $1-\alpha\pm3\sqrt{\alpha(1-\alpha)/N}$ [2].

## Cifrado AES-256-GCM y reserva de claves {#sec:cifrado}

El cifrador usa clave de 256 bits y nonce de 96, y recuerda los pares (clave, nonce) para rechazar su repetición. La reserva reparte la clave en trozos consecutivos de 352 bits (256 más 96) que salen una sola vez; agotada, aborta por entropía insuficiente. Una manipulación del texto o del dato asociado produce un fallo de autenticación. El servicio de transacciones se niega a cifrar si la clave no pasa M1 a M5. La transacción (estación, tarifa, tarjeta pseudónima) es sintética y no contiene datos personales reales.

## Métricas de aceptación y aritmética de la cadena {#sec:metricas}

Los umbrales se definen en un solo lugar (D-005) con desigualdad estricta. El veredicto es conjuntivo y un veredicto vacío no aprueba. M1 a M5 se miden en tres puntos (cruda, mitigada y clave) para que Toeplitz no oculte una fuente defectuosa.

| métrica | definición | umbral |
|:-------------|:-------------------------------------------------------------------|------------------------:|
| M1 | sesgo $\lvert\hat p(1)-\tfrac12\rvert$ | $<0{,}01$ |
| M2 | min-entropía de la clave (cota MCV al 99 %); preinscrita como mediana sobre bloques de 4096 bits, medida sobre la clave entera | $>0{,}9$ bit/bit |
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

**Desviación declarada en M2.** La preinscripción pide la mediana de bloques de 4096 bits, con el mínimo aparte. La implementación calcula la cota MCV sobre la clave entera (unos 956 000 bits), y la corrida registra 0,994 a 0,996 en lugar del valor esperado de ≈ 0,943 por bloques. La desviación favorece el resultado por la holgura del tamaño mayor. No cambia el veredicto, porque 0,943 también supera 0,9, y debió declararse por enmienda y no sustituirse en silencio. M2 sobre la salida de Toeplitz vale casi 1 por construcción y no informa sobre la fuente.

# Diseño experimental {#sec:preinscripcion}

Cada experimento se fija por escrito antes de correr: hipótesis, métricas, umbrales, controles y qué desenlaces son posibles. Esta sección describe el protocolo, los controles y los criterios; las enmiendas y las desviaciones, con su fecha y su commit, están en el apéndice D.

## Protocolo de preinscripción {#sec:que-preinscribir}

La regla 5 del documento de fundamento obliga a fijar el umbral y el criterio de cada experimento antes de la corrida. El protocolo opera en cinco pasos.

1. La preinscripción en prosa y su declaración legible por máquina entran en un commit.
2. La corrida registra en su manifiesto el commit de la preinscripción y el del código.
3. El juez se niega a veredictar si ese commit no precede a la corrida, si el documento cambió después o si falta o falla un control (error de salida 9).
4. Un control fallido significa que la medición no es válida: no se emite veredicto y se abre una incidencia.
5. Un resultado negativo cierra el experimento como negativo; reintentar exige una preinscripción nueva y el veredicto anterior se conserva.

Un error detectado antes de correr se corrige con una enmienda fechada, en commit propio y anterior a la corrida; después de correr, el documento no se modifica. Las semillas (20261007, 20261008 y 20261009) son identificadores enteros y no fechas, se declaran de antemano, y elegir una semilla está prohibido: el veredicto se emite sobre las tres. Son tres muestras de un generador determinista, no tres réplicas físicas: prueban determinismo y no repetibilidad física.

![Cronología de preinscripciones, enmiendas, código del ejecutor y corridas con veredicto (hora de commit; eje cortado entre 19:30 y 21:30 del 2026-10-07, y panel aparte para el 2026-10-08). Cada preinscripción precede a su corrida; las enmiendas de E3 del 2026-10-08 son anteriores a C.E3.](fig/cronologia.pdf){#fig:cronologia}

La [Figura](#fig:cronologia) muestra el orden real, leído de los commits. El juez comprueba por máquina que el commit de la preinscripción es ancestro de la corrida.

## Controles positivos y negativos {#sec:controles}

Cada experimento tiene controles sin los cuales no hay veredicto. Un control negativo comprueba que la batería acepta lo que debe aceptar, incluido un PRNG clásico. Un control positivo comprueba que el detector reconoce lo que se inyecta ([Tabla](#tbl:controles)).

| experimento | control | tipo | qué comprueba |
|:---------------|:--------------|:----------------------|:------------------------------------------------------|
| E1 | N1 (C.E1a) | negativo | El PRNG clásico sin sesgo y sin mitigación pasa M1 a M5: la batería no prueba origen cuántico (D-007) |
| E1 | D1 | positivo | El detector ve el sesgo inyectado: $\lvert$M1 cruda $-\,0{,}030\rvert\le0{,}002$ |
| E1 | P1 (C.E1d) | positivo (prueba de regresión) | El instrumento separa lo bueno de lo malo, con piso calibrado sobre las mismas semillas: sesgada, periódica y Markov bajo el techo 0,5 del 90B, ideal sobre el piso 0,8, MCV de la Markov $\ge0{,}9$ |
| E1 | B1 | positivo | La cruda de Aer ruidoso debe fallar M1 o M3 con el ruido declarado |
| E2 | C1 | positivo | $\lvert$crudo $-$ analítico$\rvert\le0{,}002$ en los niveles medio y alto |
| E2 | C2 | negativo | *Twirling* sin ruido: residuo $\le0{,}003$ |
| E2 | C3 | negativo | *Twirling* con canal simétrico (0,05; 0,05): residuo $\le0{,}003$ |
| E2 | C4 | puerta | ZNE o PEC «sin efecto» si mueven $\langle Z\rangle$ menos de 10 % |
| E2 | C5 | contraste | mthree como cifra de contraste, sin decidir |
| E3 | U1 a U5 | positivo y negativo | Ida y vuelta 1 000/1 000; alteración de 1 bit detectada al 100 %; clave ajena falla al 100 %; ningún par (clave, nonce) repetido; rótulos «validación del pipeline» |
| E3b | T4, U1 a U5 | positivo y negativo | Un hilo por proceso (cpu/pared $\le1{,}10$); ida y vuelta; *nonces* distintos; ningún par (clave, *nonce*) ni clave repetidos; ninguna clave en la bitácora ni en el informe; rótulo «validación del pipeline» y origen `simulador_aer` |
| E5 | D5, P5 | positivo y de igualdad | D5: el 90B de la muestra cruda ve el defecto (menos de 0,5 en las tres defectuosas, al menos 0,7 en la buena). P5: los tres dimensionados de una fuente y semilla parten de la misma muestra (igual sha256). Si fallan, la corrida es INVÁLIDA |

: Controles de los experimentos. Un control fallido invalida la corrida. []{#tbl:controles}

La tasa de falsa alarma del control negativo es $1-0{,}99^{18}\approx0{,}165$ por las 18 pruebas a $\alpha=0{,}01$ (analítico, con supuesto de independencia ⚠️). Se aceptó a priori. Si ocurre, la corrida es inválida y no se repite con otra semilla. Contando las 18 pruebas del control negativo, las 9 de M-2 y las 3 de M3 sobre la mitigada, E1 tiene unas 30 comparaciones aleatorias decisivas a $\alpha=0{,}01$ sin corrección por comparaciones múltiples: una falla espuria en un pipeline correcto ronda $1-0{,}99^{30}\approx0{,}26$ (analítico, con supuesto de independencia ⚠️), cifra que no se había reportado.

**Alcance de los controles.** En E1, el control negativo lo es del instrumento: una fuente defectuosa (sesgada, periódica, Markov) es rechazada por el 90B y por la batería. En la versión 0.1.0 el pipeline completo carecía de un control negativo equivalente, hueco que cierra E5 (sección [E5](#sec:e5)): tres fuentes con dependencia atraviesan la cadena entera y el dimensionado conservador las acorta, mientras que el de 0.1.0 no. En una prueba de la revisión R.01, una fuente de Markov con min-entropía real de 0,322 bit por bit atravesó el pipeline y produjo una clave de unos 756 kbit, unas tres veces más de lo que la fuente sostiene, que pasa M3, M4 y M5 en las tres semillas, porque el dimensionado usa MCV sobre el *pool* y supone bits independientes. Entonces era una limitación declarada y no un hallazgo de las corridas del registro; E5 la midió después en el registro y la mitigación (dimensionar con el mínimo de MCV y 90B más la contabilidad de la entropía de la fuente) es opt-in. P1 se calibró con las mismas semillas del experimento (piso 0,8, techo 0,5): es una prueba de regresión del instrumento y no un control con poder para invalidar E1. U1 a U3 de E3 comprueban propiedades de AES-GCM más que del código del proyecto; sólo U4 y U5 dependen de él.

## Criterios por experimento {#sec:criterios}

| experimento | afirma | criterios que deciden | informativos |
|:---------|:--------------------------------|:--------------------------------|:--------------------------------|
| E1 | Con entrada ruidosa (Aer, nivel medio, sesgo analítico 0,030) la cadena entrega una clave que cumple M1 a M5 y la medición distingue fuentes malas de buenas | C.E1a, D1, P1, B1; M-1: la mitigada pasa M1 y M3; M-2: la clave pasa M1 a M5 | M4 y M5 de la mitigada (por enmienda), 90B de la cruda y la mitigada, proporción NIST de la clave, resultado de la clave sin mitigar |
| E2 | Con ruido de lectura asimétrico inyectado, la mitigación baja el sesgo bajo M1 | Por celda (9 celdas sintéticas de nivel y semilla): K1 residuo $<0{,}01$; K2 IC95 superior $<0{,}01$; K3 residuo $\le0{,}003$; K4 crudo/residuo $\ge5$ si crudo $\ge0{,}01$ | Nivel realista (veredicto propio, fuera de la conjunción); mthree; ZNE y PEC |
| E3 | El conjunto en una PC con Aer entrega M6 $>10\,000$ bit/s y M7 $<500$ ms, con una transacción cifrada | Perfil A (lote completo de 3,2 M de bits): M6 y M7 (percentil 95 de 30 repeticiones), U1 a U5 | Perfil B (reserva ya generada, 1 000 transacciones); no puede rescatar un perfil A fallido |
| E3b | Con la clave de una reserva generada aparte, la transacción cumple M7 mientras el productor sostiene M6 y supera el consumo | T1 (tasa neta mayor que 10 000 bit/s y que el consumo), T2 (p95 menor que 500 ms), T3 (cero esperas, reserva no agotada); controles T4 y U1 a U5 | R1 (arranque), mediana, p99, máximo, cambios de clave, claves rechazadas, CPU de cada proceso |
| E5 | El pipeline completo acorta o rechaza la clave de una fuente con dependencia, sin dañar a la fuente buena | D por fuente (clave bajo el techo teórico K1 y bajo el 25 % de la buena), G1 a G3 (la buena pasa M1 a M5, conserva al menos el 75 % y M6 mayor que 10 000 bit/s); controles D5 y P5 | HOY con `mcv` y con `min_mcv_90b`; efecto sobre M6 |

: Criterios preinscritos de cada experimento. []{#tbl:criterios}

Tras ver un resultado registrado, ningún experimento puede relajar un umbral, repetirse con otra semilla ni mover una métrica a informativa; las excepciones que hubo, todas anteriores a la corrida registrada pero algunas posteriores a un ensayo o a un diagnóstico sin registro, están listadas en el apéndice D. Los desenlaces posibles son CUMPLE, NO CUMPLE, NULO, CUMPLE PARCIAL e INVÁLIDA, y esta última corresponde al error de corrida inválida.

## Enmiendas y desviaciones {#sec:enmiendas-resumen}

Hubo nueve enmiendas fechadas ([Tabla](#tbl:enmiendas), apéndice D). Ocho son anteriores a la corrida registrada a la que afectan y ninguna cambia un umbral de M1 a M7; la novena es de redacción y posterior a la corrida de E3. Dos enmiendas cambian el estatus de una métrica (M4 y M5 de la muestra mitigada pasan de decisivas a informativas) y dos cambian un umbral de control. Tres de ellas, del mismo día que la corrida de E3, se hicieron tras un primer intento real que tropezó con la carga de la máquina y con una clave rechazada; la primera semilla completa de ese intento se descartó sin conservar cifras, un grado de libertad del investigador que se declara aquí. El control P1 de E1 se calibró con las semillas declaradas, de modo que es una prueba de regresión del instrumento y no un control con poder.

# Resultados {#sec:resultados}

Cada cifra procede de una corrida o de un spike nombrado, y los veredictos proceden del registro de veredictos. Lo no corrido se marca PENDIENTE y no lleva cifras ni estimaciones. Los resultados cerrados son los de E1, E2, E3, E3b y E5.

| experimento | corrida | desenlace | celdas que decidieron | observación |
|:------------|:-------------|:----------|:-------------------------|:--------------------------------------------|
| E1 | C.E1 (a a d) | CUMPLE | 3 semillas × 6 criterios | Hallazgo R.00-1: la clave sin mitigar también pasa M1 a M5 en 3/3; M4 y M5 de la mitigada fallan en 3/3 (informativas por enmienda; sin ellas, CUMPLE PARCIAL) |
| E2 | C.E2 | CUMPLE | 9 celdas sintéticas (K1 a K4) | K4 es analítico; ZNE y PEC sin efecto; el nivel realista no pone a prueba la mitigación; el nivel bajo coincide con el umbral de M1 |
| E3 | C.E3 | NO CUMPLE | 3 semillas × 2 criterios (T1, T2) | M6 cumple (T1) y M7 no (T2) en las tres semillas; T4 y los controles U1 a U5 pasan |
| E3b | C.E3b | CUMPLE | 3 semillas × 3 criterios (T1 a T3) | otro diseño, con preinscripción propia y no comparable con E3: p95 de 0,17 a 0,18 ms con la reserva cebada, capacidad del productor de 177 a 199 kbit/s (entregado, 47,8 kbit/s), cero esperas; arranque informado aparte; T4 y U1 a U5 pasan |
| E5 | C.E5 | CUMPLE | 3 semillas × (D por fuente, G1 a G3) | control negativo del pipeline completo; con `mcv` las nueve claves defectuosas pasan M1 a M5 y exceden el techo; D5 y P5 pasan |

: Resumen de veredictos (fuente: `registro/veredictos.jsonl`). []{#tbl:veredictos}

## Spikes de viabilidad {#sec:spikes}

Los cuatro spikes son sondas de viabilidad, no experimentos preinscritos, y sostienen decisiones de diseño.

El primero (S.01) comprobó que conviven en un mismo entorno Python 3.13.14 qiskit 2.5.2, qiskit-aer 0.17.2, qiskit-ibm-runtime 0.50.0, mthree 3.0.0, nistrng 1.2.3 y cryptography 50.0.2. El segundo (S.02) midió el alcance de la mitigación con ruido (0,02; 0,08), 100 000 disparos y tres semillas: mthree pasó de 0,0299 a 0,0016 sin producir bits, el *twirling* propio de 0,0299 a 0,0020 con bits, y ZNE dejó $\lvert\langle Z\rangle\rvert$ en 0,0600; el muestreador rechaza el nivel de resiliencia.

El tercero (S.03) comprobó que Aer es pseudoaleatorio. Con la misma semilla dos corridas dan bitstrings idénticos disparo a disparo, con semillas distintas difieren, y con modelo de ruido y semilla fija la salida sigue siendo determinista. Queda sin verificar que la semilla por defecto proceda de la fuente de entropía del sistema, porque no se leyó el código fuente de C++ (⚠️). La demostración valida el pipeline y no establece entropía cuántica. El cuarto (S.04) evaluó el estimador 90B con $10^6$ bits: una fuente IID con $p(1)=0{,}7$ da 0,322 (esperado 0,515); la Markov de permanencia 0,8 da 0,170 (esperado 0,322, con MCV 0,992); la periódica de ocho bits da 0 (con MCV 0,996).

## E1: calidad de la clave con entrada ruidosa {#sec:e1}

Aer se configuró en el nivel medio (sesgo analítico 0,030), con 8 qubits y 400 000 disparos, es decir 3,2 M de bits crudos por semilla, tres semillas, $\varepsilon=2^{-64}$ y Peres de profundidad 8. Se ejecutaron cuatro corridas por semilla: PRNG clásico como control negativo (C.E1a), Aer sin mitigar (C.E1b), Aer con *twirling* (C.E1c) y fuentes sintéticas de $10^6$ bits como control positivo (C.E1d). La corrida registra como preinscripción el commit `37b89ca`, que corresponde a la última enmienda de E1.

El veredicto de E1 es CUMPLE en las tres semillas: los seis criterios que deciden (control negativo, D1, P1, B1, M-1 y M-2) se aprueban. La clave de C.E1c mide entre 956 560 y 956 905 bits (≈ 0,299 de los bits crudos), la de C.E1a entre 956 832 y 958 257, y la de C.E1b entre 954 102 y 955 434. H1 se sostiene en lo que los criterios podían refutar, con las condiciones de abajo: el CUMPLE depende de que M4 y M5 de la mitigada sean informativas, porque fallan en las tres semillas, y sin esas enmiendas E1 habría sido CUMPLE PARCIAL (M-2 pasa y M-1 falla). B1, D1 y el control negativo comprueban que la manipulación existe y que el instrumento acepta lo que debe; M-2 se cumple casi por construcción, por Toeplitz.

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

El 90B de la cruda (idéntica en C.E1b y C.E1c) vale 0,765, 0,766 y 0,761; el de la mitigada, 0,797, 0,796 y 0,814, todos por debajo de 0,9. La $h_{\min}$ de entrada con el estimador MCV es 0,997. El 90B decide únicamente en el control positivo y no gobierna la longitud de la clave.

### Control positivo con fuentes sintéticas {#sec:e1d}

Con fuentes de $10^6$ bits ([Figura](#fig:e1d)), la sesgada ($p(1)=0{,}7$) tiene 90B de 0,322 a 0,323 y falla M1, M3, M4 y M5. La periódica tiene 90B 0 y falla M4. La Markov tiene 90B de 0,170 a 0,171 y MCV de 0,992 a 0,994, y falla M4 y M5, además de M3 en la semilla 20261009. La ideal tiene 90B 0,821, 0,902 y 0,832 y pasa M1, M3, M4 y M5. El MCV de la Markov y de la periódica supera 0,99, de modo que el MCV las deja pasar y el 90B las rechaza. Que la ideal supere el piso 0,8 en las tres semillas no constituye una medida ciega (apéndice D).

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

En los niveles sintéticos, el *twirling* lleva el sesgo medio por qubit de 0,0098–0,0505 a 0,00074–0,00131, entre 1,2 y 2,2 veces el piso analítico de 0,0006, es decir, a la altura del ruido de muestreo. K1, K2, K3 y K4 se cumplen en las nueve celdas. El resultado es una propiedad algebraica: el *twirling* anula el sesgo global por construcción, y K4 (factor mínimo 5) era un orden de magnitud esperado de antemano. Además el estadístico es agregado por qubit y no por bloque. En una simulación de la revisión R.01 (sesgo local de signo aleatorio de ±0,03 en bloques de 200, fuera del registro ⚠️), el agregado queda en ≈ 0,0004 mientras la media por bloque de $\lvert\hat p-\tfrac12\rvert$ vale 0,038: el sesgo local coexiste con un agregado casi nulo, y es lo que detectan M4 y M5 en E1. El nivel bajo es un no-op en 2 de 3 semillas, y E2 no tiene un control con fuente determinista que muestre que el *twirling* no enmascara una fuente sin entropía.

El nivel bajo coincide con el umbral. Su sesgo crudo (0,00978, 0,01039 y 0,00990) ya cumple M1 en dos de las tres semillas sin mitigar, así que dice poco sobre la mitigación. El nivel realista tampoco la pone a prueba: su sesgo crudo (0,00046–0,00099) ya está en el piso, porque el modelo de ruido que construye `from_backend` simetriza la lectura por qubit, y el factor de 0,6 a 2,3 refleja que no hay sesgo que reducir. Eso describe al modelo y no a los dispositivos: las calibraciones del propio backend sí traen asimetría de lectura, de modo que no se afirma que los backends reales carezcan de ella. Distinguir «ruido no aplicado» de «ruido sin asimetría» exigiría otra configuración. Ese resultado es coherente con CUMPLE y no constituye evidencia de que la mitigación funcione en el realista. Queda sin verificar que el modelo del backend aplique al circuito del *twirling* el error de puerta de la H (⚠️). En la celda realista de la semilla 20261009 el residuo medio (0,00036) cae fuera de su propio IC95 (0,00038 a 0,00113): la media de $\lvert\hat p_q-\tfrac12\rvert$ está sesgada al alza cerca del piso.

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

La corrida C.E3 mide el perfil A (la cadena completa con el lote de 3,2 M de bits crudos: fuente de Aer con ruido medio, *twirling*, Peres y Toeplitz, validación M1 a M5 en tres puntos más el 90B, y una transacción cifrada y descifrada) en 30 repeticiones por semilla tras 3 de calentamiento descartadas, a un hilo y con candado de máquina. La máquina es un AMD Ryzen 9 7900X3D de 20 núcleos lógicos bajo WSL2; la corrida registra Python 3.13.14, qiskit 2.5.2 y qiskit-aer 0.17.2. Los tiempos valen para esa máquina y ese reloj. La preinscripción es el commit `41cd058`, la última enmienda de E3, y precede a la corrida. El veredicto es **NO CUMPLE** y el juez nombra los tres incumplimientos: T2 (M7) en cada una de las semillas. T1 (M6), T4 (validez de un hilo) y los controles U1 a U5 se cumplen.

| semilla | M6 (bit/s) | M7: p95 de $t_{rep}$ (ms) | M7 / 500 ms | mediana (ms) | mínimo (ms) | máximo (ms) | CV de $t_{rep}$ | claves rechazadas |
|:---------|-----------:|--------------:|---------:|-----------:|-----------:|-----------:|---------:|:----------------|
| 20261007 | 187 438 | 9 378 ✗ | 18,8 | 4 737 | 4 518 | 9 844 | 0,244 (inestable) | 3 (2 medidas) |
| 20261008 | 195 465 | 5 554 ✗ | 11,1 | 4 710 | 4 457 | 9 205 | 0,172 | 1 (1 medida) |
| 20261009 | 180 466 | 5 547 ✗ | 11,1 | 5 273 | 5 061 | 5 587 | 0,028 | 0 |

: E3, perfil A: M6 y M7 por semilla (fuente: `registro/corridas/C.E3_<semilla>_e3_000.json`). M6 cumple en las tres semillas (cociente a umbral 18,7; 19,5 y 18,0); M7 incumple en las tres (✗). Las claves rechazadas cuentan las 33 repeticiones, calentamiento incluido; entre paréntesis, las de las 30 medidas. []{#tbl:e3}

**M6 cumple y M7 no.** La tasa excede 18 veces el umbral porque una repetición entrega unos 957 000 bits de clave (de 955 799 a 957 489 en las 90 repeticiones medidas) en unos cinco segundos. La latencia es otra magnitud: una transacción que pide una clave nueva espera ese ciclo completo. Aun la repetición más rápida de cada semilla (4 518, 4 457 y 5 061 ms) supera 8,9 veces el umbral, de modo que el incumplimiento no depende de la cola de la distribución. El coeficiente de variación de $t_{rep}$ de la semilla 20261007 (0,244) supera el 0,2 que la preinscripción manda reportar como medida inestable; no invalida la corrida.

![E3: (a) mediana del tiempo por etapa del ciclo completo, apilada, frente al umbral de M7; (b) $t_{rep}$ de cada repetición medida (escala logarítmica), con el p95 de cada semilla (punteado) y las repeticiones con clave regenerada (hueco).](fig/e3_latencia.pdf){#fig:e3}

**Dónde se va el tiempo.** La [Tabla](#tbl:e3etapas) y la [Figura](#fig:e3) descomponen $t_{rep}$ por etapa. La mitigación por *twirling* consume el 47 a 49 % y la fuente de Aer otro 28 %: entre ambas, tres cuartas partes del ciclo, y las dos corren 400 000 disparos por circuito. La validación (NIST más 90B) ocupa el 18 %, la extracción el 6 a 7 %, y el cifrado de la transacción 0,19 ms, el 0,004 % del ciclo. Ni la extracción ni el cifrado son el cuello. La suma de las medianas por etapa (4 721, 4 686 y 5 275 ms) no coincide exactamente con la mediana de $t_{rep}$ porque la mediana de una suma no es la suma de las medianas.

| etapa | 20261007 | 20261008 | 20261009 |
|:------------------------|-------------------:|-------------------:|-------------------:|
| fuente (Aer) | 1 327 (28,1 %) | 1 330 (28,4 %) | 1 460 (27,7 %) |
| mitigación (*twirling*) | 2 224 (47,1 %) | 2 209 (47,1 %) | 2 559 (48,5 %) |
| extracción (Peres y Toeplitz) | 324 (6,9 %) | 299 (6,4 %) | 301 (5,7 %) |
| validación (M1 a M5 y 90B) | 846 (17,9 %) | 848 (18,1 %) | 954 (18,1 %) |
| cifrado y descifrado | 0,19 (< 0,1 %) | 0,19 (< 0,1 %) | 0,19 (< 0,1 %) |

: E3: mediana por etapa en ms y fracción de la suma de medianas (fuente: `reporte.etapas_ms` de cada corrida). []{#tbl:e3etapas}

**Claves rechazadas.** Cuatro de las 99 repeticiones (33 por semilla, calentamiento incluido) generaron una clave que no pasó M1 a M5 y se regeneraron: 3, 1 y 0 por semilla. Cada regeneración duplica aproximadamente $t_{rep}$ (9 205 a 9 844 ms en las tres repeticiones medidas con rechazo, frente a unos 4 700), porque el intento rechazado suma al tiempo. En la semilla 20261007 el p95 (9 378 ms) coincide con una de esas repeticiones; en las semillas 20261008 y 20261009 el p95 corresponde a una repetición sin rechazo. Una proporción de 4 en 99 es del orden del 3 % que implica $\alpha=0{,}01$ en tres pruebas (analítico, con supuesto de independencia ⚠️). La regla no favorece a M7: descartar el intento en silencio habría reducido las cifras, y contarlo las aumenta.

**Perfil B: la reserva de claves.** El perfil B mide el ciclo de una transacción con la reserva ya generada (`siguiente`, `cifrar` y `descifrar`) sobre 1 000 transacciones, 500 de peaje y 500 de Metro. La mediana es de 14,9 µs (semillas 20261007), 15,1 µs (20261008) y 21,7 µs (20261009), con p95 de 17,9, 17,9 y 38,7 µs, y una tasa de 63 638, 62 626 y 30 667 transacciones por segundo. La semilla 20261009 es la más lenta y la causa no se investigó (⚠️ sin verificar). **El perfil B no decide.** Con una reserva ya cargada, cifrar una transacción cuesta microsegundos y no milisegundos, pero eso describe un diseño que genera las claves por adelantado, y ese diseño no se ha validado: queda sin medir cada cuánto se repone la reserva, qué latencia ve una transacción cuando la reserva se agota y cómo se protege la reserva en memoria. Una cuenta analítica ilustra el orden de magnitud: con M6 entre 180 466 y 195 465 bit/s y 352 bits por transacción (clave de 256 bits y nonce de 96), la cadena repondría entre 513 y 555 transacciones por segundo, y un lote de unos 957 000 bits alcanza para unas 2 700 (analítico, sin medición propia). El perfil B no puede rescatar un perfil A fallido, y no se usa para suavizar el veredicto.

**Controles.** Los controles pasan en las tres semillas: ida y vuelta de las 1 000 transacciones (U1), detección de la alteración de un bit del texto cifrado y del dato asociado (U2), fallo con la clave de otra transacción (U3), ningún par (clave, nonce) repetido (U4) y rótulo «validación del pipeline» en todas las transacciones, sin «entropía cuántica» (U5). La validez de un hilo (T4) también se cumple.

**Lectura.** Generar una clave por transacción no cumple el requisito de latencia de 500 ms: el ciclo cuesta entre once y diecinueve veces el umbral, y reducirlo exigiría un lote menor o un cambio de arquitectura, no un ajuste de parámetros. La hipótesis H3 se sostiene a medias: M6, sí; M7, no. La expectativa preinscrita ya señalaba el perfil A como candidato a no cumplir M7, y el resultado la confirma con un margen amplio. Ni el lote ni el perfil se modificaron tras medir. Reducir el lote, mover la mitigación fuera del camino de la transacción o precargar claves constituye un experimento nuevo con preinscripción propia (E3b), y el veredicto actual se conserva en el registro.

## E3b: latencia con la clave de una reserva generada aparte {#sec:e3b}

E3b es una pregunta distinta de la de E3. E3 midió una transacción cuya clave se generaba dentro de ella y no cumplió. E3b pregunta si, cuando la clave sale de una reserva que un proceso productor genera en paralelo, la latencia de la transacción cumple M7 (p95 < 500 ms) mientras el productor sostiene M6 (> 10 000 bit/s) y supera el consumo declarado. No reabre E3 ni lo rescata: **el veredicto de E3 (NO CUMPLE) queda en el registro**, y el perfil B de E3 no se usó como evidencia. La preinscripción (`docs/preinscripciones/E3b.md`, commit `88d1d45`) precede a la corrida y fija los umbrales, el perfil que decide y el que no.

El diseño tiene dos procesos, cada uno fijado a su núcleo y con BLAS a un hilo. El productor corre la cadena de E3 (Aer con ruido medio, *twirling*, Peres, Toeplitz, validación M1 a M5 y 90B), regenera la clave si se rechaza y la deposita en una cola acotada a dos claves, con contrapresión. El consumidor toma trozos de 352 bits (clave de 256 y *nonce* de 96) con el registro de consumo, de modo que ningún par (clave, *nonce*) sale dos veces, y cifra y descifra una transacción con AES-256-GCM. El cambio de clave ocurre dentro de la transacción que lo provoca y cuenta en su latencia. El perfil que decide (R2) fija una demanda de 100 transacciones por segundo durante 120 s (12 000 transacciones, 35 200 bit/s de clave) con llegadas programadas en lazo abierto, de modo que cualquier retraso del consumidor entra en la latencia de las siguientes. El arranque (R1) se informa aparte y no decide. La demanda es declarada por el equipo: ningún operador la midió.

El veredicto es **CUMPLE** en las tres semillas. Los criterios que deciden son T1 (tasa neta del productor mayor que 10 000 bit/s y mayor que el consumo), T2 (M7) y T3 (cero esperas y reserva no agotada); T4 (un hilo por proceso) y los controles U1 a U5 pasan. T2 era casi trivial: con 100 transacciones por segundo y una latencia media de 0,11 ms (calculada de las 12 000 latencias de cada artefacto), el consumidor está ocupado alrededor del 1 % del tiempo, y en cada semilla sólo 4 de las 12 000 transacciones cambian de clave. El riesgo del experimento estaba en T1 y T3.

| semilla | M7: p95 (ms) | mediana (ms) | p99 (ms) | máximo (ms) | capacidad del productor (bit/s) | esperas | arranque R1 (ms) |
|:---------|------------:|------------:|--------:|-----------:|-------------:|-------:|-----------------:|
| 20261007 | 0,1737 | 0,0986 | 0,237 | 2,02 | 177 989 | 0 | 6 560 |
| 20261008 | 0,1809 | 0,1021 | 0,239 | 1,38 | 177 084 | 0 | 6 553 |
| 20261009 | 0,1686 | 0,0993 | 0,234 | 4,21 | 199 262 | 0 | 6 677 |

: E3b, perfil R2 (12 000 transacciones por semilla; fuente: `registro/corridas/C.E3b_<semilla>_e3b_000.json` y `registro/veredictos.jsonl`). El umbral de M7 es 500 ms; el cociente a umbral del p95 es de 0,0003 a 0,0004. El umbral de tasa es 10 000 bit/s y el consumo declarado, 35 200 bit/s. []{#tbl:e3b}

![E3b: (a) percentil 95 de la latencia por transacción en E3 (generar y cifrar la clave) y en E3b (cifrar con una reserva ya cebada), escala logarítmica; las dos magnitudes no son equivalentes. (b) Distribución de las 36 000 latencias de E3b (tres semillas).](fig/e3b_latencia.pdf){#fig:e3b}

**Qué dice y qué no.** La latencia de una transacción con la reserva cebada es de décimas de milisegundo. No es comparable con el p95 de E3: E3 mide generar y cifrar la clave dentro de la transacción (5,5 a 9,4 s), y E3b sólo cifrar con una clave ya generada; una transacción que llegue durante el arranque de la reserva espera unos 6,6 s, y eso incumpliría M7. El máximo de unos 1,4 a 4,2 ms y los cuatro cambios de clave por semilla (de 0,5 a 1,4 ms cada uno) también quedan lejos del umbral. La tasa neta de 177 a 199 kbit/s (entre 5,0 y 5,7 veces el consumo) es la capacidad del productor; lo que entregó en régimen durante la ventana (`reporte.tasa_entregada_ventana_bps`) fue de 47,8 kbit/s en las tres semillas, 1,36 veces el consumo de 35,2 kbit/s. La reserva nunca se agotó. El costo se trasladó, no desapareció: el arranque tarda de 6,6 a 6,7 s hasta tener la primera clave, y el productor usa entre el 31 y el 34 % de un núcleo (el consumidor, el 15 %). Hubo una clave rechazada por M1 a M5 en las semillas 20261007 y 20261008 (se regeneró) y ninguna en la 20261009.

**Limitaciones declaradas.** (1) Todo se midió sobre simulador y no incluye la cola ni la red de IBM Quantum. (2) La demanda de 100 transacciones por segundo y los umbrales de 500 ms y 10 kbit/s vienen del manifiesto del equipo; ningún requisito externo los ancla (⚠️ sin verificar). (3) Las claves se generan con el dimensionado `mcv` de 0.1.0, el que E5 mostró que sobrestima con fuentes dependientes; **E3b no se re-midió con el dimensionado conservador** y no se sabe cómo cambiaría su latencia ni su tasa (⚠️ sin verificar). (4) Una reserva en memoria es un depósito de claves: aumenta la exigencia de custodia, que el repositorio no cubre. (5) Tres semillas de un generador determinista no son réplicas físicas. (6) No se probó con una demanda alta ni con arranques en frío distintos de los tres medidos.

## E5: control negativo del pipeline completo {#sec:e5}

La revisión R.01 dejó sin cubrir un hueco: el pipeline completo carecía de un control negativo, y el dimensionado con MCV es ciego a la dependencia. E5 (`docs/preinscripciones/E5.md`, commit `7a05bea`, anterior a la corrida) lo cierra con una fuente buena (Aer con ruido medio y *twirling*, como en E1) y tres fuentes con dependencia entre bits, que atraviesan la cadena entera: *twirling*, Peres, Toeplitz, validación M1 a M5 y 90B. El defecto se aplica después de la lectura y del *twirling* reales, de modo que llega al extractor ya contaminado; el *twirling* atraviesa la cadena pero no ve el defecto. Las fuentes son `markov` (persistencia 0,8), `markov_fuerte` (persistencia 0,9) y `periodica` (semideterminista sobre el patrón `00001111`, peso 0,9). Cada una se corre con tres dimensionados y tres semillas (20261007 a 20261009), lo que da doce muestras de 3,2 M de bits crudos, cada una dimensionada de tres maneras.

| dimensionado | cómo calcula la entropía con que dimensiona la clave |
|:---------------|:-----------------------------------------------|
| `mcv` (0.1.0) | cota MCV sobre el *pool* de Peres entero |
| `min_mcv_90b` | mínimo de MCV y 90B sobre los primeros $10^6$ bits del *pool* |
| `conservador` (decide) | lo anterior y además la contabilidad de la fuente: la entropía total del *pool* no puede superar la de la muestra cruda de la que salió, medida con 90B |

: E5: los tres dimensionados. El conservador es opt-in; por defecto el pipeline sigue con `mcv`. []{#tbl:e5dim}

El veredicto es **CUMPLE** en las tres semillas. Decide el lado defectuoso (D: en las tres fuentes, la clave queda bajo el techo teórico K1 de la fuente y bajo el 25 % de la clave de la fuente buena, K2) y el lado bueno (G1: la fuente buena entrega una clave que pasa M1 a M5; G2: conserva al menos el 75 % de la clave que daría `mcv`; G3: M6 de la cadena entera mayor que 10 000 bit/s). D5 y P5 pasan como controles. El techo K1 sale de la teoría: la entropía mínima por bit de una fuente con persistencia $w$ y sesgo $p=0{,}51$ es $-\log_2(w+(1-w)p)$, multiplicada por los bits crudos.

| fuente | 90B de la muestra cruda | `mcv` (bits) | `min_mcv_90b` (bits) | `conservador` (bits) | techo K1 (bits) |
|:--------------|-----------:|-----------:|-----------:|-----------:|-----------:|
| buena | 0,796 a 0,814 | 956 560 a 956 905 | 856 258 a 885 035 | 856 258 a 883 109 | n/a |
| markov | 0,077 | 553 904 a 555 024 | 396 912 a 403 325 | 114 233 a 114 548 | 476 162 |
| markov_fuerte | 0,036 a 0,037 | 380 324 a 381 142 | 275 672 a 281 531 | 55 363 a 56 321 | 231 944 |
| periodica | 0,082 a 0,083 | 586 676 a 587 183 | 152 961 a 157 456 | 122 460 a 123 227 | 231 944 |

: E5: bits de clave por fuente y dimensionado, rango de las tres semillas (fuente: `registro/corridas/C.E5_<semilla>_e5_NNN.json`; el techo K1, de `registro/veredictos.jsonl`). []{#tbl:e5}

![E5: bits de clave por fuente y dimensionado (media de tres semillas y rango), escala logarítmica. La marca horizontal es el techo teórico de cada fuente defectuosa.](fig/e5_dimensionado.pdf){#fig:e5}

**Hallazgo R.00-1 en cadena completa.** Con el dimensionado de 0.1.0, las nueve claves de fuentes defectuosas (tres fuentes por tres semillas) pasan M1 a M5 y las nueve superan el techo K1. El cociente de la clave `mcv` a K1 va de 1,2 (markov) y 1,6 (markov_fuerte) a 2,5 (periodica), calculado con las cifras de la tabla y los techos del veredicto. Es la medida que faltaba: la batería no detecta el defecto, y una clave aprobada por M1 a M5 puede tener entre 1,2 y 2,5 veces más bits que los que la fuente sostiene. Es el criterio HOY del veredicto, que informa y no decide.

**Qué corrige el dimensionado conservador.** Con el conservador, las tres fuentes defectuosas entregan claves entre el 24 y el 53 % de K1 y el conservador las acorta de 55 a 123 mil bits; la fuente buena conserva del 89,5 al 92,3 % de la clave que daría `mcv` (de 856 a 883 mil bits), y la cadena entera mantiene M6 entre 133 y 158 kbit/s. **`min(MCV, 90B)` por sí solo no alcanza:** con `min_mcv_90b`, la fuente `markov_fuerte` sigue por encima de K1 en las tres semillas (de 1,19 a 1,21 veces su techo), porque Peres reparte la dependencia por el *pool* y el 90B del *pool* da valores moderados aunque la muestra cruda dé 0,04. Por eso el dimensionado conservador suma la contabilidad de la entropía de la fuente.

**Límites.** (1) E5 prueba tres defectos de dependencia con respuesta analítica conocida; un defecto adversarial que imite a una fuente independiente ante los estimadores no se prueba. (2) K1 es una condición necesaria, no suficiente: una clave bajo el techo no queda por ello demostrada segura. (3) El prefijo de $10^6$ bits del *pool* no es representativo del *pool* entero (empieza por la parte de von Neumann); la contabilidad cubre ese hueco, no lo elimina. (4) Los umbrales de D (K2, 0,25) y G2 (0,75) se fijaron con un diagnóstico previo sobre un generador sustituto, no con las semillas de la corrida. (5) **El dimensionado conservador es opt-in y no se re-midieron E3 ni E3b con él** (⚠️ sin verificar su efecto sobre la latencia y la tasa). (6) Nada de esto dice algo sobre origen cuántico: las fuentes son Aer, un PRNG, más un defecto sintético. (7) E5 es casi un control por construcción: las fuentes defectuosas se eligieron detectables por el 90B (control D5); el lado «rechazada» nunca se ejerce, porque las 36 claves de E5 pasan M1 a M5 y el pipeline acorta la clave en lugar de rechazarla; y K2 y G2 se fijaron tras un diagnóstico con el mismo generador de defectos que luego se corrió.

## Estado de la evidencia {#sec:estado}

| bloque | corrida o nodo | estado a 2026-10-08 |
|:--------------------------------------|:----------------------------------|:-------------------------------|
| Versiones, mitigación, Aer, 90B | S.01 a S.04 (con calibración de P1) | hecho |
| E1 | C.E1a a C.E1d, E1 | juzgado: CUMPLE |
| E2 | C.E2, E2 | juzgado: CUMPLE |
| E3 | C.E3, E3 | juzgado: NO CUMPLE (M7) |
| E3b | C.E3b, E3b | juzgado: CUMPLE (otro diseño; simulador) |
| E5 | C.E5, E5 | juzgado: CUMPLE (control negativo del pipeline completo) |
| Camino a hardware IBM | F3.07, P.E4; C.E4 bloqueado | listo y ensayado contra un backend falso; sin credencial, ningún resultado en hardware real |
| Hardware IBM real | F3.06 (F3.04 hecho) | F3.06 cerrado como constancia de no acceso (D-010); sin corrida en hardware |
| TRL por componente | T.TRL | hecho: TRL del sistema 3 (`docs/TRL.md`) |
| Difusión (informe, pitch, amenazas, roadmap) | F7.01, F7.02, F7.04 | hecho |
| Revisión adversarial del release 0.1.0 | R.01 | hecho; tres informes recibidos, hallazgos corregidos o declarados (sección [R.01](#sec:r01)) |
| Release 0.1.0 | REL-0.1.0 | publicado |
| Revisión y release 0.2.0 | R.02, REL-0.2.0 | hecho: versión 0.2.0 publicada (tag `v0.2.0`, `docs/releases/EXPEDIENTE_0.2.0.md`) |

: Estado de las evidencias. []{#tbl:estado}

# Calidad del software y reproducibilidad {#sec:calidad}

Esta sección resume cómo se mantuvo la calidad de la cadena en el código y cómo puede reproducirse cada cifra.

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
| C5b | Los bordes (API, composición, entrada, transversal) no importan un SDK directamente | Que el borde sortee el confinamiento de C5 |
| C6 | Lo transversal es hoja | Ciclos con configuración y errores |

: Contratos de importación (siete: C1 a C5, C5b y C6) verificados con import-linter. []{#tbl:contratos}

Sobre los siete contratos operan trinquetes por AST: ninguna captura silenciosa de excepciones genéricas, lectura del entorno sólo en configuración, ninguna credencial en el código, ninguna aleatoriedad global en el dominio, y lo vendorizado sin divergencias. Un trinquete sólo puede apretarse, de modo que un caso nuevo que lo viole rompe la CI. Una prueba siembra un import prohibido para comprobar que el contrato falla cuando debe, porque un contrato que nunca falla no demuestra nada. Un hook de commit rechaza mensajes con atribución automática de autoría.

## Desarrollo guiado por pruebas {#sec:tdd}

La prueba precede a la implementación, y cada decisión de diseño con consecuencia verificable tiene una prueba que la fija. La suite de la versión 0.2.0 recoge 883 casos de prueba, repartidos por capa: dominio, adaptadores, aplicación, arquitectura, transversales, integración y datos. Entre ellas figuran: Toeplitz por FFT exacto a $n\ge2\cdot10^5$ y coincidente con la matriz densa módulo 2; los validadores NIST propio y de nistrng contrastados entre sí y con los vectores publicados; el cifrador contra el vector oficial de GCM; la aritmética de ZNE sobre la escala efectiva; y el control negativo de la propia arquitectura. La CI local (ruff, mypy en modo estricto, import-linter, comprobaciones del DAG y pytest) se ejecuta antes de empujar, y un hook de push la exige.

## Plan, registro y documentación como material suplementario {#sec:suplementario}

El repositorio incluye el plan del proyecto como grafo verificable (79 nodos, once reglas comprobadas por máquina, apéndice C), un registro de sólo añadir con el estado de cada nodo y los artefactos de cada corrida, y una wiki de documentación que se publica como bóveda de Obsidian. Los tres se comparten para que un tercero pueda auditar el orden entre preinscripción y corrida y recalcular cada cifra de este informe. Ninguno hace falta para entender los resultados.

## Qué es reproducible {#sec:repro-que}

Son reproducibles el pipeline completo con semillas fijas (determinista, porque el muestreo de Aer es un PRNG), las tablas y figuras de este informe (se regeneran desde el plan, el registro de estado, el registro de veredictos y los artefactos de las corridas con un único script) y el orden de preinscripción, verificable en el historial de commits. La entropía no es reproducible por definición: en simulación, lo reproducible es lo contrario de lo que un QRNG real debe dar. Los tiempos de E3 corresponden a una máquina y un reloj, y el binario 90B depende de la CPU.

## Entorno {#sec:repro-entorno}

Python 3.13.14 (requisito mínimo 3.11). El entorno de la corrida de E2 usó qiskit 2.5.2, qiskit-aer 0.17.2, qiskit-ibm-runtime 0.50.0, mthree 3.0.0, nistrng 1.2.3, cryptography 50.0.2, numpy 2.5.3 y scipy 1.18.1. Las versiones exactas se fijan en el fichero de bloqueo del repositorio (168 paquetes). SP 800-90B corresponde a la etiqueta v1.1.8 del repositorio de referencia de NIST.

## Disponibilidad del código y comandos {#sec:repro-comandos}

El código está en el repositorio público del proyecto (enlace en la ficha del repositorio). Desde su raíz:

```bash
uv sync --frozen --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado
bash spikes/S04_90b/build_nist.sh        # compila ea_non_iid fuera del repo (red y compilador)
./scripts/ci_local.sh                    # ruff, mypy, lint-imports, DAG y pytest

uv run --no-sync qrecauda correr declaraciones/E1.toml && uv run --no-sync qrecauda juzgar E1
uv run --no-sync qrecauda correr declaraciones/E2.toml && uv run --no-sync qrecauda juzgar E2
uv run --no-sync qrecauda correr declaraciones/E3.toml && uv run --no-sync qrecauda juzgar E3   # exige máquina libre
uv run --no-sync qrecauda correr declaraciones/E3b.toml && uv run --no-sync qrecauda juzgar E3b # exige máquina libre
uv run --no-sync qrecauda correr declaraciones/E5.toml && uv run --no-sync qrecauda juzgar E5

.venv/bin/python docs/paper/figuras.py   # regenera docs/paper/fig/ desde plan/ y registro/
bash docs/paper/construir.sh             # regenera paper.pdf
```

Las corridas pesadas toman un candado de máquina, fuerzan BLAS a un hilo y registran el entorno en su manifiesto. E3 mide tiempo y exige una máquina libre (carga previa menor que 2,0 y un hilo). Dentro de una corrida, cada celda es determinista dada su semilla; los tiempos de E3 no lo son, y repetir la medición dará cifras distintas dentro de la variación que el propio informe reporta.

## Procedencia de cifras y figuras {#sec:repro-cifras}

| cifra o figura | procede de |
|:-------------------------------------------------|:-----------------------------------------------------|
| [Figura](#fig:dag) | `plan/plan.json` y `registro/nodos.jsonl` |
| [Figura](#fig:cronologia) | historial de git; `preinscripcion_sha` en el manifiesto de cada corrida |
| [Figura](#fig:e1), [Tabla](#tbl:e1) | `registro/corridas/C.E1_<semilla>_informe_NNN.json` y `registro/veredictos.jsonl` |
| [Figura](#fig:e1d) | `registro/corridas/C.E1_<semilla>_fuente_NNN.json` |
| [Figura](#fig:e2), [Tabla](#tbl:e2), [Tabla](#tbl:zne) | `registro/corridas/C.E2_<semilla>_e2_NNN.json`, `registro/corridas/C.E2.json` |
| [Figura](#fig:e3), [Tabla](#tbl:e3), [Tabla](#tbl:e3etapas) | `registro/corridas/C.E3_<semilla>_e3_000.json` (campos `reporte.etapas_ms`, `reporte.t_rep_ms`, `reporte.perfil_b`), `registro/corridas/C.E3.json` y `registro/veredictos.jsonl` |
| [Tabla](#tbl:e3b) | `registro/corridas/C.E3b_<semilla>_e3b_000.json`, `registro/corridas/C.E3b.json` y `registro/veredictos.jsonl` |
| [Tabla](#tbl:e5), [Tabla](#tbl:e5dim) | `registro/corridas/C.E5_<semilla>_e5_NNN.json`, `registro/corridas/C.E5.json` y `registro/veredictos.jsonl` (el techo K1) |
| [Tabla](#tbl:veredictos) | `registro/veredictos.jsonl` |
| Constancia de no acceso a hardware IBM | `docs/decisiones/D-010.md` |
| Calibración de P1 | `spikes/S04_90b/calibracion_p1.json` |
| Preinscripciones y enmiendas (E1, E2, E3, E3b, E4 y E5) | `docs/preinscripciones/` y `declaraciones/` |

: Procedencia de cifras y figuras (rutas relativas a la raíz del repositorio). []{#tbl:procedencia}

# Discusión {#sec:discusion}

La evidencia reunida respalda tres afirmaciones. Primera, Aer es pseudoaleatorio (S.03), de modo que atribuirle entropía cuántica sería falso, y el diseño lo impide mediante el rótulo de origen. Segunda, ZNE y PEC no actúan sobre el error de lectura (S.02 y E2), y la mitigación del flujo de bits de un QRNG exige una técnica que conserve bits; el *twirling* con XOR clásico la proporciona. Tercera, el MCV es ciego a la dependencia y el mínimo del 90B es conservador (S.04 y control positivo de E1), por lo que ni la longitud de la clave ni los controles pueden depender de un único estimador o de un umbral absoluto.

El veredicto CUMPLE de E1 indica que la cadena entrega claves que pasan la batería con entrada ruidosa. No atribuye ese resultado a la mitigación, porque el hallazgo R.00-1 muestra que Peres y Toeplitz ya bastan. Si el objetivo es aprobar M1 a M5 con este ruido, la mitigación es prescindible. Su aporte es una muestra cruda mitigada con sesgo agregado cercano a cero (E2) y una $h_{\min}$ de entrada algo más alta en el 90B (0,797 frente a 0,765, ambas por debajo de 0,9). Dicho aporte no convierte una clave reprobada en aprobada.

SP 800-22 es una batería estadística y un PRNG la pasa, como demuestra el control negativo en el propio registro. Por eso «certificada» se define como «supera la batería y las cotas de entropía de este repositorio» y no equivale a una certificación formal ni a una prueba de origen. Medir sólo la salida tiene el mismo defecto: Toeplitz elimina lo que el ruido ensució, y por eso las métricas se toman en tres puntos y B1 exige que la cruda falle.

La mitigación por bloques resulta contraproducente para las pruebas locales. El *twirling* simetriza en media pero deja estructura local que M4 y M5 detectan, y las tres semillas lo confirman. Esta es la parte menos satisfactoria del diseño: la decisión de declarar informativas esas pruebas se tomó antes de la corrida registrada y con un diagnóstico de escritorio, y marcar informativa una prueba que podía fallar admite objeciones. Con la preinscripción original, en la que M4 y M5 de la mitigada decidían, E1 habría sido CUMPLE PARCIAL. La decisión se atenúa porque la clave, que es lo que se cifra, se juzga con M1 a M5 completas. Queda abierto si el sesgo local degrada también a Peres, que exige independencia (⚠️ sin verificar).

El criterio de E2 se diseñó para que una celda fallida no pudiera absolverse con otras semillas, y ninguna falla. Cuatro hechos moderan esa lectura: el *twirling* anula el sesgo global por álgebra, el nivel bajo coincide con el umbral por construcción, el modelo de ruido realista simetriza la lectura y no pone a prueba la mitigación, y el piso del estadístico (≈ 0,0006) es del mismo orden que el residuo, de modo que el residuo máximo de 0,003 informa más sobre la precisión del instrumento que sobre la potencia de la técnica. La conclusión que sostienen los datos es la que la preinscripción afirma: en el modelo sintético, el *twirling* reduce el sesgo de lectura bajo M1 con holgura, sin afirmación sobre hardware real.

E3 es el resultado negativo. La preinscripción lo había señalado como el más probable, y el registro lo conserva sin ajustes: el criterio, el lote y el perfil son los fijados antes de medir. Dos lecturas se separan. Con una clave generada por transacción, la latencia de 5 a 9 s excluye el requisito de 500 ms, y la causa dominante es la ejecución del circuito de Aer con 400 000 disparos y la mitigación por *twirling*, que juntas suman tres cuartas partes del ciclo. Con una reserva de claves ya cargada, el ciclo de cifrado cuesta decenas de microsegundos, pero esa cifra del perfil B describe sólo una operación de AES-GCM y no responde a la pregunta de latencia del sistema completo. Esa pregunta se hizo después, con otro diseño y su propia preinscripción (E3b): con un proceso productor que genera las claves en paralelo, la latencia de la transacción es de décimas de milisegundo y el productor sostiene la demanda declarada. El costo se trasladó al arranque (de 6,6 a 6,7 s) y a la custodia de una reserva en memoria, y E3b sólo vale para simulador y con claves del dimensionado `mcv`. Que M6 supere el umbral 18 veces mientras M7 lo incumple 11 a 19 veces muestra que ambas métricas miden cosas distintas: el sistema produce claves con rapidez suficiente y las entrega tarde. Ninguna de las dos cifras tiene un requisito externo que la ancle (⚠️ sin verificar).

De los tres primeros resultados, sólo E3 podía fallar de verdad, y falló. E3b y E5 cumplieron, con matices: T2 (M7) de E3b era casi trivial por la baja utilización, y el riesgo estaba en T1 y T3; E5 es casi un control por construcción, porque sus fuentes defectuosas eran detectables por el 90B y el lado «rechazada» nunca se ejerce; E5, además, midió con su lado informativo (HOY) que el dimensionado de 0.1.0 fallaría el control negativo, y E3b no tiene un control equivalente sobre la dimensión de las claves que consume. Ninguno de los dos se ha repetido sobre hardware. En E1 y E2, B1, D1 y K4 son identidades analíticas del *twirling*: el sesgo global baja a 0 por álgebra, de modo que no podían salir negativos. Lo que sí podía fallar en ellos era M2 a M5, la separación de fuentes por el instrumento y el residuo local, y M4 y M5 de la mitigada fallaron. El sesgo local de unos 0,038 por bloque (simulación de la revisión R.01, fuera del registro) coexiste con 0,0004 agregado. Esa distinción, junto con el orden verificable entre preinscripción y corrida, los controles y las desviaciones declaradas, es lo que sobrevive a cualquier resultado futuro.

# Amenazas a la validez y limitaciones {#sec:limitaciones}

## Validez de constructo {#sec:val-constructo}

El simulador no aporta entropía cuántica. Sólo el hardware puede aportarla, y aun así su origen cuántico no se certifica sin pruebas de Bell o autoverificación. «Certificada» significa «supera esta batería». El nivel de madurez tecnológica real corresponde a la afirmación más débil: la fuente cuántica en simulador es TRL 3, y subir exige una corrida en hardware IBM con identificador de trabajo. El nodo T.TRL lo derivó en `docs/TRL.md`: TRL del sistema 3, la fila más baja. Los TRL 4 por componente de esa matriz se apoyan en los CUMPLE de E1, E2 y E5, con las salvedades de este informe; E3b queda en 3 (4 sólo con la reserva cebada).

El parámetro $\varepsilon=2^{-64}$ es una decisión de diseño y no una garantía. SP 800-90B ofrece una cota empírica, y ninguna batería equivale a una certificación FIPS o ISO.

## Validez interna {#sec:val-interna}

La calibración del control P1 se hizo con conocimiento de las semillas y con $n=11$ fuentes, tamaño que no constituye un intervalo de tolerancia; se declara como desviación del protocolo (apéndice D). M4 y M5 de la mitigada son informativas por decisión previa a la corrida registrada, y fallan en las tres semillas. La enmienda se apoyó en un diagnóstico de escritorio sin corrida archivada (la cifra de 7 de 8 semillas que cita la preinscripción no tiene artefacto), y sin ella E1 sería CUMPLE PARCIAL. Tres semillas consecutivas de un generador determinista no son réplicas físicas. El IC95 del sesgo supone disparos independientes y puede subestimar la varianza del *twirling* por bloques.

## Validez externa {#sec:val-externa}

Los resultados de E1 y E2 valen para el modelo de ruido sintético. E1 usa un solo nivel de ruido (el medio). El modelo de ruido realista simetriza la lectura y no pone a prueba la mitigación (no se afirma que los dispositivos reales carezcan de asimetría), y el nivel bajo coincide con el umbral. El *cross-talk* no está modelado. Sobre hardware real no se afirma nada.

## Validez de conclusión {#sec:val-conclusion}

El hallazgo R.00-1 impide atribuir a la mitigación la aprobación de la clave. El 90B, con valores menores que el MCV, es una cota conservadora, y adoptarlo para dimensionar acortaría la clave entre 20 y 26 % (90B de la muestra cruda de E1 frente al MCV, en la fuente de E1); en E5, con el 90B del *pool* (`min_mcv_90b`) y la fuente buena, el acortamiento es de 7,5 a 10,5 %, porque el *pool* tras Peres es una magnitud distinta de la muestra cruda; E5 midió el efecto del dimensionado conservador sobre fuentes defectuosas y sobre la buena. Con 3 semillas y 9 celdas por experimento, los veredictos son conjuntivos y no se promedian, pero el tamaño muestral no permite afirmar potencia estadística sobre el rango de ruido real. E1 acumula unos 30 valores $p$ decisivos a $\alpha=0{,}01$ sin corrección. Filtrar claves con una batería (E3 regenera las rechazadas, cerca de 4 %) es una práctica desaconsejada porque reduce el espacio de claves; el efecto es del orden de 0,06 bit y se documenta.

## Alcance y limitaciones {#sec:alcance-limitaciones}

1. Las cifras de E3 y E3b valen para una máquina, un reloj y, en E3, un hilo (en E3b, un hilo por proceso), sin cola ni red de IBM Quantum, y ningún requisito externo ancla 500 ms ni 10 kbit/s. La causa de la mayor lentitud del perfil B en la semilla 20261009 no se investigó, y la carga previa de la máquina (menos de 2,0) incluyó un proceso ajeno de un hilo.
2. La peor amenaza sin cubrir es un adversario con acceso al *pool* de semillas; también quedan fuera el canal, los canales laterales y la gestión de claves ([Tabla](#tbl:amenazas)).
3. Peres exige independencia, y el LHL aplica $n\cdot h_{\min}$ como min-entropía del bloque, una heurística estándar que con dependencia no se sigue de una estimación por muestra. La semilla de Toeplitz sale del mismo *pool*. El dimensionado por defecto usa MCV sobre el *pool* y supone bits independientes: una fuente de Markov de min-entropía 0,322 produjo una clave de unos 756 kbit, unas tres veces más de lo que sostiene, que pasa M3 a M5, y E5 lo midió en cadena completa (de 1,2 a 2,5 veces). El dimensionado conservador lo corrige en tres defectos de prueba con respuesta analítica, pero es opt-in, no cubre un defecto adversarial y no se re-midieron E3 ni E3b con él.
4. PNA y Samplomatic no están implementados; PEC corre con perfil de puerta conocido y no aprendido.
5. Las dependencias son frágiles: el binario 90B se compila fuera del repositorio (requiere red y compilador, y la optimización nativa impide portarlo entre CPU), y mthree y nistrng se fijan por versión exacta.
6. El diseño se revisó (R.00) y el release se revisó con tres informes independientes (R.01); sus hallazgos se resumen en la sección siguiente y siguen abiertos los que no se declaran corregidos.
7. No hay corrida en hardware IBM (D-010); el camino está listo (`qrecauda hardware`, preinscripción P.E4) y C.E4 espera una credencial. El origen cuántico de las claves no se afirma, y el TRL de la fuente cuántica queda en el que sostiene el simulador (3).
8. El diseño con reserva de claves se validó sólo en simulador (E3b): sin cola ni red de IBM, con una demanda declarada por el equipo, con claves del dimensionado `mcv`, y con una reserva en memoria que es un depósito de claves y aumenta la exigencia de custodia. El perfil B de E3 mide una operación sobre una reserva ya cargada y no decide.
9. La batería es un subconjunto de 3 de las 15 pruebas de SP 800-22, y el 90B no valida la clave.
10. La política ante una clave rechazada difiere entre E1 (INVÁLIDA) y E3 (regeneración), y una corrida de E3 se descartó sin conservar cifras.

# Revisión adversarial independiente (R.01 y R.02) {#sec:r01}

Antes del release, tres revisores independientes leyeron el repositorio en el commit `f1e8c3b` y recalcularon cifras del registro. No encontraron discrepancias numéricas en las tablas de E1, E2 y E3, y confirmaron que el veredicto de E3 es sólido. Sus notas globales fueron 6,0 sobre 10 (afirmaciones y estadística), 6,0 (código) y 5,5 (coherencia documental).

| hallazgo | revisor | disposición |
|:----------------------------------------------|:---------|:----------------------------------------------|
| Reutilización de (clave, nonce) AES-GCM entre servicios sobre la misma clave; U4 no la veía | código | bloqueante, corregido |
| El CUMPLE de E1 depende de M4 y M5 informativas; B1, D1 y K4 son identidades analíticas | estadística | matizado en el resumen, la discusión y el pitch |
| El pipeline aprueba y dimensiona una clave de ≈ 3 veces lo que sostiene una fuente de Markov (MCV ciego) | estadística | limitación declarada en 0.1.0; medida en cadena completa y mitigada por E5 (dimensionado conservador, opt-in) |
| M2 preinscrito por bloques de 4096 no implementado (se mide sobre la clave entera) | estadística | desviación declarada; el veredicto no cambia |
| P1 calibrado con las mismas semillas | estadística | rotulado prueba de regresión |
| Batería de 3 de 15 pruebas, unos 30 valores $p$ sin corrección, semillas no independientes, 90B informativo | estadística | declarado en el resumen y en las secciones de métodos y validez |
| Informe, pitch y DAG desfasados (nodos, pruebas, contratos, TRL, 14 %) | documental | regenerados desde el registro |
| «Cada experimento lleva un control negativo» y «ninguna cifra se mueve después» | documental | corregidos en el pitch |

: Hallazgos principales de R.01 y su disposición. []{#tbl:r01}

La reutilización de nonce fue el único hallazgo bloqueante y se corrigió; el resto quedó como corrección de texto o como limitación declarada. Los hallazgos sobre la documentación y la publicación del repositorio se atienden en el release. Las enmiendas de E3 del 2026-10-08 se hicieron el mismo día de la corrida y se declaran como un grado de libertad del investigador (apéndice D): la primera semilla completa de un intento se descartó como INVÁLIDA sin conservar cifras. El veredicto de E3 no depende de ello, porque M7 está entre 8,9 y 19 veces por encima del umbral.

La revisión R.02, previa al release 0.2.0, la hicieron otros tres revisores independientes (afirmaciones 7,5; coherencia 6,0; código 5,5 sobre 10). Sus hallazgos sobre E3b y E5 ya están incorporados en este texto: la comparación entre E3 y E3b no es equivalente, el productor de 177 a 199 kbit/s es capacidad y no lo entregado, T2 de E3b era casi trivial, E5 es casi un control por construcción y E3b queda en TRL 3 (4 sólo con la reserva cebada). La tabla completa de hallazgos y disposiciones está en `docs/informes/REVISION_ADVERSARIAL_0.2.0.md`.

# Conclusiones {#sec:conclusiones}

1. La cadena completa (fuente simulada, mitigación de lectura, extracción, dimensionado, validación y cifrado) entrega claves AES-256-GCM que superan las pruebas M1 a M5 con ruido de lectura asimétrico. El simulador valida el postprocesamiento y no aporta entropía cuántica; «certificada» significa «supera esta batería y estas cotas».
2. La mitigación por *twirling* reduce el sesgo de lectura con holgura en el modelo sintético y deja un sesgo local por bloque que detectan las pruebas de rachas y de frecuencia por bloques. ZNE y PEC no actúan sobre el error de lectura. La clave aprueba la batería también sin mitigar, de modo que la mitigación mejora la muestra cruda y no es necesaria para aprobar.
3. Una batería aplicada a la salida de un extractor no mide la calidad de la fuente. Con el dimensionado por MCV, claves de fuentes con dependencia aprueban M1 a M5 y son de 1,2 a 2,5 veces más largas de lo que la fuente sostiene. El dimensionado conservador las acorta por debajo del techo teórico y conserva del 89,5 al 92,3 % de la clave de una fuente buena, pero es opcional, no cubre un defecto adversarial y no se re-midió en los experimentos de latencia.
4. Generar una clave por transacción incumple el requisito de latencia (percentil 95 de 5,5 a 9,4 s frente a 500 ms), mientras que la tasa lo supera 18 veces. Con una reserva de claves producida aparte, la transacción cuesta décimas de milisegundo. El costo se traslada al arranque (6,6 s) y a la custodia de una reserva en memoria, y el resultado vale para simulador, con una demanda declarada por el equipo.
5. Tres de los cinco experimentos (E1, E2 y E5) y el criterio de latencia de E3b tienen un poder limitado para fallar, por propiedades algebraicas del *twirling* o por construcción del control. El informe lo declara y conserva el resultado negativo de E3.
6. El software se mantuvo bajo contratos de arquitectura ejecutables y 883 casos de prueba, y cada cifra de este informe se regenera desde un registro de sólo añadir. Dos revisiones independientes (R.01 y R.02) puntuaron el trabajo entre 5,5 y 7,5 sobre 10, y sus hallazgos están incorporados.
7. No hay corrida en hardware de IBM. El camino está implementado y ensayado contra un backend falso, la corrida está preinscrita (E4) y su ejecución espera una credencial. El nivel de madurez tecnológica del sistema es 3, y no se afirma origen cuántico.

El trabajo siguiente, en este orden, consiste en ejecutar E4 en hardware de IBM (identificador de trabajo, contraste con el simulador y comparación del *twirling* propio con la mitigación del muestreador de IBM); re-medir E3b con el dimensionado conservador y decidir si pasa a ser el predeterminado; medir la latencia con la cola y la red de IBM dentro; y cerrar la medición de M2 por bloques, hallazgo abierto de R.01.

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
| D-007 | E1 lleva un control negativo: un generador clásico también pasa M1 a M5 |
| D-008 | Secretos por ruta, nunca por valor |
| D-009 | F4.01 es *twirling* de lectura propio; mthree sólo de contraste; ZNE y PEC fuera del bitstream |
| D-010 | Sin acceso a hardware IBM: constancia fechada; no se afirma origen cuántico ni se simula una corrida de hardware |

: Decisiones de diseño D-001 a D-010 (`docs/decisiones/`). []{#tbl:decisiones}

# Apéndice B. Discrepancias con el manifiesto fundacional {.unnumbered}

El manifiesto del equipo gobierna el objetivo del proyecto. Su método choca en nueve puntos con lo que permiten las bibliotecas o la estadística. Cada punto se declaró antes de actuar, y una décima discrepancia surgió de la revisión adversarial del diseño ([Tabla](#tbl:discrepancias)).

| \# | El manifiesto dice | Lo que se encontró o decidió | Estado |
|:-----|:-------------------------------------|:-------------------------------------|:--------------------------|
| 1 | «No dependemos de hardware real» y, a la vez, «procesadores físicos de IBM» | Son dos alcances: el backend es un puerto (D-001), con simulador por defecto y hardware opcional | decidido |
| 2 | Aer con ruido produce «entropía cuántica» | El muestreo de Aer es un PRNG; `Origen.SIMULADOR_AER` no reclama origen cuántico (D-002; S.03) | demostrado |
| 3 | TREX + ZNE + PEC mitigan el *bitstream* del muestreador | ZNE y PEC se definen sobre valores esperados; `resilience_level` es opción del estimador (S.02) | verificado |
| 4 | «TREX vía mthree» | Son técnicas distintas; mthree entrega cuasi-probabilidades, no bits (D-009) | verificado |
| 5 | Min-entropía > 0,9 prueba la calidad | Tras Toeplitz vale casi 1 por construcción; la informativa es la de entrada | decidido |
| 6 | «Claves certificadas» | SP 800-22 no certifica origen ni impredecibilidad; hay control negativo (D-007) | decidido |
| 7 | «TRL 4» | La rúbrica exige $n\ge3$, protocolo preinscrito y auditable; el TRL real es el de la afirmación más débil (fuente en simulador: TRL 3) | cerrado por T.TRL: TRL del sistema 3 |
| 8 | El MCV decide la longitud y la «certifica» | El MCV es ciego a la dependencia: Markov con permanencia 0,8 (min-entropía real 0,322 bit/bit, analítico) da MCV 0,992 (S.04, C.E1d); el dimensionado sigue usando MCV | demostrado; E5 lo mide en cadena completa y el dimensionado conservador (opt-in) lo corrige en las tres fuentes de prueba; el predeterminado sigue siendo `mcv` |
| 9 | M1 < 1 % y M2 > 0,9 como umbrales | Con $N=800\,000$ el monobit exige sesgo menor que 0,0014 (siete veces más estricto que M1) y M2 sobre 256 bits no supera 0,785 (analítico, P.E0) | decidido |
| 10 | (revisión R.00) | Medir M1 a M5 sólo sobre la salida de Toeplitz haría pasar a cualquier fuente; se miden en tres puntos (cruda, mitigada y clave); hallazgo R.00-1 | decidido y confirmado en E1 |

: Discrepancias con el manifiesto fundacional. []{#tbl:discrepancias}

# Apéndice C. El plan como grafo verificable {.unnumbered}

Material suplementario. El plan del proyecto es un grafo dirigido acíclico generado por un script; el estado de cada nodo vive en un registro de sólo añadir y una herramienta de validación rechaza cualquier estado que contradiga las reglas. El plan no se edita a mano, y una prueba comprueba que el fichero versionado coincide con la regeneración. Este apéndice documenta la estructura y las reglas; no hace falta para seguir los resultados.

El plan de la versión 0.1.0 tenía 59 nodos y 132 aristas, con una única hoja (el producto 0.1.0) y una profundidad máxima de 15 niveles. Las tablas y la figura son una instantánea de 0.1.0. A la fecha (versión 0.2.0) el plan tiene 79 nodos y 194 aristas: 70 hechos, 5 juzgados (E1, E2, E3, E3b y E5), 1 bloqueado (la corrida en hardware de IBM, sin credencial) y 3 pendientes (el juicio de esa corrida, su revisión y la versión 0.3.0). Se organiza en ocho fases más la revisión final ([Tabla](#tbl:fases)). Cada nodo declara su tipo ([Tabla](#tbl:tipos)), sus dependencias, su entrega (rutas del repositorio), el criterio de cierre y los requisitos que cubre. La [Figura](#fig:dag) muestra el estado real al cierre de 0.1.0: 54 nodos hechos, 3 juzgados (E1, E2 y E3) y 2 pendientes (la revisión R.01, lista, y el release 0.1.0, bloqueado por ella).

![El plan como DAG, por fases y coloreado por el estado real (instantánea de 0.1.0: plan de 59 nodos y registro de estado de ese momento; a la fecha el plan tiene 78 nodos). Borde grueso: eureka; discontinuo: preinscripción; punteado: corrida o medición. Verde: hecho; azul: juzgado; naranja: listo; blanco: pendiente.](fig/dag.pdf){#fig:dag}

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

**Revisión independiente por versión.** Cada versión publicada desciende de una revisión adversarial propia, hecha por revisores que leen el repositorio sin el historial de la conversación y recalculan cifras del registro. La revisión del diseño (R.00) puntuó la arquitectura de capas con 6/10 y el plan hacia TRL 4 con 3,5/10; la del release 0.1.0 (R.01) y la del 0.2.0 (R.02) se resumen en la [sección](#sec:r01). Los hallazgos aceptados entran al tablero de incidencias antes que al plan.

# Apéndice D. Enmiendas fechadas y desviaciones del protocolo {.unnumbered}

Todas las enmiendas de la tabla son anteriores a la corrida registrada a la que afectan, y ninguna cambia un umbral de M1 a M7. La única edición de una preinscripción posterior a su corrida es de redacción: `d9c9c6d` (fila final de la tabla). Sí cambian el estatus de dos métricas (M4 y M5 de la mitigada, de decisivas a informativas) y dos umbrales de control (P1, de 0,9 a un piso de 0,8 y un techo de 0,5; la carga previa de E3, de 1,0 a 2,0). Las tres del 2026-10-08 afectan a las condiciones de la medición de E3 (carga previa, clave rechazada, reposo) y no a las definiciones de M6 y M7; la segunda es la única que modifica lo que se mide, y lo hace en contra de la corrida, porque el tiempo del intento rechazado se cuenta. Cada una abre una oportunidad de sesgo del investigador y por eso se documenta ([Tabla](#tbl:enmiendas)).

| fecha | doc. | enmienda | commit | motivo y alcance |
|:---------|:------|:----------------------------------|:---------------------|:----------------------------------|
| 2026-10-07 | E3 | El guard de cifrado juzga sólo M1 a M5; M6 y M7 las juzga C.E3 de extremo a extremo | `8984147`, `09da88c`, `5a72939` | Las M6 y M7 internas se miden hasta Toeplitz y podrían impedir cifrar; no se salta el guard ni se relaja un umbral |
| 2026-10-07 | E3 | M1 a M5 en el punto «mitigada» pasan a informativas | `5a72939` | Misma causa que en E1; los criterios T1 a T4 no leen M1 a M5 |
| 2026-10-07 | E1 | M5 sobre la mitigada pasa a informativa | `dae22a6` | Diagnóstico de escritorio sin corrida registrada ⚠️ (la preinscripción cita una falla en 7 de 8 semillas, sin artefacto archivado) |
| 2026-10-07 | E1 (1) | M4 sobre la mitigada pasa a informativa; M-1 decide con M1 y M3 | `1a06602` | Misma causa; la clave sigue decidiendo con M1 a M5 |
| 2026-10-08 | E3 | Carga previa de la máquina: de menos de 1,0 a menos de 2,0, con la corrida fijada a un núcleo libre | `15bd897` | El umbral era arbitrario y un proceso ajeno de un hilo mantenía la carga entre 1,4 y 2,0 durante horas; la validez de «un hilo» sigue decidiendo |
| 2026-10-08 | E3 | Una clave rechazada por M1 a M5 se regenera y el tiempo del intento rechazado suma a $t_{rep}$ | `8cc0ec1` | Con $\alpha=0{,}01$ por prueba una clave válida falla alguna con probabilidad no nula; cinco rechazos seguidos invalidan la corrida. Se hizo el mismo día de la corrida, tras un primer intento real que cayó en el monobit; ese intento no conserva cifras |
| 2026-10-08 | E3 | Reposo de hasta 900 s entre semillas antes de comprobar la carga | `41cd058` | La medición de una semilla eleva la carga de 1 min en ≈ 1 y habría invalidado la siguiente por autocontaminación |
| 2026-10-07 | E1 (2) | P1 cambia de «ideal con 90B $>0{,}9$» a separación del instrumento: piso 0,8 y techo 0,5 | `37b89ca`, `447c907` | Desviación declarada, descrita a continuación. La segunda enmienda de E1 es ésta, tras una calibración con las semillas declaradas |
| 2026-10-08 | E3 | Redacción: la nota sobre E1 pasa de «M4 decisiva con alerta analítica» a «M4 y M5 informativas por enmienda» | `d9c9c6d` | **Posterior** a C.E3 (`fdb4386`, 14:46; `d9c9c6d`, 15:08): sólo edita texto de `docs/preinscripciones/E3.md`; no cambia umbrales, criterios ni T1 a T4 |

: Enmiendas fechadas; todas anteriores a la corrida salvo la de redacción de `d9c9c6d`. []{#tbl:enmiendas}

La enmienda del control P1 constituye una desviación del protocolo que debe declararse con detalle. El 90B de la fuente ideal se midió antes de correr E1, pero sobre las semillas declaradas (20261007, 20261008 y 20261009) y ocho más (20261010 a 20261017), con $10^6$ bits por fuente y semilla. La fuente ideal dio 90B entre 0,821 y 0,903 (sólo 2 de 11 superan 0,9), la Markov entre 0,170 y 0,172, la sesgada entre 0,321 y 0,324, y la periódica 0. El criterio original (ideal con 90B mayor que 0,9) fallaba en 9 de 11 fuentes ideales. El instrumento resultaba inválido por una propiedad suya, ya que el mínimo de diez estimadores es una cota conservadora incluso con $h=1$, y no por la fuente. Además, el 0,9 de M2 corresponde a la clave de salida tras Toeplitz, otra magnitud. El piso 0,8 es el mínimo observado (0,821) redondeado hacia abajo a la décima; el techo 0,5 deja un hueco de 0,3.

Quien fijó el piso conocía los valores de las tres semillas declaradas (0,821; 0,902 y 0,832). En consecuencia, P1 pasaría en ellas salvo cambio de código, la calibración no fue ciega, y la cola por debajo de 0,8 en una semilla futura no está medida (⚠️ sin verificar). Con la media y la desviación de las 11 fuentes, la probabilidad de que una fuente ideal nueva quede bajo 0,8 ronda el 2 % (analítico, revisión R.01). P1 es por tanto una prueba de regresión del instrumento.

**Enmiendas hechas el mismo día de la corrida.** Las tres enmiendas de E3 del 2026-10-08 se escribieron después de que un primer intento real de C.E3 tropezara con la carga de la máquina y con una clave rechazada. La primera semilla completa de ese intento se descartó como INVÁLIDA y no se conservaron sus cifras, contra la letra de la regla de que las corridas anteriores permanecen en el registro. Es un grado de libertad del investigador y se declara como tal. El veredicto de E3 no depende de ello: M7 supera el umbral entre 8,9 y 19 veces incluso en la repetición más rápida, y las enmiendas lo penalizan en vez de favorecerlo. E1 aplicó el criterio contrario ante el mismo evento (clave rechazada: INVÁLIDA, sin repetir), de modo que la política no es homogénea entre experimentos. La pregunta que P1 responde pasa a ser una separación (¿distingue el estimador lo bueno de lo malo?) y deja de ser si la ideal alcanza 0,9.

# Apéndice E. Mapa de fuentes del repositorio {.unnumbered}

| tema | fuente (relativa a la raíz del repositorio) |
|:-------------------------------------------|:-----------------------------------------------------------|
| Objetivo, alcance, discrepancias | `docs/FUNDAMENTO.md` |
| Arquitectura | `docs/DISENO.md` |
| Amenazas | `docs/AMENAZAS.md` |
| Decisiones D-001 a D-010 | `docs/decisiones/` |
| Preinscripciones P.E0 a P.E5 (E1, E2, E3, E3b, E4 y E5) | `docs/preinscripciones/` y `declaraciones/*.toml` |
| Spikes S.01 a S.04 | `spikes/` |
| Revisión adversarial R.00 | `docs/informes/REVISION_DISENO_R00.md` |
| Plan (DAG) | `plan/construir_dag.py` y `plan/plan.json` |
| Corridas y veredictos | `registro/corridas/`, `registro/veredictos.jsonl` |
| Estado generado | `ESTADO.md`, `registro/nodos.jsonl` |
| Figuras de este informe | `docs/paper/figuras.py` y `docs/paper/fig/` |

: Mapa de fuentes. []{#tbl:fuentes}
