# RETOMA — QRECAUDA (una página)

1. Lee `ESTADO.md` y corre `python3 plan/dag.py siguiente`.
2. Objetivo: `docs/FUNDAMENTO.md` (§Objetivo y §Objetivos por rama). Arquitectura: `docs/DISENO.md`.
3. Hecho en código pero **sin commitear** (se cierra el nodo al commitear): F1.01–F1.03, F2.01–F2.06, F0.04, F0.07, F0.08.
4. Lo siguiente con sentido: commitear → cerrar nodos en `registro/nodos.jsonl` (línea nueva con el sha) → spikes S.01–S.03
   (¿conviven qiskit y mthree? ¿qué acepta SamplerV2? ¿Aer es pseudoaleatorio?) → F3.01.
5. Pendiente de decisión del usuario: acceso a hardware IBM (F3.04) y remoto en GitHub (F0.09).
