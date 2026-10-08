# docs/paper

`paper.md` es la fuente del informe técnico (español, pandoc-markdown). `paper.pdf` se genera a partir de él.

Regenerar el PDF (usa `pandoc` y `xelatex` ya instalados; no instala nada):

```bash
docs/paper/construir.sh
```

Sin pandoc/LaTeX, `paper.md` se lee tal cual. Reglas: toda cifra remite a una corrida de `registro/corridas/` o a un spike; lo no corrido lleva
«PENDIENTE: corrida X» y se sustituye por su tabla cuando la corrida y su veredicto existan; lo marcado ⚠️ es hipótesis.
