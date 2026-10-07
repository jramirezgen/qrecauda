# DISEÑO de QRecauda — arquitectura en capas

> Auditado con las dos lentes de `code-principles`: principios (§1) y mapa clásico de capas (§3, cada fila con
> sitio + regla de imports + test). La revisión adversarial independiente es el nodo `R.01` del DAG: **hasta que
> corra, este diseño es 10/10 «en el papel», no demostrado.**

## 0. Las cuatro macro-capas (el mapa que se lee primero)

| macro-capa | qué es | paquetes | quién la importa |
|---|---|---|---|
| **Datos** | lo que persiste y cruza fronteras: esquemas versionados, informes, serialización canónica, almacén append-only | `datos/` (+ puerto `Almacen`, adaptador `almacen_json`) | puertos, aplicación, adaptadores |
| **Lógica** | las reglas: matemática de la entropía, métricas, y los casos de uso/orquestador | `dominio/` (puro) · `aplicacion/` | aplicación → dominio; nunca al revés |
| **Integración** | todo lo que habla con un sistema externo, uno por puerto, con su SDK confinado | `adaptadores/` (Aer, IBM Runtime, mthree, nistrng, cryptography, disco) · `composicion.py` | sólo la raíz de composición los elige |
| **Transversales** | lo que cruza capas: configuración, errores, observabilidad, reproducibilidad, seguridad, concurrencia, empaquetado | `transversal/` · `dominio/errores.py` | entrada, api, composición y adaptadores; **nunca** el núcleo ni la presentación |

Cada una tiene su propio nodo de cierre en el DAG (`L-datos`, `L-dominio`/`L-aplicacion`, `L-integracion`, `T-*`) y su propio
contrato en `.importlinter`. La Presentación y la CLI son bordes de la lógica, no una quinta capa.

## 1. Principios aplicados (lente 1)

| principio | cómo se aplica aquí |
|---|---|
| DRY de conocimiento | los umbrales M1–M7 viven en `dominio/metricas.py` y nadie más los teclea |
| Ortogonalidad | la fuente, la mitigación, la validación y el cifrado son puertos independientes: cambiar uno no toca otro |
| Bala trazadora | `aplicacion/pipeline.py` corre hoy de punta a punta con un PRNG; Aer e IBM entran después sin tocarlo |
| Diseño por contrato | `Bits` no se construye ilegal; `longitud_segura` aborta si no sale un bit; el veredicto vacío no aprueba |
| Reversibilidad | el backend es un puerto; los SDK pesados son extras opcionales (`pyproject.toml`) |
| Ventanas rotas | trinquetes por AST y `lint-imports` en la CI local |
| Estimación | los costes por etapa se miden (`transversal/observabilidad.py`) y se escriben al manifiesto |

## 2. Flujo

```
FuenteDeBits ──▶ [Mitigador] ──▶ Peres ──▶ Toeplitz(LHL) ──▶ Validador ──▶ Clave ──▶ Cifrador
(prng | aer | ibm)   (opcional)   dominio     dominio          (scipy|nistrng)         (AES-GCM)
```

## 3. Mapa de capas (lente 2)

| capa | sitio | regla de imports | test |
|---|---|---|---|
| Presentación | `presentacion/` | formatea; no orquesta ni importa adaptadores ni transversal | C1, C3 |
| API pública | `api.py` | fachada estable; la CLI es un cliente más | `tests/arquitectura/test_api.py` congela firmas |
| Raíz de composición | `composicion.py` | ÚNICO sitio que elige adaptadores | C1 |
| Entrada | `entrada/` (CLI, códigos de salida) | importa la fachada y la jerarquía de errores (`dominio/errores.py`, para mapearlos a códigos); nada más del dominio | C1, `test_cli_codigos.py` |
| Adaptadores / integración | `adaptadores/` | uno por puerto, sin importarse entre sí; el SDK sólo aquí | C2, C5 |
| Aplicación | `aplicacion/` | casos de uso + orquestador; sólo puertos y dominio | C1, C3 |
| Puertos | `puertos/` | `Protocol`s | C1 |
| Datos / persistencia | `datos/` | esquema versionado, serialización canónica; lector viejo rechaza esquema futuro | `tests` de F2.01 |
| Dominio | `dominio/` | puro: sin I/O, reloj, aleatoriedad global ni SDK | C3, C4 |

**Transversales** (`transversal/`; sólo las importan `entrada`, `api`, `composicion` y `adaptadores`; al núcleo le llegan por puertos o ya validadas):

| transversal | sitio | compuerta |
|---|---|---|
| Configuración | `configuracion.py`, objeto inmutable, clave desconocida aborta | `test_os_environ_solo_en_configuracion` |
| Errores | raíz `ErrorQRecauda`, hijas con nombre, tabla de códigos en `entrada/codigos.py` | `test_ningun_except_exception_silencioso` |
| Observabilidad | JSON-lines + coste por etapa | F2.04 |
| Reproducibilidad | BLAS a un hilo **forzado**; entorno capturado | F2.04 |
| Seguridad | secretos por ruta; `describir()` no muestra el valor | `test_ninguna_credencial_en_el_codigo` |
| Concurrencia | candado de máquina para corridas pesadas | F2.04 |
| Empaquetado | `uv.lock`, semver, `CHANGELOG.md`, `scripts/ci_local.sh` | F0.08 |

## 4. Lo que se decidió NO poner (y cómo se revertiría)

| no hay | porque | si hiciera falta |
|---|---|---|
| Servidor HTTP / API REST | sin consumidor real en la hackatón | un adaptador de entrada más sobre `api.py` |
| Base de datos | los artefactos son JSON canónico en `registro/` | un adaptador de persistencia tras un puerto |
| Gestión de claves (KMS/HSM) | fuera de alcance, ver FUNDAMENTO | puerto `AlmacenDeClaves` |
| Multi-backend simultáneo | fuera de alcance | varias `FuenteDeBits` en la composición |

## 5. Contratos de imports (`.importlinter`)

C1 capas · C2 adaptadores independientes (`aer` es un paquete: `ruido` y `transpilacion` son suyos) · C3 el núcleo y la presentación no importan transversal/adaptadores/entrada ·
C4 dominio puro · C5 SDKs sólo en adaptadores (el borde —api, composicion, entrada, transversal— los alcanza sólo por el adaptador elegido, C5b) · C6 lo transversal es hoja (sólo depende de `dominio/errores`; lo usan entrada, api, composicion y adaptadores). `tests/arquitectura/test_contratos.py` los ejecuta, comprueba que
`.importlinter` y `qrecauda.CAPAS` dicen lo mismo y siembra un import prohibido para ver que el contrato muerde.
