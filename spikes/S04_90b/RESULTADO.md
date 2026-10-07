# S.04 — Estimador NIST SP 800-90B no-IID independiente

**Veredicto:** utilizable. Se usa el `ea_non_iid` oficial (usnistgov/SP800-90B_EntropyAssessment, tag v1.1.8, C++),
compilado fuera del repo con `build_nist.sh` y llamado por `run.py`. Independiente de `dominio/entropia.py`: sí.

## Opciones examinadas
- (a) PyPI: `sp800-90b` 0.1.1 existe (hnj2, tercero, sdist 52 KB, sin evaluar); `ea-non-iid`, `nist-sp800-90b`, `entropy-assessment`, `min-entropy` dan 404. Descartado: no es del NIST.
- (b) Oficial C++: hay red, g++ y make; el tarball del tag baja (3,3 MB). Faltaban libbz2-dev, libdivsufsort y libjsoncpp (sin sudo): se obtienen con `apt-get download` + `dpkg -x` a /tmp. ELEGIDA.
- (c) Embebido en paquete instalado: no se buscó a fondo (innecesario con (b)).

## Resultados (1 000 000 bits, semilla 20261007, `-i -a`, 1 bit/símbolo; ~0,5 s por señal)
| Señal | h esperada | NIST (mínimo) | Estimador del mínimo | MCV NIST = MCV propio |
|---|---|---|---|---|
| IID p(1)=0,7 | 0,515 | 0,322 | Compression | 0,5123 |
| Markov permanencia 0,8 | 0,322 | 0,170 | Collision | 0,9916 |
| Periódica 00001111 | 0 | 0 | Collision | 0,9963 |

Markov por estimador: MCV 0,992; Collision 0,170; Markov 0,325; Compression 0,213; t-Tuple 0,331; LRS 0,557; MultiMCW 0,486; Lag 0,319; MultiMMC 0,319; LZ78Y 0,319.

## Lectura
- Mínimo exigido por la herramienta: **1 000 000 muestras**.
- Nuestro MCV coincide con el MCV de NIST a 6 decimales en las tres señales: valida la implementación del MCV.
- MCV solo no ve la dependencia (0,99 en Markov, 0,996 en la periódica): importa el mínimo de la batería.
- El mínimo NIST es una cota inferior conservadora, no un valor puntual: en IID sesgada Compression baja a 0,322 (esperado 0,515) y en Markov Collision a 0,170 (esperado 0,322, que los predictores sí reproducen: 0,319). Un umbral contra NIST debe asumir ese sesgo a la baja.
- Depende de red en la primera compilación y de `-march=native` (binario no portable entre CPUs).

## Reproducir
`uv run python spikes/S04_90b/run.py` (escribe resultado.json y salida_cruda.json).
