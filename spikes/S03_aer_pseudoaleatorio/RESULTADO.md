# S.03 — AerSimulator es pseudoaleatorio (qiskit 2.5.2, qiskit-aer 0.17.2)

Reproducir: `uv run python spikes/S03_aer_pseudoaleatorio/run.py` (H⊗8, 2048 disparos). Datos y hashes sha256: `resultado.json`.

## Resultados comprobados
- Misma semilla (42), dos corridas: bitstrings idénticos disparo a disparo, en `AerSimulator.run` y en `SamplerV2` → `misma_semilla_identica = true`.
- Semillas 42 vs 43: secuencias distintas en ambos → `semillas_distintas_distintas = true`.
- Con `NoiseModel` + `ReadoutError` y semilla fija: sigue determinista (y distinto del caso sin ruido) → `con_ruido_determinista = true`.
- `backend` y `sampler` con seed=42 dan el mismo hash (mismo flujo pseudoaleatorio).
- Sin semilla, dos corridas difirieron en esta ejecución.

## Origen de la semilla sin fijar
- Comprobado: `SamplerV2(seed=None)` pasa `seed_simulator=None` a `backend.run` (`sampler_v2.py:166-173`); la opción por defecto del backend es `None`.
- Comprobado: el binario C++ de Aer importa `std::random_device`.
- ⚠️ sin verificar: que la semilla por defecto salga de `std::random_device` (entropía del SO) y no de otro mecanismo; no se leyó el fuente C++.

## Qué PUEDE afirmar la demo
- Valida el pipeline (circuito → muestreo → bitstrings → hash/posproceso) con salida reproducible.
- Prueba que, con semilla fija, el resultado es una función determinista de la semilla y del circuito.
- Prueba que el modelo de ruido de lectura se aplica y también es reproducible con semilla.

## Qué NO PUEDE afirmar la demo
- No demuestra entropía cuántica: el simulador genera bits con un PRNG clásico.
- No sirve para estimar calidad de aleatoriedad cuántica ni para claves reales con semilla fija (predecible por quien la conozca).
- Que la salida sin semilla "parezca" impredecible no la hace cuántica; su origen sería el SO o el PRNG (⚠️ sin verificar).
- Solo hardware real puede reclamar origen cuántico, y aun así sin prueba de Bell (o equivalente) no se certifica ese origen.
