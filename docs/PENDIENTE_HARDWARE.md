# Manual de lo que falta: la corrida en hardware real de IBM

Lo único pendiente de QRECAUDA es ejecutar E4 en un ordenador cuántico de IBM, juzgarlo y publicar 0.3.0. Todo lo demás está hecho y publicado (0.2.0, tag `v0.2.0`, DAG de 79 nodos en verde). Este manual recoge los pasos en orden, con los comandos exactos. El detalle técnico está en [`HARDWARE.md`](HARDWARE.md).

Estado del DAG en el punto de partida: `C.E4` bloqueado («sin credencial IBM»), `E4`, `R.03` y `REL-0.3.0` abiertos.

## Qué necesitas antes de empezar

| cosa | detalle |
|---|---|
| Cuenta de IBM Quantum | con una API key creada en el panel |
| Token en un fichero | **fuera del repo**, en un disco Linux (no `/mnt/...`), con `chmod 600`. Se pasa siempre por ruta, nunca por valor |
| Instancia (opcional) | CRN o nombre, si tu cuenta tiene varias |
| Cuota de QPU | mírala en el panel. E4 estima ≈ 85 s de QPU para los 3 trabajos y el tope por omisión es 120 s. La cuota real del plan abierto es ⚠️ sin verificar |
| `uv`, `git`, `python3` | el entorno `.venv` se borró al cerrar; se recrea en el paso 1 |

Ejemplo para guardar el token sin que aparezca en pantalla ni en el historial del shell:

```bash
mkdir -p ~/.secretos && chmod 700 ~/.secretos
read -rs -p "Pega el token y pulsa Enter: " T && printf '%s' "$T" > ~/.secretos/ibm_quantum.txt && unset T
chmod 600 ~/.secretos/ibm_quantum.txt
```

En los pasos siguientes `RUTA_TOKEN` es `~/.secretos/ibm_quantum.txt` (expándelo a la ruta completa).

## Paso 1. Recrear el entorno

```bash
cd ~/Documents/REPOSITORIOS/QRECAUDA
git pull --ff-only origin main
git status --short                      # debe salir vacío
uv sync --frozen --group dev --extra cuantico --extra mitigacion --extra validacion --extra cifrado
bash spikes/S04_90b/build_nist.sh       # compila el binario del NIST 90B en ~/.cache/qrecauda/nist90b/
```

Comprobación rápida de que todo está sano:

```bash
python3 plan/dag.py validar             # esperado: 79 nodos · reglas en verde
PATH=$PWD/.venv/bin:$PATH .venv/bin/pytest -q    # esperado: 883 passed
```

## Paso 2. Ensayo (sin credencial y sin gastar cuota)

```bash
scripts/ibm_run.sh ensayo
```

Recorre todo el camino contra el backend falso `fake_sherbrooke` y tarda del orden de medio minuto. No escribe en `registro/`; escribe en `salidas/ensayo_e4/` y el script lo borra al empezar la siguiente vez.

Debe salir «15 informes» (5 corridas × 3 semillas) y ningún error. Si no sale, **no sigas**: arregla antes de gastar cuota.

## Paso 3. Comprobar que el token funciona (sin gastar QPU)

Opcional pero recomendable. Ejecuta la demo con una rama de hardware pequeña: un único trabajo de 16 000 a 40 000 disparos.

```bash
scripts/ibm_run.sh demo RUTA_TOKEN [BACKEND]
```

Si falla por credencial o instancia, vuelve al paso de la tabla inicial. Para ver la selección de backend sin enviar nada, usa el paso 2.

## Paso 4. Corrida real de E4

Condiciones que el script comprueba solo:
- `declaraciones/E4.toml` y `docs/preinscripciones/E4.md` están commiteados y sin cambios. **No se tocan nunca.** Si necesitas cambiar un criterio, es otro experimento con otra preinscripción.
- el token tiene modo 0600 o 0400.

```bash
scripts/ibm_run.sh real RUTA_TOKEN [BACKEND]
```

Variantes útiles:

```bash
MAX_SEGUNDOS_QPU=200 scripts/ibm_run.sh real RUTA_TOKEN ibm_brisbane   # otro tope y otro backend
uv run --no-sync qrecauda hardware --token-file RUTA_TOKEN --instancia "MI_CRN"   # elegir instancia
uv run --no-sync qrecauda hardware --token-file RUTA_TOKEN --ia                   # enrutado con IA (degrada con aviso si falta qiskit_ibm_transpiler)
```

