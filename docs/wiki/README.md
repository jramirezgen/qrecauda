# Wiki del repositorio (herramientas del autor)

Esta carpeta es *tooling* del autor, no parte del producto. Los generadores (`generar_*.py`, `publicar.py`, `archivar.py`) y su declaración (`wiki.json`, `wiki.lock.json`) publican mapas y tableros de este repositorio en una bóveda de Obsidian que sólo existe en la máquina del autor. Por eso `wiki.json` contiene **rutas locales de ese entorno** (la bóveda y sus carpetas), y `tests/test_dag_estandar.py` también: no se reproducen en otra máquina y no es necesario hacerlo.

Para quien lea o contribuya al repositorio, nada de esto interviene en el pipeline, en los experimentos ni en la CI. Los lienzos (`*.canvas`) y las bases (`*.base`) se pueden abrir con Obsidian, pero no hacen falta para entender el proyecto: el estado vive en `registro/` y `ESTADO.md`.
