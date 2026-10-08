# QRecauda

[![CI](https://github.com/jramirezgen/qrecauda/actions/workflows/ci.yml/badge.svg)](https://github.com/jramirezgen/qrecauda/actions/workflows/ci.yml)
[![Licencia: Apache-2.0](https://img.shields.io/badge/licencia-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](.python-version)

**La aleatoriedad clásica se predice. La recaudación del Perú no debería.**

QRecauda es un pipeline reproducible que convierte los bits de un circuito cuántico en claves de cifrado para cobros masivos (peaje y Metro de Lima), y mide cada etapa de la cadena. Hoy corre en simulador y está diseñado para recibir, por el mismo puerto, bits de una computadora cuántica de IBM. Nació en el Track 4 del Hackatón Qiskit IBM Lima.

## Por qué importa

Cada cobro es una transacción pequeña que se firma y se cifra con una clave y un *nonce*. Si el generador que los produce es pseudoaleatorio, quien reconstruye su estado reproduce las claves siguientes. El volumen que depende de eso es grande:

- **Metro de Lima, L1:** 203,9 millones de pasajeros en 2025, un récord (*verificado*, [energiminas](https://energiminas.com/?p=48912)). Más de 600 000 usuarios por día (*tercero*).
- **Peajes:** 24,6 millones de vehículos en el primer cuatrimestre de 2021, el único dato nacional hallado (*tercero*, desactualizado, sin cifra de recaudación, [andina](https://andina.pe/agencia/noticia-ositran-trafico-vehicular-crece-24-carreteras-concesionadas-852013.aspx)).

Las fuentes completas y su etiqueta están en [`docs/pitch/IMPACTO.md`](docs/pitch/IMPACTO.md).

**Lo que no se afirma.** Ninguna norma que revisamos (Ley 29733 con su DS 016-2024-JUS, SBS Res. 504-2021, reglamento del MTC) exige un QRNG; piden medidas técnicas de seguridad (*tercero*). El argumento de QRecauda es de ingeniería: la entropía de la fuente se mide, no se supone. Para eso se apoya en NIST SP 800-90B (estimación de entropía de la fuente) y SP 800-90C (construcción de generadores, versión final del 2025-09-25, *verificado*). NIST SP 800-22 se usa sólo como chequeo de regresión del postprocesamiento: en 2022 NIST aclaró que no sirve para validar generadores aleatorios criptográficos (*tercero*), y aquí lo confirmamos, porque una clave de PRNG y una de fuente sesgada la pasan igual.

## Qué hay hoy y qué añade la computadora de IBM

| | hoy, en simulador | lo que añade la computadora cuántica de IBM |
|---|---|---|
| Fuente de bits | Qiskit Aer, circuito de un gate sobre ocho qubits | mediciones de un dispositivo real, con `job_id` trazable |
| Origen de la entropía | un PRNG: sin valor de seguridad | proceso físico de medición, **no certificado** (no hallamos un QRNG certificado de IBM) |
| Ruido de lectura | modelado (sesgo crudo de 0,03 en el nivel medio) | ruido real, posiblemente asimétrico, correlacionado y con deriva |
| Mitigación | twirling propio medido sobre ruido modelado; ZNE y PEC no mueven el sesgo | comprobar que funciona sobre ruido real y compararlo con `mthree` y con las opciones de IBM (⚠️ sin verificar) |
| Validación | NIST 800-22 y 90B sobre las etapas; control de fuente Markov | 90B sobre los bits crudos del dispositivo, que es lo que informa sobre la fuente |
| Latencia | M7 cumple con la clave de una reserva generada aparte (E3b); sin cola ni red de IBM | sumará latencia de cola y de red, hoy fuera de M7 |
| Qué se puede afirmar | que el postprocesamiento y su medición funcionan | nada nuevo hasta que corra E1 y E2 sobre esa fuente con tres semillas |

## Demo en 2 minutos

> `qrecauda demo` está en el árbol de trabajo (sin publicar): no existía en 0.1.0. Corre en segundos con Aer y sin red; la salida lleva el rótulo «simulado: Aer es pseudoaleatorio, sin origen cuántico».

```bash
uv run qrecauda demo
```

Muestra tres ramas lado a lado: un PRNG clásico, la fuente de Aer sin mitigar y la fuente de Aer mitigada. La mitigación limpia la entrada (el sesgo de la muestra baja de 0,03 a cuatro diezmilésimas), pero la clave de las tres ramas pasa la batería: por eso la batería no prueba el origen. La figura sale de las corridas registradas con `presentacion/figura_demo.py` y está en el [deck](docs/pitch/DECK.md); el [guion de dos minutos](docs/pitch/GUION.md) cronometra la presentación. Además cifra y descifra con AES-256-GCM un peaje y un trayecto de Metro con la clave aprobada. `uv run qrecauda demo --rapido` tarda menos; `uv run qrecauda demo --fuente ibm --ensayo` recorre el camino a IBM contra un backend falso (ver [docs/HARDWARE.md](docs/HARDWARE.md)). `uv run qrecauda juzgar E1` rejuzga la corrida registrada.

**Estado en una línea:** TRL **3**, prototipo de laboratorio. Lo que se probó es el postprocesamiento: mitigación de lectura, extracción de entropía, validación estadística y cifrado AES-GCM. El simulador no aporta entropía cuántica y no hay corrida en hardware IBM: el camino está listo y ensayado contra un backend falso (`uv run qrecauda hardware`, [docs/HARDWARE.md](docs/HARDWARE.md)), pero la corrida real (C.E4) está bloqueada por falta de credencial y **no existe ningún resultado en hardware real**. La tabla honesta de resultados está debajo y los detalles en [Limitaciones](#limitaciones).

## Qué problema aborda

Un generador de claves para cobros debe ser impredecible. Un generador clásico seudoaleatorio se predice si alguien conoce su estado. Una fuente cuántica evita ese problema, pero sus bits salen sesgados y correlacionados, y una batería estadística no distingue una fuente buena de un buen PRNG.

QRecauda arma la cadena completa y mide cada etapa:

```
FuenteDeBits -> [Mitigador] -> Peres -> Toeplitz (LHL) -> Validador -> Clave -> AES-GCM
```

Cada cifra del proyecto sale de una corrida con nombre, registrada en `registro/`. Los umbrales de éxito se fijaron por escrito antes de correr (`docs/preinscripciones/`).

## Resultado

| experimento | qué mide | veredicto | cifra registrada |
|---|---|---|---|
| E1 | pipeline con fuente simulada, métricas M1 a M5 | CUMPLE, condicionado | La clave sin mitigar también pasa M1 a M5, así que esas métricas no prueban el valor de la mitigación ni el origen. |
| E2 | mitigación de lectura | CUMPLE | El twirling propio baja el sesgo de lectura entre 11 y 32 veces sobre ruido modelado. ZNE y PEC no mueven el sesgo de lectura. |
| E3 (0.1.0) | tasa (M6) y latencia (M7), la clave se genera dentro de la transacción | **NO CUMPLE** | M6 de 180 a 195 kbit/s (umbral 10 kbit/s, cumple). M7, p95 de 5,5 a 9,4 s frente a 500 ms: falla en las tres semillas. |
| E3b (0.2.0 en preparación) | latencia y sostenibilidad con la clave de una reserva generada aparte por un proceso productor | CUMPLE | M7, p95 de 0,17 a 0,18 ms sobre 12 000 transacciones por semilla (umbral 500 ms). Productor de 177 a 199 kbit/s contra un consumo declarado de 35,2 kbit/s, sin esperas. Arranque de 6,6 a 6,7 s hasta la primera clave, informado aparte. |
| E5 (0.2.0 en preparación) | control negativo del pipeline completo con fuentes que dependen de sus bits, y dimensionado conservador | CUMPLE | Con el dimensionado de 0.1.0 (`mcv`), las nueve claves de fuentes defectuosas pasan M1 a M5 y salen entre 1,2 y 2,5 veces más largas que lo que la fuente sostiene (hallazgo R.00-1 en cadena completa). El dimensionado conservador las acorta (markov_fuerte: de 380 a 381 mil bits con `mcv`, de 55 a 56 mil con el conservador) y la fuente buena conserva de 856 a 883 mil bits. |

Las cifras salen de `registro/corridas/C.E3.json`, `C.E3b.json` y `C.E5.json` y de `registro/veredictos.jsonl`; el cociente de 1,2 a 2,5 se calcula en el veredicto de E5 (criterio HOY) frente al techo teórico de cada fuente.

**E3 no se reabre.** Falla por M7 y su veredicto queda en el registro. E3b es otro diseño (la clave sale de una reserva que un proceso productor genera en paralelo), con preinscripción propia anterior a la corrida y veredicto propio; no corrige E3. Sus límites: se midió sobre simulador, sin la cola ni la red de IBM; la demanda (100 transacciones por segundo) la declara el equipo; y las claves se generan con el dimensionado `mcv` de 0.1.0.

**El dimensionado conservador es opt-in.** E5 muestra que el mínimo de MCV y 90B más la contabilidad de la entropía de la fuente acorta las claves de fuentes dependientes; `min(MCV, 90B)` por sí solo no alcanza en markov_fuerte. Por defecto el pipeline sigue con `mcv`, y no se re-midieron E3 ni E3b con el conservador (⚠️ sin verificar su efecto sobre la latencia). E5 prueba tres defectos de dependencia con respuesta analítica, no uno adversarial.

## Estado

| componente | TRL | nota |
|---|---|---|
| Dominio (Peres, Toeplitz) | 4 | aritmética pura, tres semillas preinscritas |
| Mitigación de lectura (twirling propio) | 4 | sobre ruido modelado, no real |
| Validación (NIST SP 800-22 y 90B) | 4 | con control positivo y negativo |
| Fuente simulada con ruido (Aer) | 3 | Aer muestrea con un PRNG |
| ZNE y PEC | 3 | sin efecto medido sobre el sesgo de lectura |
| Latencia con reserva de claves (E3b) | 4 | tres semillas preinscritas, en simulador; no sube al sistema |
| Dimensionado y control negativo del pipeline (E5) | 4 | tres defectos de dependencia, en simulador |
| Cifrado AES-GCM | 3 | su fila sólo cita E3 |
| Fuente real (hardware IBM) | 3 | sin corrida, `job_id` nulo; C.E4 bloqueado por falta de credencial |
| **Sistema** | **3** | la fila más baja, no el promedio |

La tabla completa y su derivación están en [`docs/TRL.md`](docs/TRL.md). El camino a TRL 4 y 5 está en [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Instalación

Necesitas [uv](https://docs.astral.sh/uv/) y Python 3.13.

```bash
git clone https://github.com/jramirezgen/qrecauda.git && cd qrecauda
uv sync --group dev
```

Eso instala el núcleo (numpy y scipy). Los adaptadores pesados son extras opcionales: `cuantico`, `mitigacion`, `validacion`, `cifrado`, `informe`. La guía [`docs/USO.md`](docs/USO.md) explica cuál necesita cada tarea.

## Uso rápido

CLI. Sin subcomando genera una clave con el PRNG de línea base y devuelve el código de salida 0 si el veredicto aprueba:

```bash
uv run qrecauda                       # tabla de métricas M1 a M7
uv run qrecauda --formato json        # lo mismo en JSON
uv run qrecauda juzgar E3             # aplica el criterio preinscrito a la corrida registrada
```

API de Python:

```python
from qrecauda import api

resultado = api.generar_clave(api.Configuracion(backend="prng"))
print(resultado.veredicto.aprobado)   # True
print(len(resultado.clave))           # bits de clave, dimensionados con la min-entropía
```

`correr` (declaración TOML a corrida registrada), las opciones de configuración y los códigos de salida están en [`docs/USO.md`](docs/USO.md).

## Arquitectura

Cuatro macro-capas sobre puertos y adaptadores. El dominio no hace I/O ni importa ningún SDK, y siete contratos de `import-linter` lo hacen cumplir en cada ejecución de la CI.

```mermaid
flowchart TB
    subgraph Borde
        CLI["entrada (CLI)"] --> API["api (fachada)"]
        API --> COMP["composicion (elige adaptadores)"]
    end
    subgraph Integracion
        COMP --> AD["adaptadores: Aer, IBM Runtime, mthree, nistrng, 90B, AES-GCM, disco"]
    end
    subgraph Logica
        COMP --> APL["aplicacion (casos de uso)"]
        APL --> PUE["puertos (Protocol)"]
        APL --> DOM["dominio (puro)"]
    end
    subgraph Datos
        PUE --> DAT["datos (esquemas versionados, JSON canónico)"]
    end
    AD -. implementa .-> PUE
    TR["transversal: configuración, errores, observabilidad, reproducibilidad, concurrencia"] -.-> COMP
    PRE["presentacion (tablas, figuras)"] --> APL
```

El detalle, con la regla de imports de cada capa y el test que la protege, está en [`docs/DISENO.md`](docs/DISENO.md).

## Estructura del repo

| ruta | contenido |
|---|---|
| `src/qrecauda/` | paquete: `dominio`, `puertos`, `datos`, `aplicacion`, `adaptadores`, `presentacion`, `transversal`, `entrada`, `api.py`, `composicion.py` |
| `tests/` | pruebas por capa y tests de arquitectura (contratos, trinquetes, TRL) |
| `declaraciones/` | experimentos E1, E2 y E3 en TOML, fijados antes de medir |
| `docs/preinscripciones/` | umbral y criterio de cada experimento, escritos antes de la corrida |
| `registro/` | corridas, veredictos y estado de nodos (solo se añade) |
| `plan/` | DAG del proyecto y su verificador |
| `notebooks/` | `qrecauda.ipynb` (tablas del informe) y `qrecauda_vivo.ipynb` (del circuito a la clave cifrada, con `FUENTE` aer o ibm) |
| `spikes/` | investigaciones acotadas (S.01 a S.04), incluida la compilación del 90B |
| `presentacion/` | `figura_demo.py`: figura de la demo de las tres ramas, desde `registro/corridas/` |
| `scripts/` | CI local, hooks de git, limpieza del entorno |
| `docs/` | fundamento, diseño, amenazas, TRL, roadmap, glosario, decisiones, informes; `docs/pitch/` con deck, guion e impacto |

## Reproducir los resultados

```bash
uv sync --frozen --group dev --extra informe
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/qrecauda.ipynb
.venv/bin/qrecauda juzgar E1       # E2 y E3 igual: rejuzga sobre las corridas registradas
```

Volver a correr un experimento completo (`qrecauda correr declaraciones/E1.toml`) necesita los cuatro extras, el binario del estimador 90B compilado y una máquina sin carga. [`docs/USO.md`](docs/USO.md) lo explica paso a paso.

## Plan y registro

El plan es un grafo acíclico (`plan/`); los 59 nodos de la versión 0.1.0 están cerrados y la 0.2.0 (en preparación, sin publicar) suma E3b y E5. La hoja de ruta de la 0.3.0 es el camino a hardware: C.E4 y E4 siguen abiertos. El estado vive en `registro/nodos.jsonl` y `ESTADO.md` se genera de él. Un nodo se cierra con un commit que toca su entrega. Para ver el estado: `python3 plan/dag.py estado`; para ver qué sigue: `python3 plan/dag.py siguiente`. Si quieres contribuir, empieza por [`CONTRIBUTING.md`](CONTRIBUTING.md) y [`RETOMA.md`](RETOMA.md).

## Limitaciones

- Aer muestrea con un PRNG. Pasar la batería NIST prueba el postprocesamiento, no el origen de los bits.
- No hay corrida en hardware IBM. Que el modelo de ruido propio reproduzca el ruido físico y que la mitigación funcione sobre ruido real quedan sin probar.
- Por defecto la clave se dimensiona con min-entropía MCV, que supone bits independientes. Con correlación temporal la longitud se sobrestima: E5 la midió en cadena completa (claves de 1,2 a 2,5 veces lo que la fuente sostiene). El dimensionado conservador la corrige en las tres fuentes de prueba, pero es opt-in y no cubre un defecto adversarial.
- M7 falla en E3 (0.1.0) y cumple en E3b con una reserva de claves, sólo en simulador y sin cola ni red de IBM. Esa reserva en memoria es un depósito de claves que aumenta la exigencia de custodia. Los 500 ms, los 10 kbit/s y los 100 tx/s vienen del manifiesto del equipo, no de un operador real.
- El registro de nonces vive en la memoria del proceso y no protege entre procesos. No hay gestión de claves (KMS o HSM), ni protección del canal, ni anti-replay.
- NIST SP 800-22 es una batería estadística y SP 800-90B una cota empírica. Ninguna es una certificación FIPS, ISO o Common Criteria.

El modelo de amenazas completo está en [`docs/AMENAZAS.md`](docs/AMENAZAS.md). Para reportar un problema de seguridad, ver [`SECURITY.md`](SECURITY.md).

## Cómo citar

Hay metadatos en [`CITATION.cff`](CITATION.cff); GitHub los ofrece en el botón «Cite this repository». Autor: kaitokid, versión 0.1.0. El informe técnico está en `docs/paper/`.

## Licencia

Apache-2.0. Ver [`LICENSE`](LICENSE). Las contribuciones siguen [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
