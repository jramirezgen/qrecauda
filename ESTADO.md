# ESTADO de QRECAUDA

> GENERADO por `dag.py estado` desde `plan/plan.json` y `registro/`. No se edita a mano.

Plan v1 · 2026-10-07

## Nodos del plan (59)

| estado | nodos |
|---|---|
| hecho | 32 |
| pendiente | 27 |

## En curso, bloqueados y pausados

- ninguno

## Listos

- **F0.09** Remotos: GitHub privado y espejo bare
- **F2.05** Presentación, fachada pública y CLI
- **P.E3** Preinscripción E3: tasa, latencia y caso de uso
- **F3.04** SamplerV2 sobre hardware IBM con Batch/Session (opcional)
- **F4.02** ZNE y PEC/PNA sobre el observable de sesgo ⟨Z⟩
- **P.E2** Preinscripción E2: la mitigación reduce el sesgo de lectura bajo el 1 %
- **F3.05** Composición y configuración de la demo con Aer ruidoso y mitigación

## Hechos y juzgados

| nodo | estado | evidencia | título |
|---|---|---|---|
| F0.00 | hecho | `a5bf535` | Repo git con la identidad del usuario |
| F0.01 | hecho | `a5bf535` | uv, pyproject y árbol de capas |
| F0.02 | hecho | `b11f4eb` | FUNDAMENTO, DISENO y GLOSARIO |
| F0.03 | hecho | `a5bf535` | Decisiones D-001…D-008 |
| F0.04 | hecho | `564dc94` | Contratos de imports y trinquetes de arquitectura |
| F0.05 | hecho | `a5bf535` | DAG verificable, registro append-only y ESTADO.md generado |
| F0.06 | hecho | `d9609a1` | RETOMA.md y CLAUDE.md del repo |
| F0.07 | hecho | `d9609a1` | Hooks commit-msg (sin atribución) y pre-push (CI local) |
| F0.08 | hecho | `a5bf535` | CI local: ruff, mypy, lint-imports, pytest y DAG |
| R.00 | hecho | `564dc94` | Revisión adversarial del diseño, antes de construir |
| F1.01 | hecho | `0419140` | Bits inmutable y errores con nombre |
| F1.02 | hecho | `0419140` | Extractores von Neumann, Peres y Toeplitz con LHL |
| F1.03 | hecho | `0419140` | Entropía, métricas M1–M7 y Muestra con su origen |
| F2.01 | hecho | `564dc94` | Puertos (Protocol) y datos con esquema versionado |
| F2.02 | hecho | `564dc94` | Línea base PRNG y validador estadístico propio |
| F2.03 | hecho | `564dc94` | Orquestador del pipeline (bala trazadora) |
| F2.04 | hecho | `a898076` | Transversales: configuración, observabilidad, reproducibilidad, seguridad, concurrencia |
| F2.06 | hecho | `73c4c42` | Capa de datos: InformeCorrida versionado y Almacén JSON append-only |
| S.01 | hecho | `7856f4e` | Spike de versiones: qiskit, aer, runtime, mthree y nistrng en un mismo entorno |
| S.02 | hecho | `7856f4e` | Spike de alcance de la mitigación: ¿TREX, ZNE y PEC actúan sobre bitstrings? |
| S.03 | hecho | `7856f4e` | Spike de honestidad: el muestreo de AerSimulator es pseudoaleatorio |
| S.04 | hecho | `7856f4e` | Spike del estimador SP 800-90B: qué herramienta, instalable y probada |
| F3.01 | hecho | `5312674` | Circuito H⊗n + medición sobre AerSimulator con SamplerV2 |
| F3.02 | hecho | `5312674` | Modelo de ruido del backend: lectura asimétrica, relajación y cross-talk |
| F3.03 | hecho | `5312674` | Transpilación guiada (AIRouting / StagedPassManager) con salida local |
| F4.01 | hecho | `a9bd306` | Mitigación de lectura (TREX / mthree) como puerto Mitigador |
| F5.01 | hecho | `42b54c9` | Batería NIST SP 800-22 con nistrng y contraste con el validador propio |
| F5.02 | hecho | `42b54c9` | Min-entropía SP 800-90B y contraste con la cota MCV del dominio |
| F6.01 | hecho | `aea23de` | Cifrado AES-256-GCM con clave QRNG |
| F6.02 | hecho | `a7cd133` | Transacción de peaje/Metro cifrada con la clave certificada |
| P.E0 | hecho | `f8e21d0` | Parámetros y aritmética de la cadena, fijados antes de medir |
| F7.03 | hecho | `d9609a1` | Modelo de amenazas |
