# Del simulador al hardware de IBM

Cómo pasar QRECAUDA del simulador (Aer) a un ordenador cuántico de IBM, qué esperar y qué NO afirmar. Todo lo que dice «⚠️ sin verificar»
no se ha comprobado contra un dispositivo real: este repositorio todavía no tiene una sola ejecución en hardware (nodos C.E4 y E4 abiertos,
causa «sin credencial IBM»).

## Qué hay hecho

| pieza | dónde | estado |
|---|---|---|
| fuente `FuenteIbm` (selección de backend, transpilación ISA, `SamplerV2`, twirling con PUBs, registro por trabajo) | `adaptadores/ibm_runtime.py` | probada contra un backend falso (`fake_sherbrooke`) |
| presupuesto de QPU (`--max-segundos-qpu`) | `dominio/presupuesto_qpu.py` | aborta ANTES de enviar; la estimación es ⚠️ sin verificar |
| enrutado con IA (`--ia`) | `adaptadores/aer/transpilacion.py` | ⚠️ `qiskit_ibm_transpiler` no está instalado; degrada a transpilación local CON aviso |
| experimento E4 (3 trabajos, hardware frente a su gemelo en Aer) | `declaraciones/E4.toml`, `docs/preinscripciones/E4.md` | preinscrito; sin correr |
| `qrecauda demo --fuente ibm` | `composicion.demo_de` | ensayada; con hardware real, ⚠️ sin verificar |

Disponible en 0.2.0 (sin publicar): `qrecauda demo --dimensionado {mcv,conservador}` y `--instancia INSTANCIA` (CRN o nombre; también en `qrecauda hardware`) para elegir la instancia de IBM.

## 1. Una vez: cuenta, token e instancia

1. Crea una cuenta en la plataforma de IBM Quantum y, en el panel, una **API key**.
2. Guarda el token en un fichero **fuera del repositorio**, con permisos `600`. Se pasa siempre **por ruta**
   (`--token-file RUTA` o la variable `QRECAUDA_IBM_TOKEN_FILE`), nunca por valor, y no se imprime ni truncado.
3. Anota la cuota que tu plan declara en el panel (⚠️ sin verificar aquí: el plan abierto da una cuota mensual de minutos de QPU que
   cambia con el tiempo). La estimación de E4 son ≈ 85 s para los 3 trabajos; el tope por omisión de la corrida es 120 s.

## 2. Ensayo (sin credencial, sin cuota)

```bash
scripts/ibm_run.sh ensayo
```

Equivale a `qrecauda hardware --ensayo` (con los extras instalados: instala `uv sync --frozen --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado`; ejecuta con `.venv/bin/qrecauda` o `uv run --no-sync`, porque `uv run` a secas puede quitar los extras). Recorre TODO el camino (backend, transpilación ISA, `SamplerV2`, twirling, gemelo, los cinco
pipelines por semilla, el registro de cada trabajo) contra `fake_sherbrooke`. Tarda del orden de medio minuto. Los bits los pone Aer:
el origen queda `simulador_aer` y **nada se escribe en `registro/`**, sino en `salidas/ensayo_e4/`. El control V1 (trabajos reales)
falla a propósito: un ensayo no es una medición. Bórralo con `rm -rf salidas/ensayo_e4` (el script lo hace solo).

Antes de gastar cuota, mira:
- que salga «15 informes» (5 corridas × 3 semillas) y que ningún error aborte;
- el sesgo por qubit del «hardware» frente al del gemelo (`reporte.sesgos_por_qubit`).

## 3. La demo con una rama de hardware (opcional, pocos disparos)

```bash
scripts/ibm_run.sh demo RUTA_TOKEN [BACKEND]
```

Añade a la tabla de la demo dos filas (IBM sin mitigar / con twirling) con un único trabajo de 16 000 a 40 000 disparos. Sólo con un
`job_id` real el rótulo deja de decir «simulado» y pasa a decir que los bits vienen del dispositivo.

## 4. La corrida real (E4)

Requisitos: `declaraciones/E4.toml` y `docs/preinscripciones/E4.md` **commiteados y sin cambios** (no se tocan nunca después de preinscribir).

```bash
scripts/ibm_run.sh real RUTA_TOKEN [BACKEND]     # MAX_SEGUNDOS_QPU=<s> para otro tope
uv run --no-sync qrecauda juzgar E4
```

El primer comando envía **3 trabajos** (uno por semilla) y los espera (la cola puede tardar horas: la corrida no toma el candado de
máquina). Si el tope o la cuota restante no alcanzan para los tres, aborta con código 11 **antes de enviar el primero**. Un trabajo que
se cae a medias deja los artefactos de las semillas ya hechas; el error nombra cómo recuperar el `job_id` de la cola del servicio.
La corrida real escribe en `registro/corridas/` (`C.E4_<semilla>_informe_NNN.json` y `C.E4a`…`C.E4e`); `juzgar` aplica H1 y H2.

## 5. Qué mirar

- **El `job_id` y el backend** de cada informe: es lo único que prueba que los bits salieron de un dispositivo.
- **H1:** diferencia por qubit entre el sesgo crudo del hardware y el de su gemelo en Aer (tolerancia 0,03, ⚠️ arbitraria).
  Un qubit con la lectura asimétrica puede dar un sesgo grande: con el backend falso se vio ≈ 0,24 en un qubit frente a ≈ 0,003 del
  gemelo. Es información, no un fallo.
- **H2:** la clave tras el twirling pasa M1–M5. ⚠️ Es débil por construcción (hallazgo R.00-1): Peres + Toeplitz limpian sesgo.
  Por eso H1 lleva el peso.
- **Cola y ejecución:** `reporte.trabajo` guarda tiempos de cola y de ejecución y el uso de QPU que IBM cargó; son informativos.
- **Deriva:** calibración del backend (fecha, T1, T2, error de lectura por qubit) en el registro de cada trabajo.

## 6. Qué NO decir

- Que la clave «es cuántica» o «certificada aleatoria»: NIST y la cota MCV miden estadística, no origen. Un PRNG pasa las mismas pruebas
  (control N1).
- Que el simulador demuestra algo sobre el dispositivo: Aer es pseudoaleatorio. Si la fuente no es un `job_id` real, el rótulo dice «simulado».
- Cualquier cifra de hardware antes de que exista `registro/corridas/C.E4*.json` de una corrida real.

## ⚠️ Sin verificar

1. Que el plan abierto admita trabajos sueltos de 100 000 disparos y cuánto QPU carguen (el estimador usa un retardo por disparo y 3 s
   fijos por trabajo, aún sin contrastar con un cargo real).
2. `SamplerV2` está desaprobado en `qiskit-ibm-runtime` 0.50.0 (sigue funcionando; el sustituto se evaluará cuando exista el primer
   trabajo real). Se emite un `DeprecationWarning` visible.
3. El formato de los sellos de tiempo de las métricas del trabajo.
4. Que `AerSimulator.from_backend` reproduzca la asimetría de lectura de un dispositivo real.
5. `--ia` (enrutado con IA) con la API instalada.
