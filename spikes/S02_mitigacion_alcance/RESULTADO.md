# S.02 · Alcance de la mitigación sobre bitstrings por disparo

Fecha: 2026-10-07 · Reproducir: `uv run python spikes/S02_mitigacion_alcance/run.py` · Datos: `resultado.json`.
Ruido de lectura: p(1|0)=0.02, p(0|1)=0.08 (sesgo analítico de H⊗8: 0.0300). 100 000 disparos, semillas 11/22/33.

| Técnica | Bits por disparo | Local (Aer) | Observable | Mueve sesgo de lectura |
| --- | --- | --- | --- | --- |
| SamplerV2 options | sí (twirling, DD) ⚠️ sin verificar | no | bitstrings | ⚠️ sin verificar |
| mthree 3.0.0 | **no** | sí | cuasi-probabilidades de conteos | sí: 0.0299 -> 0.0016 |
| Twirling propio (X + XOR) | **sí** | sí | bitstrings | sí: 0.0299 -> 0.0020 |
| ZNE | no | no | valores esperados (Estimator) | no: 0.0600 -> 0.0600 |
| PEC | no | no ⚠️ sin verificar | valores esperados (Estimator) | no ⚠️ sin verificar |

## 1. SamplerV2.options
Campos de `SamplerOptions` (v0.50.0): default_shots, dynamical_decoupling, environment, execution, experimental, max_execution_time, simulator, twirling. Rechazados con ValidationError: `resilience_level`, `resilience` (incluye `measure_mitigation`, `zne_mitigation`). Solo de EstimatorV2: `resilience`, `resilience_level`, `default_precision`, `seed_estimator`. Aceptados: `twirling.enable_measure/enable_gates/num_randomizations/shots_per_randomization/strategy` y `dynamical_decoupling`.
Twirling en Sampler: existe, pero se ejecuta en el servicio de IBM; no hay forma local de comprobar que el resultado conserve bits por disparo ni cuánto mueve el sesgo. ⚠️ sin verificar (se espera que sí, porque SamplerV2 solo expone `get_bitstrings()` por disparo).

## 2. mthree
`apply_correction` devuelve cuasi-probabilidades sobre conteos; `M3Mitigation` no tiene método por disparo. Sesgo medio por qubit: antes 0.0299, después 0.0016 (por semilla 0.00191/0.00162/0.00144; sin probabilidades negativas). Bitstrings sin remuestrear con PRNG: no.

## 3. Twirling propio
500 bloques x 200 disparos, máscara X por qubit y bloque, XOR clásico tras medir. Conserva N bits por disparo. Sesgo medio 0.0299 -> 0.0020 (0.00172/0.00141/0.00287 por semilla), a la altura del ruido estadístico (~0.0025 con 100 000 disparos). Límite: el canal queda simetrizado (p efectiva 0.05), no eliminado; para H⊗n el bit sale uniforme. Estados no uniformes: ⚠️ sin verificar.

## 4. ZNE / PEC
Actúan sobre valores esperados: opciones `resilience.zne_mitigation`/`pec_mitigation` solo en EstimatorOptions; `qiskit_mitigation` 0.1.1 trae GateFolding, PEC, PEA, TREX, zne. mitiq no está instalado. Prueba mínima de ZNE (plegado 1,3,5, solo ruido de lectura): |<Z>| = 0.0600 en los tres factores y tras extrapolar a 0.0600 (el plegado de puertas no toca la lectura). PEC no se ejecutó; ⚠️ sin verificar que corra con Aer.
