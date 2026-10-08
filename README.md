# QRecauda

Entropía cuántica certificada (QRNG) para la recaudación del Perú — Track 4, Hackatón Qiskit IBM Lima.

Pipeline: `FuenteDeBits → [Mitigador] → Peres → Toeplitz(LHL) → Validador → Clave → AES-GCM`.

## Empezar

```bash
uv sync --group dev          # núcleo: numpy + scipy
./scripts/ci_local.sh        # ruff · mypy · lint-imports · DAG · pytest
uv run qrecauda              # bala trazadora con el PRNG de línea base
uv sync --extra cuantico --extra mitigacion --extra validacion --extra cifrado   # cuando toquen F3–F6
```

## Dónde está cada cosa

| qué | dónde |
|---|---|
| por dónde seguir | `RETOMA.md` → `ESTADO.md` → `python3 plan/dag.py siguiente` |
| objetivo, alcance, discrepancias con el manifiesto | `docs/FUNDAMENTO.md` |
| arquitectura (datos · lógica · integración · transversales) | `docs/DISENO.md` |
| vocabulario | `docs/GLOSARIO.md` |
| decisiones | `docs/decisiones/` |
| plan verificable | `plan/` + `registro/` |
| wiki (se lee y se edita en Obsidian) | `docs/wiki/` → bóveda `wiki/QRECAUDA/` |
