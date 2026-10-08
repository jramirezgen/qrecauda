# Guía de uso

Esta guía cubre la instalación por extras, la CLI, las declaraciones TOML, la API de Python, la configuración y los problemas habituales. Para el panorama del proyecto, ver el [README](../README.md).

## 1. Instalación

Requisitos: [uv](https://docs.astral.sh/uv/) y Python 3.13 (el repo lo fija en `.python-version`; `pyproject.toml` permite 3.11 o superior, pero solo 3.13 está probado). Para el estimador 90B hace falta además `g++`, `curl` y `apt-get` (descarga de paquetes sin root).

```bash
git clone https://github.com/jramirezgen/qrecauda.git && cd qrecauda
uv sync --group dev
```

El núcleo (dominio, puertos, aplicación) usa solo numpy y scipy. Cada extra alimenta un adaptador:

| extra | instala | lo necesitas para |
|---|---|---|
| `cuantico` | qiskit, qiskit-aer, qiskit-ibm-runtime | backend `aer_ruidoso`, backend `ibm`, E1, E2, E3 |
| `mitigacion` | mthree | contraste con mthree en E2 |
| `validacion` | nistrng | validador `nist`, proporciones NIST de E1 |
| `cifrado` | cryptography | cifrado AES-GCM, E3 |
| `informe` | matplotlib, plotly, jupyter | notebook y figuras |

Instalación completa, la misma que usa la CI:

```bash
uv sync --frozen --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado --extra informe
```

`uv run <orden>` sincroniza antes de ejecutar y puede quitar los extras que no pediste en esa llamada. Si instalaste extras, usa `.venv/bin/<orden>` o `uv run --no-sync <orden>`.

## 2. CLI

```
qrecauda [--config TOML] [--formato {tabla,json}] [--raiz DIR] [correr DECLARACION | juzgar ID]
```

Las opciones globales van antes del subcomando.

| orden | qué hace |
|---|---|
| `qrecauda` | genera una clave con la configuración dada (PRNG por defecto) y muestra el veredicto M1 a M7 |
| `qrecauda correr declaraciones/E1.toml` | corre cada semilla de la declaración y escribe `registro/corridas/` |
| `qrecauda juzgar E1` | aplica el criterio preinscrito a la corrida ya registrada y añade una línea a `registro/veredictos.jsonl` |

`--raiz` es la raíz del repo, donde viven `declaraciones/` y `registro/`; por defecto es el directorio actual.

Códigos de salida (`src/qrecauda/entrada/codigos.py`):

| código | significa |
|---|---|
| 0 | correcto |
| 1 | veredicto rechazado (la clave o el experimento no cumple) |
| 2 | entrada inválida |
| 3 | entropía insuficiente |
| 4 | fuente o extra no disponible |
| 5 | esquema de registro más nuevo que el lector |
| 6 | autenticación AES-GCM fallida |
| 7 | nonce repetido |
| 8 | candado de máquina ocupado |
| 9 | corrida inválida |
| 10 | otro error de QRecauda |

Ejemplo, con salida JSON:

```bash
.venv/bin/qrecauda --formato json            # genera y juzga una clave; código 0 si aprueba
.venv/bin/qrecauda --config mi.toml          # con una configuración propia
.venv/bin/qrecauda juzgar E3; echo $?        # 1: E3 NO CUMPLE (M7)
```

`juzgar` escribe en `registro/veredictos.jsonl`. Si solo quieres leer el resultado, consulta ese archivo y `registro/corridas/`.

## 3. Declaraciones TOML

Un experimento es una declaración en `declaraciones/` que hereda los parámetros comunes de `declaraciones/PARAMETROS.toml` (qubits, disparos, semillas, niveles de ruido, validación). Su criterio de éxito está escrito en `docs/preinscripciones/<ID>.md` antes de correr. Estructura mínima, tomada de E3:

```toml
hereda = "declaraciones/PARAMETROS.toml"

[experimento]
id = "E3"
nodo_corrida = "C.E3"
metricas = ["M6_tasa_bps", "M7_latencia_ms"]

[configuracion]
backend = "aer_ruidoso"
nivel_ruido = "medio"
repeticiones = 30
calentamiento = 3
hilos = 1
carga_previa_maxima = 2.0
candado_de_maquina = true
```

Los umbrales de M1 a M7 no se escriben aquí: viven en `src/qrecauda/dominio/metricas.py`. Un experimento nuevo exige su preinscripción y su declaración antes de la primera corrida.

## 4. API de Python

La fachada es `qrecauda.api`. Sus firmas están congeladas por `tests/arquitectura/test_api.py`.

```python
from pathlib import Path

from qrecauda import api

# Una clave con la línea base (PRNG): no necesita extras.
cfg = api.Configuracion(backend="prng", qubits=8, shots=100_000, semilla=20261007)
res = api.generar_clave(cfg)

print(res.veredicto.aprobado)   # True si pasan M1 a M7
print(len(res.clave))           # bits de clave
print(res.h_min)                # min-entropía MCV de la entrada al extractor
for medida in res.veredicto.medidas:
    print(medida.metrica, medida.valor, medida.cumple)

# Rejuzgar un experimento sobre las corridas ya registradas (escribe en registro/).
v = api.juzgar("E3", Path("."))
print(v.aprobado)               # False
```

`api.correr(Path("declaraciones/E1.toml"), raiz)` devuelve el `ManifiestoDeCorrida`. El ejemplo anterior se verificó con el backend `prng`.

## 5. Configuración

`api.Configuracion` es un objeto inmutable. Se construye en código o desde un TOML con `--config`. Una clave desconocida o de tipo incorrecto aborta con `EntradaInvalida`.

| campo | tipo | por defecto | valores |
|---|---|---|---|
| `backend` | texto | `prng` | `prng`, `aer_ruidoso`, `ibm` |
| `qubits` | entero | 8 | 1 a 127 |
| `shots` | entero | 100000 | mayor que 0 |
| `semilla` | entero | 20261007 | cualquiera |
| `epsilon_exp` | entero | 64 | 8 a 128; ε = 2^-epsilon_exp, parámetro de diseño |
| `mitigacion` | texto | `ninguna` | `ninguna`, `lectura` (solo con `aer_ruidoso`) |
| `nivel_ruido` | texto | `medio` | `bajo`, `medio`, `alto`, `realista` (solo `aer_ruidoso`) |
| `validador` | texto | `estadistico` | `estadistico`, `nist` |
| `ibm_token_ruta` | texto | vacío | ruta al archivo del token; obligatorio con `ibm` |
| `ibm_backend` | texto | vacío | nombre del backend; vacío elige el menos ocupado |
| `ibm_modo` | texto | `batch` | `batch`, `session` |

Ejemplo de `mi.toml`:

```toml
backend = "aer_ruidoso"
nivel_ruido = "medio"
mitigacion = "lectura"
validador = "nist"
```

Variables de entorno que el código lee (solo `transversal/configuracion.py` toca `os.environ`):

| variable | efecto |
|---|---|
| `QRECAUDA_IBM_TOKEN_FILE` | ruta al token de IBM; se usa si `ibm_token_ruta` no está en el TOML |
| `OMP_NUM_THREADS` | E3 exige el valor `1` antes de medir; si no, aborta |
| `GIT_*` | se descartan al lanzar `git` desde un hook, para no heredar el repo equivocado |

Los secretos entran por ruta, nunca por valor. Para comprobar que un token carga, mira su longitud y prefijo; no lo imprimas.

## 6. Reproducir las tablas del notebook

```bash
uv sync --frozen --group dev --extra informe
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/qrecauda.ipynb
```

El notebook lee `registro/` y no vuelve a correr los experimentos. Genera los veredictos, la tabla de E1 por semilla y fuentes de control, el sesgo crudo y residual de E2, y la tasa y la latencia de E3 con el perfil B aparte. Para el informe en PDF, ver `docs/paper/README.md`.

## 7. Solución de problemas

**`lint-imports: command not found`.** El ejecutable vive en `.venv/bin`. Usa `uv run lint-imports` o añade el venv al PATH: `export PATH="$PWD/.venv/bin:$PATH"`.

**`FuenteNoDisponible: falta .../ea_non_iid`.** E1, E3 y varios tests usan el estimador oficial SP 800-90B. Hay que compilarlo una vez:

```bash
bash spikes/S04_90b/build_nist.sh
```

El script baja la versión 1.1.8 desde GitHub, trae las dependencias con `apt-get download` sin root y deja `ea_non_iid` en `/tmp/qrecauda_nist90b/`. Esa ruta es la que busca el código. Si `/tmp` se vacía (por ejemplo tras reiniciar), repite el comando. Sin el binario, los tests de `test_min_entropia.py` se saltan solos y E1 aborta antes de la primera semilla. Los tests de `tests/integracion/test_e2_e3_reales.py` usan el binario sin saltarse, así que compílalo antes de correr la suite completa.

**`CandadoOcupado` (código 8).** Las corridas pesadas toman un candado de máquina en `salidas/candado_maquina.lock`. E3 no espera: si otra corrida lo tiene, aborta. Espera a que termine la otra. El sistema operativo suelta el candado si el proceso muere, así que no queda colgado.

**La corrida de E3 aborta por carga previa.** E3 mide tiempos y exige que la carga de la máquina baje de `carga_previa_maxima` (2,0 en `declaraciones/E3.toml`). Espera un tiempo acotado a que la máquina se calme y, si no baja, lanza `CorridaInvalida` (código 9). Cierra otros procesos y revisa `uptime`. No subas el umbral para que pase: cambiarlo cambia lo que mide la corrida y exige una enmienda de la preinscripción.

**`OMP_NUM_THREADS` distinto de 1.** Exporta `OMP_NUM_THREADS=1` antes de lanzar Python. BLAS y OpenMP en varios hilos alteran M6 y M7.

**`uv run` quitó los extras.** Usa `.venv/bin/python` o `uv run --no-sync`, o vuelve a sincronizar con los extras que necesites.

**Un test falla con "hooksPath".** Ejecuta `scripts/instalar_hooks.sh` una vez por clon.

**`ruff format --check` falla.** Corre `uv run ruff format src tests` y revisa el diff.