Qué ocurre:
- envía **3 trabajos**, uno por semilla (20261007, 20261008, 20261009), y espera cada uno. La cola puede tardar horas; deja el terminal abierto o usa `tmux`.
- si el tope o la cuota no alcanzan para los tres, aborta con **código 11 antes de enviar el primero**. Sube `MAX_SEGUNDOS_QPU` o espera a la cuota del mes siguiente.
- si un trabajo se cae a medias, quedan los artefactos de las semillas ya hechas y el error explica cómo recuperar el `job_id` desde la cola del servicio. No relances a ciegas: gastarías cuota duplicada.
- escribe en `registro/corridas/` los ficheros `C.E4_<semilla>_informe_NNN.json` y `C.E4a` … `C.E4e`.

### Códigos de salida que puedes encontrar

| código | significa | qué hacer |
|---|---|---|
| 2 | argumento mal formado (token inexistente, `MAX_SEGUNDOS_QPU` inválido) | corrige el comando |
| 3 | token legible por otros, o preinscripción con cambios sin commit | `chmod 600` o `git restore` de los ficheros de preinscripción |
| 11 | el presupuesto de QPU no alcanza | sube el tope o espera cuota |

## Paso 5. Juzgar

```bash
uv run --no-sync qrecauda juzgar E4
```

Escribe una línea en `registro/veredictos.jsonl` con el veredicto de H1 y H2 y los controles N1, S1 y V1.

**El veredicto se publica tal como sale.** Si E4 da NO CUMPLE, se publica NO CUMPLE, con la causa. No se ajustan tolerancias después de ver los datos. Un resultado negativo honesto es un hallazgo válido para el concurso; uno retocado lo invalida todo.

Qué mirar antes de contar nada:
- el `job_id` y el backend de cada informe: es lo único que prueba que los bits salieron de un dispositivo;
- H1: diferencia por qubit entre sesgo crudo del hardware y el de su gemelo en Aer (tolerancia 0,03, ⚠️ arbitraria);
- H2: la clave tras el twirling pasa M1–M5 (débil por construcción: Peres + Toeplitz limpian sesgo);
- calibración del backend (fecha, T1, T2, error de lectura) en el registro de cada trabajo.

## Paso 6. Cerrar el DAG

Cada cierre exige un commit que toque la entrega del nodo, y la línea del registro lleva ese sha. Se hace en este orden:

```bash
# 1) Commitea las corridas y el veredicto (por rutas concretas, nunca `git add -A`)
git add registro/corridas/C.E4*.json registro/veredictos.jsonl
git commit -m "C.E4: corrida real en hardware de IBM (backend, job_id, semillas)" -- registro/corridas registro/veredictos.jsonl
git rev-parse --short HEAD              # este sha es la evidencia de C.E4 y de E4
```

Después añade al final de `registro/nodos.jsonl` (append-only: no edites las líneas anteriores) las líneas de los nodos, con el sha del commit que tocó su entrega:

```json
{"nodo":"C.E4","estado":"hecho","evidencia":"SHA_DEL_COMMIT","fecha":"AAAA-MM-DD"}
{"nodo":"E4","estado":"juzgado","veredicto":"registro/veredictos.jsonl#E4","evidencia":"SHA_DEL_COMMIT","fecha":"AAAA-MM-DD"}
```

Mira el formato exacto de `E3b` y `E5` en `registro/nodos.jsonl` y cópialo. Luego:

```bash
python3 plan/dag.py validar
python3 plan/dag.py estado               # regenera ESTADO.md
python3 plan/dag.py siguiente            # debe proponer R.03
```

## Paso 7. Poner al día lo que cuenta el resultado

Solo con el veredicto ya escrito, y sin inflar:

| fichero | qué cambia |
|---|---|
| `docs/TRL.md` | E4 sube el TRL de la fuente solo si H1 cumple; el del sistema no sube por una sola corrida |
| `docs/pitch/PITCH.md`, `DECK.md`, `GUION.md` | añade la cifra de hardware con el `job_id` y el backend; quita «sin hardware» solo donde ya no sea cierto |
| `README.md`, `docs/HARDWARE.md` | sustituye «todavía no tiene una sola ejecución en hardware» por la corrida real |
| `docs/pitch/deck.pdf` | regenera con `bash docs/pitch/construir.sh` |

Después de editar, comprueba que las cifras citadas siguen saliendo de una corrida nombrada:

