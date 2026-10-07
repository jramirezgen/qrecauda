# S.01 — versiones (2026-10-07)

Evidencia: `run.py` → `resultado.json`. Entorno: Python 3.13.14, `uv.lock` + `requirements.txt` con `==`.

- **Conviven** qiskit 2.5.2, qiskit-aer 0.17.2, qiskit-ibm-runtime 0.50.0, mthree 3.0.0 (importa y trae `M3Mitigation`),
  nistrng 1.2.3 y cryptography 50.0.2 en el mismo entorno.
- Aer + `SamplerV2` + `get_bitstrings()` corre un H⊗8 de 1000 disparos (8 bits por muestra).
- **Falta** `qiskit-ibm-transpiler` (F3.03): no está en ningún extra. `F3.03` usa el pass manager local y lo registra; instalarlo
  es opcional y no bloquea nada.
- ⚠️ sin verificar: que mthree 3.0.0 *funcione* (no solo importe) con qiskit 2.5.2; lo comprueba `S.02`.
- 90B: no hay paquete en los extras; lo decide `S.04`.
