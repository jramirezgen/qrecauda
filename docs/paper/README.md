# Informe técnico (docs/paper)

Informe de QRecauda: planeación, método preinscrito y resultados de E1 y E2 (E3 pendiente).

| fichero | función |
|:--|:--|
| `paper.md` | texto fuente (Markdown de pandoc) |
| `paper.pdf` | informe compilado |
| `plantilla.tex` | plantilla LaTeX propia (banner, resumen enmarcado, tipografía) |
| `filtro.lua` | filtro de pandoc: numeración y referencias cruzadas, tablas, símbolo de advertencia |
| `figuras.py` | genera las figuras desde `plan/plan.json`, `registro/` y `registro/corridas/` |
| `construir.sh` | compila `paper.pdf` (requiere pandoc y xelatex) |
| `fig/` | figuras en PDF, SVG y PNG |

Reproducir, desde la raíz del repositorio:

```bash
.venv/bin/python docs/paper/figuras.py
bash docs/paper/construir.sh
```

Toda cifra procede de una corrida o veredicto nombrado del registro. No se citan rutas absolutas ni datos personales; el autor figura sólo con el alias «kaitokid».
