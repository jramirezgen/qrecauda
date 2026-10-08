# Remotos de QRecauda

| remoto | dónde | uso |
|---|---|---|
| `origin` | https://github.com/jramirezgen/qrecauda (público, Apache-2.0) | publicación; el espejo `bare` lo respalda |
| `espejo` | espejo `bare` local en el disco F: (`REPOSITORIOS/espejos/QRECAUDA.git`) | respaldo; no se edita |

- Identidad: la historia de git lleva la identidad de git del dueño del repo (decisión suya; la misma cuenta del remoto público). El informe (`docs/paper`) es anónimo, con el alias «kaitokid». No se reescribe la historia.
- Credencial: `gh auth login` (almacén de credenciales de `gh`), nunca un token en el repo ni en la URL. Ver `docs/AMENAZAS.md`.
- El hook `pre-push` corre `scripts/ci_local.sh`: con la CI en rojo el push no sale.
- Los commits no llevan atribución a ningún modelo (hook `commit-msg`).
- Empujar a ambos: `git push origin main && git push espejo main`.