```bash
PATH=$PWD/.venv/bin:$PATH .venv/bin/pytest -q tests/arquitectura/test_cifras_del_pitch.py
```

Palabras prohibidas si el origen sigue sin demostrarse: «clave cuántica certificada» y «certificada aleatoria». La estadística de NIST no mide origen cuántico.

## Paso 8. Revisión adversarial R.03 y release 0.3.0

La regla 7 del DAG exige una revisión propia por release. Es la misma mecánica que R.02:

1. Lanza un agente independiente de solo lectura que intente romper E4, el ensayo y lo que dice el pitch sobre el hardware. Que lea solo los documentos del repo, no el chat.
2. Verifica cada hallazgo contra el texto antes de aceptarlo, corrige lo cierto y escribe `docs/informes/REVISION_ADVERSARIAL_0.3.0.md` (con una sección «Lo que sigue abierto»).
3. Cierra `R.03` en el registro con el sha del commit que toca ese informe.
4. Escribe `docs/releases/EXPEDIENTE_0.3.0.md` (alcance, arquitectura, cómo se probó, resultados con script y denominador, despliegue, limitaciones) y la entrada fechada en `CHANGELOG.md`.
5. Sube la versión (`pyproject.toml`, `__version__`, `CITATION.cff`, `uv.lock`).
6. Pasa la suite completa y el CI local:

```bash
python3 plan/dag.py validar && python3 plan/dag.py estado --comprobar
PATH=$PWD/.venv/bin:$PATH .venv/bin/pytest -q
```

7. Publica. El hook `pre-push` corre el CI local. **Sin atribución a ningún modelo** en commits, tag ni release (el hook `commit-msg` la bloquea).

```bash
git push origin main && git push espejo main
git tag -a v0.3.0 -m "QRECAUDA 0.3.0"
git push origin v0.3.0 && git push espejo v0.3.0
gh release create v0.3.0 --title "QRECAUDA 0.3.0" --notes-file docs/releases/EXPEDIENTE_0.3.0.md
gh run list --limit 1                    # espera a que el CI de GitHub termine en success
```

8. Cierra `REL-0.3.0` en el registro con el sha del commit de la entrega. Si E4 no cumple, el release se publica igualmente con el veredicto tal como salió, pero **sin** la etiqueta de hardware validado.

## Paso 9. Limpiar el entorno

```bash
bash scripts/limpiar_entorno.sh
```

Borra `.venv`, las cachés y los paquetes del SDK cuántico de la caché de uv. Borra también el token si ya no lo necesitas: `shred -u ~/.secretos/ibm_quantum.txt`.

## Si algo sale mal

| síntoma | causa probable | qué hacer |
|---|---|---|
| `qrecauda demo` no corre | instalaste sin extras | repite el comando `uv sync` del paso 1 |
| `uv run` quita los extras | `uv run` a secas resincroniza | usa `uv run --no-sync` o `.venv/bin/qrecauda` |
| No encuentra el binario 90B | no se compiló | `bash spikes/S04_90b/build_nist.sh` |
| El ensayo falla | cambio local o dependencias | `git status`, repite el paso 1 y no sigas hasta que pase |
| Error de credencial o instancia | token caducado o instancia equivocada | genera otra API key; pasa `--instancia` |
| Código 11 | cuota o tope insuficiente | `MAX_SEGUNDOS_QPU=...` mayor, o espera |
| Un trabajo queda a medias | caída de red o del servicio | recupera el `job_id` desde la cola de IBM; no relances los tres |
| `dag.py validar` falla al cerrar | el commit de evidencia no toca la entrega del nodo | commitea la ruta de entrega del nodo y usa ese sha |
| Un test de cifras del pitch falla | el texto cita una cifra sin corrida nombrada | corrige el texto, no el test |
| Prisa por retocar una tolerancia tras ver datos | — | no. La preinscripción no se toca |

## Lo que sigue sin verificar (no lo afirmes)

1. Que el plan abierto admita trabajos de 100 000 disparos y cuánto QPU cargue cada uno.
2. `SamplerV2` está desaprobado en `qiskit-ibm-runtime` 0.50.0 (funciona; se evaluará el sustituto con el primer trabajo real).
3. Que `AerSimulator.from_backend` reproduzca la asimetría de lectura de un dispositivo real.
4. `--ia` con `qiskit_ibm_transpiler` instalado.
5. Que el hardware aporte aleatoriedad certificada: E4 mide estadística y fidelidad al gemelo, no origen.
