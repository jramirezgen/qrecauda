"""Fuente del DAG de QRECAUDA. Genera plan/plan.json (nunca se edita a mano) y se NIEGA a escribirlo si viola dag_lib.

`cubre` nombra lo que el nodo realiza (la lista que debe estar cubierta vive en plan/dag.json → `requerido`):
  O1…O7   los siete «Construir» del mensaje fundacional, en su orden (tabla en docs/FUNDAMENTO.md)
  R1…R6   las seis filas de la «Rúbrica» del mensaje fundacional, en su orden (idem)
  M1…M7   métricas de aceptación (dominio/metricas.py; «Métricas» del mensaje fundacional)
  L-*     capas clásicas (docs/DISENO.md §3) · T-*  transversales · A-* artefactos de documentación (A-trl: docs/TRL.md)
  E1…E3   eurekas (cada uno con UNA preinscripción; sus corridas descienden de ella)

    python3 plan/construir_dag.py              # genera plan.json
    python3 plan/construir_dag.py --comprobar  # sólo compara (lo usa el test)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dag_lib as D  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
N: list[dict] = []


def n(id, fase, tipo, titulo, dep, entrega, hecho, cubre):
    N.append(dict(id=id, fase=fase, tipo=tipo, titulo=titulo, depende_de=dep, entrega=entrega,
                  hecho_cuando=hecho, cubre=cubre, estado="pendiente"))


# ───────────── F0 · Fundación ─────────────
n("F0.00", "F0", "infra", "Repo git con la identidad del usuario", [], "repo QRECAUDA con git y rama main",
  "git log muestra al usuario como autor y committer", ["T-empaquetado"])
n("F0.01", "F0", "infra", "uv, pyproject y árbol de capas", ["F0.00"], "pyproject.toml, uv.lock y src/qrecauda/ con las capas de docs/DISENO.md §3",
  "uv sync termina sin error y el árbol coincide con DISENO §3", ["T-empaquetado"])
n("F0.02", "F0", "doc", "FUNDAMENTO, DISENO y GLOSARIO", ["F0.01"], "docs/FUNDAMENTO.md, docs/DISENO.md, docs/GLOSARIO.md, tests/arquitectura/test_glosario.py",
  "objetivo, alcance, limitaciones, tabla O1–O7/R1–R6 contra el mensaje fundacional, mapa de capas y vocabulario sin términos con dos sentidos; un test cruza el glosario con los tipos públicos de src/", ["A-fundamento"])
n("F0.03", "F0", "decision", "Decisiones D-001…D-008", ["F0.02"], "docs/decisiones/D-001.md … D-008.md",
  "una decisión por archivo con motivo, fecha y cómo se revertiría", ["A-decisiones", "D-001", "D-002", "D-003", "D-004", "D-005", "D-006", "D-007", "D-008"])
n("F0.04", "F0", "infra", "Contratos de imports y trinquetes de arquitectura", ["F0.01"], ".importlinter y tests/arquitectura/",
  "lint-imports pasa con 7 contratos y un import prohibido sembrado a propósito lo hace fallar", ["C-contratos"])
n("F0.05", "F0", "infra", "DAG verificable, registro append-only y ESTADO.md generado", ["F0.01"], "plan/plan.json, registro/nodos.jsonl, ESTADO.md, tests/test_dag_estandar.py",
  "python3 plan/dag.py validar sale en verde y ESTADO.md coincide con su regeneración", ["A-dag"])
n("F0.06", "F0", "infra", "RETOMA.md y CLAUDE.md del repo", ["F0.05"], "RETOMA.md y CLAUDE.md",
  "una sesión nueva sabe por dónde seguir leyendo sólo esos dos ficheros y ESTADO.md", ["A-retoma"])
n("F0.07", "F0", "infra", "Hooks commit-msg (sin atribución) y pre-push (CI local)", ["F0.00", "F0.08"], "scripts/hooks/commit-msg, scripts/hooks/pre-push, scripts/instalar_hooks.sh y tests/arquitectura/test_sin_atribucion.py",
  "git config core.hooksPath apunta a scripts/hooks; un commit con trailer de modelo se rechaza, un push con la CI local en rojo se rechaza y el test recorre toda la historia", ["R-sin-atribucion"])
n("F0.08", "F0", "infra", "CI local: ruff, mypy, lint-imports, pytest y DAG", ["F0.04", "F0.05"], "scripts/ci_local.sh",
  "un comando corre todo lo anterior y sale distinto de cero si algo falla; se corre ANTES de empujar", ["T-empaquetado"])
n("F0.09", "F0", "infra", "Remotos: GitHub público y espejo bare", ["F0.07"], "scripts/remotos.md con origin y espejo, sin ningún token",
  "primer push a origin y al espejo en F:/REPOSITORIOS/espejos/QRECAUDA.git; la credencial se pasa por ruta", ["T-seguridad"])

n("R.00", "F0", "revision", "Revisión adversarial del diseño, antes de construir", ["F0.02", "F0.03"], "docs/informes/REVISION_DISENO_R00.md",
  "un agente independiente intentó romper arquitectura y DAG (28 hallazgos); cada uno verificado contra el texto o el código y aceptado, degradado o rechazado con motivo, y el aceptado entra al tablero antes que al DAG", ["A-honestidad"])

# ───────────── F1 · Dominio puro ─────────────
n("F1.01", "F1", "dominio", "Bits inmutable y errores con nombre", ["F0.04"], "src/qrecauda/dominio/bits.py, src/qrecauda/dominio/errores.py, tests/dominio/",
  "Bits rechaza lo que no es 0/1 y no congela el array del llamante; hay una excepción raíz y cuatro hijas", ["L-dominio", "T-errores"])
n("F1.02", "F1", "dominio", "Extractores von Neumann, Peres y Toeplitz con LHL", ["F1.01"], "src/qrecauda/dominio/extractores.py, tests/dominio/test_bits_y_extractores.py",
  "von Neumann quita el sesgo medido; Toeplitz coincide con la matriz densa mod 2 (y por FFT con el producto exacto a n ≥ 2e5), es lineal sobre GF(2) y longitud_segura aborta cuando no sale ni un bit; el test de sembrado usa un directorio temporal, nunca src/", ["O4"])
n("F1.03", "F1", "dominio", "Entropía, métricas M1–M7 y Muestra con su origen", ["F1.01"], "src/qrecauda/dominio/entropia.py, src/qrecauda/dominio/metricas.py, src/qrecauda/dominio/muestra.py",
  "umbrales en un solo sitio, desigualdad estricta, veredicto conjuntivo; Muestra lleva procedencia (backend, job_id, versión) y HARDWARE_IBM sin job_id no se construye; una mitigación que no conserva los bits por disparo degrada el Origen a PRNG_CLASICO; np.random vetado en dominio/", ["M1", "M2"])

# ───────────── F2 · Puertos, aplicación y bala trazadora ─────────────
n("F2.01", "F2", "infra", "Puertos (Protocol) y datos con esquema versionado", ["F1.03"], "src/qrecauda/puertos/__init__.py, src/qrecauda/datos/__init__.py",
  "diez puertos como Protocol: los siete actuales más EstimadorDeEntropia, EstimadorDeSesgo (⟨Z⟩ con y sin mitigar) y FuenteDeSemilla; ZNE/PEC no se disfrazan de Mitigador", ["L-puertos"])
n("F2.02", "F2", "adaptador", "Línea base PRNG y validador estadístico propio", ["F2.01"], "src/qrecauda/adaptadores/prng.py, src/qrecauda/adaptadores/estadistica.py, tests/adaptadores/test_vectores_nist.py",
  "monobit y runs reproducen los ejemplos publicados de NIST SP 800-22 (p = 0,527089, 0,109599, 0,147232, 0,500798) con |Δp| < 1e-6; χ² de bytes exige ≥ 10 240 bits y falla con EntropiaInsuficiente; el PRNG es reproducible por semilla", ["M3", "M4", "M5"])
n("F2.03", "F2", "aplicacion", "Orquestador del pipeline (bala trazadora)", ["F1.02", "F2.01"], "src/qrecauda/aplicacion/pipeline.py, tests/aplicacion/",
  "fuente → Peres → Toeplitz → clave corre con cualquier FuenteDeBits y Resultado trae M1, M3, M4 y M5 en tres puntos (muestra cruda, mitigada, clave) más h_min de entrada y de salida; EstimadorDeEntropia sustituye al MCV directo", ["L-aplicacion"])
n("F2.04", "F2", "infra", "Transversales: configuración, observabilidad, reproducibilidad, seguridad, concurrencia", ["F2.01"], "src/qrecauda/transversal/",
  "configuración inmutable con clave desconocida que aborta, BLAS a un hilo forzado, secretos sólo por ruta y candado de máquina", ["T-config", "T-observabilidad", "T-reproducibilidad", "T-seguridad", "T-concurrencia"])
n("F2.05", "F2", "infra", "Presentación, fachada pública y CLI", ["F2.03", "F2.04", "F2.06"], "src/qrecauda/presentacion/__init__.py, src/qrecauda/api.py, src/qrecauda/entrada/cli.py, src/qrecauda/entrada/codigos.py, src/qrecauda/composicion.py, tests/arquitectura/test_api.py",
  "la CLI es un cliente más de la fachada, un test congela sus firmas, cada excepción tiene su código de salida y la regla de transversales (C6) se cumple en composicion y entrada", ["L-presentacion", "L-api"])

n("F2.06", "F2", "adaptador", "Capa de datos: InformeCorrida versionado y Almacén JSON append-only", ["F2.01", "F1.03"], "src/qrecauda/datos/informe.py, src/qrecauda/adaptadores/almacen_json.py, tests/adaptadores/test_almacen_e_informe.py",
  "esquema 2 con semilla, sha256 de la muestra cruda, epsilon, profundidad de Peres, validador, sha de la preinscripción y commit; esquemas de E2 y E3; una sola función leer_esquema que rechaza el futuro; serialización canónica, registro append-only y atómico (incluido registro/corridas/) e ida y vuelta exacta", ["L-datos"])

n("F2.07", "F2", "aplicacion", "Correr y juzgar: de la declaración al veredicto", ["F2.05", "F2.06", "R.00"], "src/qrecauda/aplicacion/juez.py, tests/aplicacion/test_juez.py",
  "qrecauda correr declaraciones/E1.toml escribe registro/corridas/<id>.json por el Almacén; qrecauda juzgar E1 aplica el criterio de la declaración, añade una línea a veredictos.jsonl y se niega si la preinscripción no precede a la corrida en git (merge-base --is-ancestor) o falta un control", ["L-aplicacion"])

# ───────────── F3 · Spikes y adaptadores cuánticos ─────────────
n("S.01", "F3", "insumo", "Spike de versiones: qiskit, aer, runtime, mthree y nistrng en un mismo entorno", ["F0.01", "R.00"], "spikes/S01_versiones/RESULTADO.md, spikes/S01_versiones/resultado.json, requirements.txt, .python-version",
  "la combinación exacta que instala y corre un circuito queda fijada con == en requirements.txt y uv.lock; el resultado.json dice qué extra choca con cuál (⚠️ mthree puede no soportar el qiskit actual) y qué paquete falta para transpilación y 90B", ["R2"])
n("S.02", "F3", "insumo", "Spike de alcance de la mitigación: ¿TREX, ZNE y PEC actúan sobre bitstrings?", ["S.01"], "spikes/S02_mitigacion_alcance/RESULTADO.md, spikes/S02_mitigacion_alcance/resultado.json, docs/decisiones/D-009.md",
  "por técnica: ¿conserva los bits por disparo?, ¿corre local con Aer?, ¿qué observable la mide? (⚠️ mthree devuelve cuasi-probabilidades: si no conserva bits, F4.01 implementa twirling con máscara X y XOR clásico y mthree queda de contraste); la decisión se registra como D-009", ["R4"])
n("S.03", "F3", "insumo", "Spike de honestidad: el muestreo de AerSimulator es pseudoaleatorio", ["S.01"], "spikes/S03_aer_pseudoaleatorio/RESULTADO.md, spikes/S03_aer_pseudoaleatorio/resultado.json",
  "se demuestra con la misma semilla ⇒ los mismos bits, y se fija qué puede y qué no puede afirmar la demo sobre entropía cuántica", ["A-honestidad"])
n("S.04", "F3", "insumo", "Spike del estimador SP 800-90B: qué herramienta, instalable y probada", ["S.01"], "spikes/S04_90b/RESULTADO.md, spikes/S04_90b/resultado.json",
  "una herramienta elegida, instalable con uv sync --extra validacion o con un script documentado, que devuelve h para tres señales sintéticas (IID sesgada, Markov, determinista) y documenta su mínimo de muestras; reimplementar la fórmula en numpy haría al evaluador no independiente", ["A-honestidad"])
n("F3.01", "F3", "adaptador", "Circuito H⊗n + medición sobre AerSimulator con SamplerV2", ["S.01", "S.03", "F2.01"], "src/qrecauda/adaptadores/aer/__init__.py, tests/adaptadores/test_aer.py",
  "devuelve una Muestra con Origen.SIMULADOR_AER usando PUBs y get_bitstrings, sin red ni credenciales; el orden de los bits es qubit-mayor (todos los disparos del qubit 0, luego el 1…) y un test lo fija", ["O1", "R2"])
n("F3.02", "F3", "adaptador", "Modelo de ruido del backend: lectura asimétrica, relajación y cross-talk", ["F3.01"], "src/qrecauda/adaptadores/aer/ruido.py, tests/adaptadores/test_ruido.py",
  "el canal de lectura se escribe como matriz de confusión y su sesgo inyectado coincide con el medido dentro de su error; además de tres niveles sintéticos hay un nivel realista con NoiseModel.from_backend sobre un backend falso (⚠️ sin verificar que exista en la versión fijada); Pauli-Lindblad y NoiseLearnerV3 se declaran no aplicables en local", ["O2", "R1"])
n("F3.03", "F3", "adaptador", "Transpilación guiada (AIRouting / StagedPassManager) con salida local", ["F3.01"], "src/qrecauda/adaptadores/aer/transpilacion.py, tests/adaptadores/test_transpilacion.py",
  "el circuito sale en forma ISA; si el servicio de IA no está disponible, cae a un pass manager local y lo registra", ["R3"])
n("F3.04", "F3", "adaptador", "SamplerV2 sobre hardware IBM con Batch/Session (opcional)", ["F3.03", "F2.04"], "src/qrecauda/adaptadores/ibm_runtime.py, tests/adaptadores/test_ibm_runtime.py",
  "contract test sin red con un doble, token por ruta, transpilación inyectada desde la composición; el doble NO puede devolver HARDWARE_IBM sin job_id (lo impide Muestra); la corrida real es F3.06", ["L-integracion"])

n("F3.06", "F3", "decision", "Acceso a hardware IBM: corrida real o constancia de no acceso", ["F3.04"], "docs/decisiones/D-010.md y registro/corridas/HW.json",
  "o bien una corrida real con job_id, backend y versión (TRL de la fuente cuántica sube a lo que T.TRL diga), o bien una constancia fechada de que no hay acceso; las dos cierran el nodo y ninguna cambia el resto del plan", ["A-honestidad"])

n("F3.05", "F3", "infra", "Composición y configuración de la demo con Aer ruidoso y mitigación", ["F3.02", "F4.01", "F5.01"], "src/qrecauda/composicion.py, src/qrecauda/transversal/configuracion.py, tests/arquitectura/test_configuracion.py",
  "Configuracion(backend='aer_ruidoso', mitigacion='lectura', nivel_ruido=…, validador=…) corre de punta a punta, un_hilo y entorno() se aplican desde la composición y una clave desconocida sigue abortando", ["L-integracion", "T-reproducibilidad"])

# ───────────── F4 · Mitigación ─────────────
n("F4.01", "F4", "adaptador", "Mitigación de lectura (TREX / mthree) como puerto Mitigador", ["S.02", "F3.02"], "src/qrecauda/adaptadores/mthree.py, tests/adaptadores/test_mthree.py",
  "dada una muestra con sesgo de lectura conocido, devuelve otra marcada mitigada con menos sesgo y conservando los bits por disparo (si la técnica remuestrea, el Origen se degrada); la técnica sale de D-009", ["O3"])
n("F4.02", "F4", "adaptador", "ZNE y PEC/PNA sobre el observable de sesgo ⟨Z⟩", ["S.02", "F3.02"], "src/qrecauda/adaptadores/zne_pec.py, tests/adaptadores/test_zne_pec.py",
  "ZNE y PEC implementan EstimadorDeSesgo donde D-009 dice que tienen sentido, reportan ⟨Z⟩ con y sin mitigar, y contra ruido de lectura declaran «sin efecto esperado» con una corrida de puerta que lo muestra", ["R4"])

# ───────────── F5 · Validación independiente ─────────────
n("F5.01", "F5", "adaptador", "Batería NIST SP 800-22 con nistrng y contraste con el validador propio", ["F2.02", "S.01"], "src/qrecauda/adaptadores/nist.py, tests/adaptadores/test_nist.py",
  "nistrng y adaptadores/estadistica coinciden en monobit y runs con |Δp| < 1e-6 sobre 100 secuencias; M5 se contrasta con scipy.stats.chisquare y con frequency_within_block; el criterio es la proporción de aprobados sobre N secuencias (SP 800-22 §4.2) y no un p único", ["O5"])
n("F5.02", "F5", "adaptador", "Min-entropía SP 800-90B y contraste con la cota MCV del dominio", ["F1.03", "S.04"], "src/qrecauda/adaptadores/min_entropia.py, tests/adaptadores/test_min_entropia.py",
  "implementa EstimadorDeEntropia con la herramienta que eligió S.04: una fuente de Markov con permanencia 0,8 da h ≤ 0,4 y longitud_segura recorta la clave; una IID sesgada da h ≈ −log2(p_max); exige ≥ 10^6 muestras o falla con EntropiaInsuficiente", ["M2"])

n("F5.05", "F5", "aplicacion", "Dimensionado conservador: el mínimo entre MCV, 90B y la contabilidad de entropía de la fuente", ["F5.02", "F2.03"],
  "src/qrecauda/dominio/entropia.py, src/qrecauda/aplicacion/pipeline.py, tests/dominio/test_entropia_conservadora.py y tests/aplicacion/test_pipeline_conservador.py",
  "el pipeline acepta un estimador que toma el mínimo de las cotas (MCV sobre todo el pool, 90B sobre un prefijo declarado) y un estimador de fuente que acota la entropía total por la de la muestra cruda; sin ellos se comporta exactamente como en 0.1.0 (regresión); con una fuente Markov o periódica la clave sale más corta que con MCV y nunca más larga; sin muestra suficiente para el 90B aborta con EntropiaInsuficiente", ["M2"])

# ───────────── F6 · Caso de uso peruano ─────────────
n("F6.01", "F6", "adaptador", "Cifrado AES-256-GCM con clave QRNG", ["F2.01"], "src/qrecauda/adaptadores/aes_gcm.py, tests/adaptadores/test_aes_gcm.py",
  "clave de 256 bits y nonce de 96 bits cortados de bloques consecutivos distintos de la clave certificada; un cursor de consumo impide entregar dos veces el mismo trozo; ida y vuelta, rechazo de un texto alterado y de un nonce repetido con la misma clave", ["O6"])
n("F6.02", "F6", "aplicacion", "Transacción de peaje/Metro cifrada con la clave certificada", ["F2.03", "F6.01"], "src/qrecauda/aplicacion/transaccion.py, tests/aplicacion/test_transaccion.py",
  "una transacción simulada se cifra, se descifra y se verifica; la clave sale de Resultado.clave de un pipeline con Origen declarado y la demo con Aer se rotula «validación del pipeline», no «entropía cuántica»", ["A-caso-de-uso"])
n("F6.03", "F6", "adaptador", "Reserva asíncrona de claves: productor en otro proceso y consumidor con registro de consumo", ["F6.02", "F2.07"],
  "src/qrecauda/aplicacion/reserva_asincrona.py, src/qrecauda/aplicacion/ejecutor_e3b.py, src/qrecauda/adaptadores/productor_en_proceso.py, src/qrecauda/adaptadores/temporizador_local.py, tests/aplicacion/test_ejecutor_e3b.py, tests/adaptadores/test_productor_en_proceso.py y tests/integracion/test_e3b_real.py",
  "un proceso spawn fijado a su núcleo genera claves aprobadas por M1–M5 con la cadena de E3 y las entrega por una cola acotada; el consumidor toma trozos de 352 bits sin repetir (clave, nonce), cifra y descifra, cuenta las esperas y declara la reserva agotada; la clave cruza en memoria y nunca se imprime ni se escribe; el ejecutor de E3b y su juez se prueban con dobles y con la cadena real a demanda diminuta", ["L-integracion"])

# ───────────── Eurekas ─────────────
n("P.E0", "E", "decision", "Parámetros y aritmética de la cadena, fijados antes de medir", ["F2.03", "R.00"], "docs/preinscripciones/PARAMETROS.md y declaraciones/PARAMETROS.toml",
  "qubits, shots, bits crudos necesarios (la clave es ≈ 0,3 de lo crudo), semillas, N de secuencias NIST, repeticiones n ≥ 3 por eureka, M2 sobre bloques de 4096 bits (no sobre 256) y el 90B sobre ≥ 10^6 bits; si falta muestra se suben los shots, no se relajan los umbrales", ["M2"])
n("P.E1", "E", "preinscripcion", "Preinscripción E1: el pipeline entrega claves que cumplen M1–M5 con entrada ruidosa", ["F2.03", "F2.07", "F0.02", "P.E0"], "docs/preinscripciones/E1.md y declaraciones/E1.toml",
  "criterio fijado ANTES de correr: la muestra cruda sin mitigar FALLA M1 o M3 al nivel de ruido declarado, la mitigada PASA y la clave PASA; controles negativo (un PRNG pasa) y positivo (fuentes malas rechazadas) declarados; regla de reintento sin elegir semilla", ["E1"])
n("C.E1a", "E", "corrida", "E1a · control: PRNG clásico pasa M1–M5 (la batería no distingue origen)", ["P.E1", "F5.01"], "registro/corridas/E1a.json",
  "la corrida del PRNG sale con su veredicto en los tres puntos; que pase es el resultado esperado y se declara", ["E1", "M3", "M4", "M5"])
n("C.E1b", "E", "corrida", "E1b · Aer ruidoso sin mitigar", ["P.E1", "F3.05", "F5.01"], "registro/corridas/E1b.json",
  "M1, M3, M4 y M5 sobre la muestra cruda ruidosa sin mitigar, y sobre la clave, al menos 3 repeticiones; el veredicto lee la muestra cruda, no sólo la clave", ["E1", "M3", "M4", "M5"])
n("C.E1c", "E", "corrida", "E1c · Aer ruidoso mitigado", ["P.E1", "F3.05", "F5.01", "F5.02"], "registro/corridas/E1c.json",
  "M1, M3, M4, M5 y la min-entropía de entrada y de salida sobre la muestra mitigada y sobre la clave, al menos 3 repeticiones", ["E1", "M3", "M4", "M5", "M2"])
n("C.E1d", "E", "corrida", "E1d · control positivo: fuentes defectuosas rechazadas, fuente ideal aceptada", ["P.E1", "F5.01", "F5.02", "F3.05"], "registro/corridas/E1d.json",
  "una fuente sesgada, una periódica y una de Markov (permanencia 0,8) son rechazadas por al menos una métrica o por h_min, la Markov pasa el MCV (≥ 0,9) y la rechaza el 90B (< 0,9), y la ideal pasa; sin esto un veredicto «pasa» no informa", ["E1"])
n("E1", "E", "eureka", "¡EUREKA 1! Pipeline de punta a punta con veredicto M1–M5 y control negativo", ["C.E1a", "C.E1b", "C.E1c", "C.E1d"], "registro/veredictos.jsonl",
  "las cuatro corridas cumplen su preinscripción y el informe dice, sin adornos, qué prueba y qué NO prueba sobre el origen cuántico", ["E1"])
n("P.E2", "E", "preinscripcion", "Preinscripción E2: la mitigación reduce el sesgo de lectura bajo el 1 %", ["F3.02", "S.02", "P.E0"], "docs/preinscripciones/E2.md y declaraciones/E2.toml",
  "tres niveles sintéticos más uno realista, factor mínimo de reducción y residuo máximo fijados antes de correr; declara qué técnica puede mover qué fuente de ruido y que «sin efecto esperado» de ZNE/PEC sobre lectura es un veredicto válido", ["E2"])
n("C.E2", "E", "corrida", "E2 · sesgo antes y después de TREX, ZNE y PEC en tres niveles de ruido", ["P.E2", "F4.01", "F4.02"], "registro/corridas/C.E2.json",
  "sesgo crudo y residual por técnica y por nivel, con su intervalo", ["E2", "M1"])
n("E2", "E", "eureka", "¡EUREKA 2! La mitigación mueve el sesgo bajo el umbral M1", ["C.E2"], "registro/veredictos.jsonl",
  "el residuo cumple M1 en los tres niveles o el veredicto lo dice con el nivel donde deja de cumplir", ["E2"])
n("P.E3", "E", "preinscripcion", "Preinscripción E3: tasa, latencia y caso de uso", ["F6.02", "F2.04", "P.E0"], "docs/preinscripciones/E3.md y declaraciones/E3.toml",
  "M6 = bits de clave por segundo de reloj de pared a un hilo; M7 = p95 sobre N ≥ 30 repeticiones tras 3 de calentamiento, extremo a extremo (fuente, mitigación, extracción, validación, cifrado); sin cola ni red de IBM; lote, hilos y máquina fijados antes de medir", ["E3"])
n("C.E3", "E", "medicion", "E3 · tasa sostenida, latencia y ciclo de cifrado, a un hilo y con candado", ["P.E3", "F6.02", "F5.02", "F3.05", "F5.01"], "registro/corridas/C.E3.json",
  "bit/s y ms medidos con reloj monotónico sobre el pipeline con Aer, N repeticiones y la máquina registrada, con la definición de M6 y M7 de la preinscripción", ["E3", "M6", "M7"])
n("E3", "E", "eureka", "¡EUREKA 3! Tasa y latencia dentro de umbral con la transacción cifrada", ["C.E3"], "registro/veredictos.jsonl",
  "M6 y M7 cumplen con el pipeline completo, o el veredicto dice cuál no y por cuánto", ["E3"])

# ───────────── F7 · Documentación, wiki y pitch ─────────────
n("F7.03", "F7", "doc", "Modelo de amenazas", ["F0.02", "F0.03"], "docs/AMENAZAS.md",
  "qué ataques cubre un QRNG, cuáles NO (el canal, la implementación, el HSM) y qué certifica y qué no certifica NIST", ["A-amenazas"])
n("P.E3b", "E", "preinscripcion", "Preinscripción E3b: la latencia de transacción con la clave de una reserva generada aparte", ["E3", "F6.03", "P.E0"], "docs/preinscripciones/E3b.md y declaraciones/E3b.toml",
  "arquitectura productor/consumidor, perfiles R1 (arranque, informativo) y R2 (régimen, decide), λ y duración, definiciones de tasa neta, latencia y espera, criterios T1–T3 con sus umbrales de M6/M7, controles U1–U5 y T4, núcleos y candado, limitaciones e hipótesis marcada, todo fijado antes de medir; E3 NO se reabre", ["E3b"])
n("C.E3b", "E", "medicion", "E3b · latencia y sostenibilidad con la clave de una reserva generada aparte", ["P.E3b", "F6.03", "F5.02", "F3.05", "F5.01"], "registro/corridas/C.E3b.json",
  "tasa neta del productor, p95 de las latencias, esperas y CPU/pared de cada proceso medidos con reloj monotónico a λ tx/s durante la duración declarada, en tres semillas, con la máquina registrada y los dos procesos en sus núcleos", ["E3b", "M6", "M7"])
n("E3b", "E", "eureka", "¡EUREKA 3b! La latencia de transacción cumple M7 con la clave de una reserva generada aparte", ["C.E3b"], "registro/veredictos.jsonl",
  "T1 (la tasa neta del productor supera M6 y el consumo), T2 (p95 < 500 ms) y T3 (cero esperas) cumplen en las tres semillas, o el veredicto dice cuál no y por cuánto", ["E3b"])
n("P.E5", "E", "preinscripcion", "Preinscripción E5: el control negativo del pipeline completo con fuentes defectuosas", ["E1", "F5.05", "P.E0"], "docs/preinscripciones/E5.md y declaraciones/E5.toml",
  "fuentes defectuosas (Markov con persistencia y periódica) y la fuente buena atraviesan la cadena completa; criterios por ambos lados (la defectuosa se rechaza o su clave se acorta por debajo de un techo analítico y de una fracción de la buena; la buena no se rechaza ni pierde más de una fracción declarada ni baja de M6), controles de validez, la medición HOY con MCV y el efecto del dimensionado sobre M6, todo fijado antes de medir", ["E5"])
n("F5.06", "F5", "aplicacion", "Ejecutor de E5: defectos sobre Aer con twirling real y el juez del control negativo", ["P.E5", "F5.05", "F3.05", "F5.01"],
  "src/qrecauda/adaptadores/defectos.py, src/qrecauda/aplicacion/ejecutor_e5.py, src/qrecauda/aplicacion/juez.py, src/qrecauda/datos/informe.py, tests/aplicacion/test_ejecutor_e5.py y tests/adaptadores/test_defectos.py",
  "un defecto (persistencia de Markov o patrón periódico) se aplica a la salida de Aer y a la del twirling real; el ejecutor corre la cadena con tres dimensionados sobre las mismas muestras y entrega artefactos tipados; el juez recalcula techo analítico, fracciones y controles de los datos crudos", ["L-integracion"])
n("C.E5", "E", "medicion", "E5 · control negativo del pipeline completo y efecto del dimensionado conservador", ["P.E5", "F5.06", "F5.02", "F3.05", "F5.01"], "registro/corridas/C.E5.json",
  "tres semillas; por fuente (buena, Markov, Markov fuerte, periódica) y por dimensionado (MCV, mínimo MCV-90B, conservador) la longitud de clave, M1–M5, h estimadas y tasa, con la máquina quieta y a un hilo", ["E5", "M6"])
n("E5", "E", "eureka", "¡EUREKA 5! La cadena rechaza o acorta la clave de una fuente defectuosa y no rechaza la buena", ["C.E5"], "registro/veredictos.jsonl",
  "los criterios de P.E5 cumplen en las tres semillas por ambos lados, o el veredicto dice cuál no y por cuánto", ["E5"])
n("F7.06", "F7", "infra", "Prueba de integración: Aer → mitigación → extracción → validación → AES-GCM → descifrado", ["F6.02", "F3.05"], "tests/integracion/test_e2e_aer.py",
  "la cadena completa corre sin red en la CI local y el texto descifrado es igual al original", ["L-integracion"])
n("T.TRL", "F7", "doc", "Matriz de TRL por componente, derivada de la evidencia", ["F0.02", "F3.06", "F7.06", "E1", "E2", "E3"], "docs/TRL.md y tests/arquitectura/test_trl.py",
  "una fila por componente con su evidencia (id de nodo y de corrida), el TRL alcanzado sin hardware y con él; el TRL del sistema es el de la fila más baja; TRL 4 pide repetibilidad n ≥ 3, protocolo preinscrito y que un tercero pueda auditarlo; el test falla si una fila cita un nodo inexistente", ["A-trl"])
n("F7.05", "F7", "doc", "Wiki repo: mapas, bases e incidencias publicados en la bóveda", ["F0.05", "F0.06", "F2.05"], "docs/wiki/wiki.json y docs/wiki/",
  "publicar.py termina sin rechazos, la nota puerta enlaza los índices y el vault_audit no marca huérfanas", ["W-wiki"])
n("F7.01", "F7", "doc", "Notebook reproducible con versiones exactas", ["E1", "E2", "E3"], "notebooks/qrecauda.ipynb, src/qrecauda/presentacion/figuras.py, tests/presentacion/test_figuras.py",
  "un clon limpio reproduce las tablas del pitch con dos comandos y los pins de uv.lock; el notebook sólo llama a presentacion/figuras.py, que tiene su test", ["O7", "R5"])
n("F7.02", "F7", "doc", "Pitch de 10 slides", ["E1", "E2", "E3", "F7.03", "T.TRL"], "docs/pitch/PITCH.md, tests/arquitectura/test_cifras_del_pitch.py",
  "las diez láminas con cada cifra marcada {{corrida:ID.métrica}} y un test que la cruza con registro/corridas/; la lámina de límites dice «validación del pipeline», no «entropía cuántica», con el TRL de T.TRL", ["R6"])
n("F7.04", "F7", "doc", "Roadmap TRL 4 → TRL 5 → piloto → producción", ["E3", "F3.06", "F7.03", "T.TRL"], "docs/ROADMAP.md",
  "qué evidencia falta para cada salto de TRL, empezando por el hardware real y la certificación formal que NO se hace en la hackatón", ["A-roadmap"])

n("P.E4", "E", "preinscripcion", "Preinscripción E4: el hardware de IBM frente a su gemelo en Aer", ["F3.04", "P.E0"], "docs/preinscripciones/E4.md y declaraciones/E4.toml",
  "tres trabajos de 100 000 disparos (1 PUB cruda y 7 con twirling) en hardware real y su gemelo en Aer con la calibración del mismo backend; H1 (sesgo por qubit dentro de una tolerancia declarada) y H2 (la clave del twirling pasa M1–M5), controles N1, S1 y V1, lo que NO afirma y qué no está verificado, todo fijado antes de correr", ["E4"])
n("F3.07", "F3", "adaptador", "Camino a hardware: FuenteIbm con twirling por PUBs, presupuesto de QPU, ensayo y qrecauda hardware", ["P.E4", "F3.04", "F3.05", "F5.01"],
  "src/qrecauda/adaptadores/ibm_runtime.py, src/qrecauda/aplicacion/ejecutor_e4.py, src/qrecauda/aplicacion/juez_e4.py, scripts/ibm_run.sh, docs/HARDWARE.md y tests/aplicacion/test_e4.py",
  "el ensayo contra un backend falso recorre selección de backend, transpilación ISA, SamplerV2, twirling, gemelo y registro del trabajo; el tope --max-segundos-qpu aborta antes de enviar; el ejecutor y el juez de E4 recalculan N1, S1, V1, H1 y H2 de los artefactos; docs/HARDWARE.md paso a paso", ["L-integracion"])
n("C.E4", "E", "corrida", "E4 · tres trabajos en hardware de IBM y su gemelo en Aer", ["P.E4", "F3.07", "F5.02"], "registro/corridas/C.E4.json",
  "tres trabajos reales con job_id, backend y versión del SDK, más su gemelo en Aer, las cinco corridas C.E4a a C.E4e por semilla y el sesgo por qubit; bloqueada hasta que haya credencial de IBM", ["E4"])
n("E4", "E", "eureka", "¡EUREKA 4! El hardware real coincide con su gemelo y su clave con twirling pasa M1–M5", ["C.E4"], "registro/veredictos.jsonl",
  "H1 y H2 de P.E4 cumplen en los tres trabajos, o el veredicto dice cuál no y por cuánto; no certifica origen cuántico", ["E4"])
n("F7.07", "F7", "aplicacion", "qrecauda demo: PRNG, Aer y Aer con twirling lado a lado, con AES-GCM y rótulo de origen", ["F6.02", "F3.05", "F5.02"],
  "src/qrecauda/aplicacion/demo.py, src/qrecauda/api.py y tests/aplicacion/test_demo.py",
  "dos minutos como máximo, determinista con semilla, sin red ni credencial; tabla con M1, min-entropía, tres p-valores NIST y bits de clave; un peaje y un trayecto de Metro cifrados y descifrados; rótulo «simulado» salvo hardware real", ["R6"])
n("F7.08", "F7", "doc", "Cuaderno vivo: del circuito a la clave cifrada, con FUENTE aer o ibm", ["F7.07", "F3.07"], "notebooks/qrecauda_vivo.ipynb y tests/presentacion/test_cuaderno_vivo.py",
  "corre en menos de dos minutos con nbclient y queda guardado con sus salidas: circuito, ISA, SamplerV2, twirling, Peres y Toeplitz, NIST, AES-GCM y la tabla; una celda de parámetros cambia la fuente", ["O7"])

# ───────────── Cierre ─────────────
n("R.01", "R", "revision", "Revisión adversarial propia previa al release 0.1.0", ["E1", "E2", "E3", "F7.01", "F4.02", "T.TRL", "F7.06"], "docs/informes/REVISION_ADVERSARIAL_0.1.0.md",
  "un agente independiente intentó romper las claims con las eurekas y las mediciones ya hechas; cada hallazgo verificado contra el texto y registrado; esta revisión es distinta de R.00", ["A-honestidad"])
n("REL-0.1.0", "R", "release", "Release 0.1.0: pipeline QRNG reproducible en simulador (rótulo de TRL según T.TRL)", ["R.01", "F7.02", "F7.04", "F0.09", "F7.05"], "docs/releases/EXPEDIENTE_0.1.0.md, CHANGELOG.md y tests/arquitectura/test_release_sin_dudas.py",
  "expediente con alcance, arquitectura, pruebas, validación contra línea base, despliegue y límites; el título dice lo que T.TRL sostiene; un test falla si queda un ⚠️ sin verificar vigente en FUNDAMENTO o en las decisiones", ["T-empaquetado"])
n("R.02", "R", "revision", "Revisión adversarial propia previa al release 0.2.0", ["E3b", "F6.03", "T.TRL", "E5", "F5.05"], "docs/informes/REVISION_ADVERSARIAL_0.2.0.md",
  "un agente independiente intentó romper E3b y la reserva asíncrona con la medición ya hecha; cada hallazgo verificado contra el texto y registrado; es distinta de R.01", ["A-honestidad"])
n("R.02c", "R", "aplicacion", "Correcciones de los hallazgos de R.02 en el código: presupuesto QPU, claves reproducibles, productor, 90B, demo y CI", ["E3b", "F6.03", "F5.05", "F3.07"], "src/qrecauda/ (ibm_runtime, presupuesto_qpu, reserva_asincrona, productor_en_proceso, min_entropia, dimensionado, composicion), docs/decisiones/D-011.md y sus tests",
  "cada hallazgo de código de R.02 tiene su test; E3b conserva la regla de semilla que se midió; ci_local pasa; lo que no se corrigió queda dicho con su motivo", ["A-honestidad"])
n("REL-0.2.0", "R", "release", "Release 0.2.0: la reserva asíncrona de claves y la latencia de E3b", ["REL-0.1.0", "R.02", "R.02c", "E3b", "T.TRL"], "docs/releases/EXPEDIENTE_0.2.0.md y CHANGELOG.md",
  "expediente con el alcance añadido a 0.1.0, el veredicto de E3b tal como salió (CUMPLE o NO_CUMPLE), la arquitectura de la reserva, las pruebas, el rótulo de TRL que T.TRL sostiene y los límites; E3 sigue como la dejó su veredicto", ["T-empaquetado"])

n("R.03", "R", "revision", "Revisión adversarial propia previa al release 0.3.0", ["E4", "F3.07", "F7.08", "T.TRL"], "docs/informes/REVISION_ADVERSARIAL_0.3.0.md",
  "un agente independiente intentó romper E4, el ensayo y la demo con lo ya medido; cada hallazgo verificado contra el texto y registrado; es distinta de R.02", ["A-honestidad"])
n("REL-0.3.0", "R", "release", "Release 0.3.0: el camino a hardware de IBM y la demo", ["REL-0.2.0", "R.03", "E4"], "docs/releases/EXPEDIENTE_0.3.0.md y CHANGELOG.md",
  "expediente con el veredicto de E4 tal como salió, el camino a hardware, la demo y el cuaderno vivo, y los límites; sin corrida real de IBM no se publica con la etiqueta de hardware", ["T-empaquetado"])

def construir() -> dict:
    conf = D.Config.leer(RAIZ / "plan" / "dag.json")
    plan = {"proyecto": conf.proyecto, "version_plan": 1, "fecha": "2026-10-07", "degradaciones": {}, "nodos": N}
    previo = D._git(RAIZ, "show", "HEAD:plan/plan.json")
    anterior = json.loads(previo)["nodos"] if previo else None
    fallos = D.validar(N, RAIZ, conf, anterior, plan["degradaciones"])
    if fallos:
        raise SystemExit("✗ el plan viola dag_lib, no se escribe plan.json:\n  " + "\n  ".join(fallos))
    return plan


def main(argv: list[str]) -> int:
    texto = json.dumps(construir(), ensure_ascii=False, indent=1) + "\n"
    destino = RAIZ / "plan" / "plan.json"
    if "--comprobar" in argv:
        return 0 if destino.exists() and destino.read_text() == texto else 1
    destino.write_text(texto)
    print(f"→ {destino.relative_to(RAIZ)}: {len(N)} nodos")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
