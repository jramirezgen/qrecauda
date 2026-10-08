"""Toda cifra de resultado del pitch y del deck lleva un marcador y el marcador resuelve contra el registro (F7.02).

Se cruzan dos documentos, ``docs/pitch/PITCH.md`` y ``docs/pitch/DECK.md``, con la misma gramática. Las cifras de
contexto del deck (Metro, peajes, NIST) no salen de una corrida: se atan con ``{{ref:docs/pitch/IMPACTO.md}}``, donde
figuran con su fuente y su etiqueta.

Gramática. Un marcador va pegado a la cifra que respalda: ``187{{corrida:C.E3.m6_bits_por_s:min/1000}}``.

    {{corrida:ID[filtro,...].ruta[:agregado][/divisor]}}
    {{trl:sistema}}
    {{ref:docs/ruta.md}}

``ID``       valor del campo ``corrida`` de los artefactos de ``registro/corridas/*.json`` (C.E1a, C.E1b, C.E1c,
             C.E1d, C.E2, C.E3, C.E3b, C.E5) o el nombre del archivo si no lo trae (HW). Los manifiestos (con ``artefactos``)
             no cuentan: sólo los artefactos por semilla.
``filtro``   ``campo=valor`` sobre el artefacto (p. ej. ``[nivel=medio,tecnica=zne]``). Todos deben cumplirse.
``ruta``     campo con puntos; un segmento entero indexa una lista (``etapas.cruda.0.1``).
``agregado`` sobre los artefactos que quedan tras el filtro, por semilla:
             ``min``, ``max``, ``mediana``, ``suma``, ``n`` (cuántos artefactos), ``ntrue`` (cuántos con valor
             verdadero), ``sem=<semilla>`` (el de esa semilla). Sin agregado se exige un único artefacto.
``divisor``  se divide el valor antes de comparar (kbit/s: ``/1000``).
La cifra escrita debe igualar el valor redondeado a los decimales con que se escribió (coma decimal; espacio
como separador de miles).

``trl:sistema``  la cifra es el «TRL del sistema» de docs/TRL.md.
``ref:ruta``     la cifra no sale de una corrida sino de un criterio preinscrito (p. ej. el umbral): debe aparecer
                 literalmente en ese documento.

Una cifra sin marcador falla; un marcador sin cifra pegada falla; un marcador que apunta a una corrida, filtro o
campo inexistente falla. Quedan fuera de «cifra de resultado» los identificadores (E1, M7, AES-256-GCM, R.00-1,
D-010), las versiones (0.1.0), las fechas, el rótulo «Lámina N», el front matter, los bloques de código y los destinos de enlaces.
"""

import json
import re
import statistics
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PITCH = RAIZ / "docs" / "pitch" / "PITCH.md"
DECK = RAIZ / "docs" / "pitch" / "DECK.md"
RUTAS = [PITCH, DECK]
MINIMO_DE_CIFRAS = {PITCH: 25, DECK: 12}
CORRIDAS = RAIZ / "registro" / "corridas"

NUM = r"\d+(?: \d{3})*(?:,\d+)?"
MARCADOR = re.compile(r"\{\{(corrida|trl|ref):([^{}]*)\}\}")
CIFRA_CON_MARCADOR = re.compile(rf"(?<![\w,])({NUM})\{{\{{(corrida|trl|ref):([^{{}}]*)\}}\}}")


def _artefactos():
    por_id: dict[str, list[dict]] = {}
    for p in sorted(CORRIDAS.glob("*.json")):
        d = json.loads(p.read_text())
        if "artefactos" in d:
            continue
        por_id.setdefault(d.get("corrida", p.stem), []).append(d)
    return por_id


ARTEFACTOS = _artefactos()


def _ruta(d, ruta):
    for seg in ruta.split("."):
        d = d[int(seg)] if isinstance(d, list) else d[seg]
    return d


def resolver_corrida(spec: str) -> float:
    candidatos = [k for k in ARTEFACTOS if spec.startswith(k) and spec[len(k) :][:1] in ("[", ".")]
    assert candidatos, f"corrida inexistente en registro/corridas/: {spec!r} (hay {sorted(ARTEFACTOS)})"
    cid = max(candidatos, key=len)
    m = re.fullmatch(r"(?:\[([^\]]*)\])?\.?([\w.]+?)(?::([\w=]+))?(?:/(\d+))?", spec[len(cid) :])
    assert m, f"marcador mal formado: {spec!r}"
    filtros, ruta, agg, div = m.groups()
    docs = ARTEFACTOS[cid]
    for f in filter(None, (filtros or "").split(",")):
        k, v = f.split("=", 1)
        assert any(k in d for d in docs), f"filtro sobre un campo que {cid} no tiene: {k!r}"
        docs = [d for d in docs if str(d.get(k)) == v]
    assert docs, f"el filtro [{filtros}] no deja ningún artefacto de {cid}"
    valores = []
    for d in docs:
        try:
            valores.append((d.get("semilla"), _ruta(d, ruta)))
        except (KeyError, IndexError, ValueError, TypeError):
            pytest.fail(f"el campo {ruta!r} no existe en un artefacto de {cid}")
    nums = [v for _, v in valores]
    if agg is None:
        assert len(valores) == 1, f"{cid}.{ruta} tiene {len(valores)} artefactos: declara un agregado"
        valor = nums[0]
    elif agg == "n":
        valor = len(nums)
    elif agg == "ntrue":
        valor = sum(1 for v in nums if v is True)
    elif agg in ("min", "max", "suma", "mediana"):
        assert all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in nums), f"{cid}.{ruta} no es numérico"
        valor = {"min": min, "max": max, "suma": sum, "mediana": statistics.median}[agg](nums)
    elif agg.startswith("sem="):
        sel = [v for s, v in valores if str(s) == agg[4:]]
        assert len(sel) == 1, f"{cid}: la semilla {agg[4:]} no da exactamente un artefacto"
        valor = sel[0]
    else:
        pytest.fail(f"agregado desconocido: {agg!r}")
    assert isinstance(valor, (int, float)) and not isinstance(valor, bool), f"{spec!r} no resuelve a un número"
    return valor / int(div) if div else valor


def _leer(cifra: str) -> tuple[float, int]:
    t = cifra.replace(" ", "")
    dec = len(t.split(",")[1]) if "," in t else 0
    return float(t.replace(",", ".")), dec


def _trl_sistema() -> int:
    m = re.search(r"\*\*TRL del sistema: (\d)\*\*", (RAIZ / "docs" / "TRL.md").read_text())
    assert m, "docs/TRL.md ya no declara «TRL del sistema: N»"
    return int(m.group(1))


def _cuerpo(ruta: Path = PITCH) -> str:
    t = ruta.read_text()
    assert t.startswith("---\n"), "falta el front matter"
    return t.split("\n---\n", 1)[1]


def _sin_ruido(texto: str) -> str:
    """Quita lo que no es cifra de resultado: código, destinos de enlaces, rótulos de lámina, fechas, identificadores."""
    t = re.sub(r"```.*?```", " ", texto, flags=re.S)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"\]\([^)]*\)", "]", t)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"^# Lámina \d+", "# Lámina", t, flags=re.M)
    t = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", t)
    t = re.sub(r"\b\d+\.\d+\.\d+\b", " ", t)  # versiones (0.1.0)
    t = re.sub(r"\bSP \d+(?:-\d+)?[A-Z]?\b", " ", t)
    # identificadores: cualquier palabra que mezcle letras y dígitos (E1, M7, AES-256-GCM, R.00-1, D-010, F7.02, 90B)
    t = re.sub(r"[\w.\-]*[A-Za-z][\w.\-]*\d[\w.\-]*|[\w.\-]*\d[\w.\-]*[A-Za-z][\w.\-]*", " ", t)
    return t


def _laminas(ruta: Path = PITCH):
    partes = re.split(r"(?m)^(?=# Lámina \d+)", _cuerpo(ruta))
    return [p for p in partes if p.startswith("# Lámina")]


def _marcadores(ruta: Path = PITCH):
    return list(CIFRA_CON_MARCADOR.finditer(_cuerpo(ruta)))


def _casos_de_marcadores():
    return [pytest.param(ruta, m, id=f"{ruta.stem}:{m.group(0)[:70]}") for ruta in RUTAS for m in _marcadores(ruta)]


def _por_ruta(f):
    return pytest.mark.parametrize("ruta", RUTAS, ids=lambda r: r.stem)(f)


# --- estructura -------------------------------------------------------------------------------------------------


@_por_ruta
def test_diez_laminas_numeradas(ruta):
    laminas = _laminas(ruta)
    assert len(laminas) == 10
    nums = [int(re.match(r"# Lámina (\d+)", p).group(1)) for p in laminas]
    assert nums == list(range(1, 11))


@_por_ruta
def test_cabecera_autor_y_sin_rutas_absolutas(ruta):
    texto = ruta.read_text()
    assert re.search(r"(?m)^author: kaitokid$", texto.split("\n---\n", 1)[0])
    assert not re.search(r"(?<![\w.])/(?:home|mnt|tmp|Users|root)/|[A-Za-z]:\\", texto)


@_por_ruta
def test_registro_de_publicacion(ruta):
    texto = ruta.read_text()
    assert "honestidad" not in texto.lower()
    assert not re.search(r"co-authored|generated with|claude|anthropic", texto, re.I)
    assert "—" not in _cuerpo(ruta), "sin rayas largas (stop-slop)"


@_por_ruta
def test_nunca_afirma_entropia_cuantica(ruta):
    assert "entropía cuántica" not in ruta.read_text().lower()


def test_la_lamina_de_limites_dice_validacion_del_pipeline_y_cita_el_trl():
    limites = next(p for p in _laminas() if re.match(r"# Lámina \d+ · Límites", p))
    assert "validación del pipeline" in limites
    assert "docs/TRL.md" in limites
    assert re.search(r"TRL del sistema \d+\{\{trl:sistema\}\}", limites) or re.search(r"TRL \d+\{\{trl:sistema\}\}", limites)
    assert "origen cuántico" in limites and "hardware" in limites.lower()


@_por_ruta
def test_la_lamina_de_hoja_de_ruta_apunta_a_roadmap(ruta):
    assert "docs/ROADMAP.md" in next(p for p in _laminas(ruta) if re.match(r"# Lámina \d+ · Hoja de ruta", p))


def test_el_deck_declara_que_sin_hardware_no_hay_origen_cuantico():
    deck = _cuerpo(DECK)
    assert "hardware" in deck.lower() and "origen" in deck.lower()
    assert re.search(r"TRL-3\{\{trl:sistema\}\}", deck), "el deck debe atar su TRL al de docs/TRL.md"


# --- cifras -----------------------------------------------------------------------------------------------------


@_por_ruta
def test_hay_cifras_marcadas(ruta):
    assert len(_marcadores(ruta)) >= MINIMO_DE_CIFRAS[ruta]


@pytest.mark.parametrize(("ruta", "m"), _casos_de_marcadores())
def test_cada_marcador_resuelve_y_coincide(ruta, m):
    cifra, tipo, spec = m.groups()
    escrito, dec = _leer(cifra)
    if tipo == "corrida":
        assert round(resolver_corrida(spec), dec) == pytest.approx(escrito, abs=10 ** -(dec + 3)), (
            f"{cifra} no coincide con {spec}: el registro da {resolver_corrida(spec)}"
        )
    elif tipo == "trl":
        assert spec == "sistema" and int(escrito) == _trl_sistema()
    else:
        ruta = RAIZ / spec
        assert ruta.is_file(), f"ref a un archivo inexistente: {spec}"
        assert re.search(rf"(?<![\w,]){re.escape(cifra)}(?![\w]|,\d)", ruta.read_text()), f"{cifra} no aparece en {spec}"


@_por_ruta
def test_todo_marcador_va_pegado_a_una_cifra(ruta):
    sueltos = len(MARCADOR.findall(_cuerpo(ruta))) - len(_marcadores(ruta))
    assert sueltos == 0, f"{sueltos} marcadores sin una cifra pegada a su izquierda"


@_por_ruta
def test_no_hay_cifra_de_resultado_sin_marcador(ruta):
    t = _sin_ruido(CIFRA_CON_MARCADOR.sub(" ", _cuerpo(ruta)))
    sobrantes = re.findall(rf"(?<![\w,]){NUM}(?![\w])", t)
    assert not sobrantes, f"cifras sin marcador: {sobrantes}"


# --- el propio test se vigila: un marcador falso tiene que fallar ---------------------------------------------


@pytest.mark.parametrize(
    "spec",
    [
        "C.E9.m6_bits_por_s:min/1000",
        "C.E3.no_existe:min",
        "C.E3.m6_bits_por_s",
        "C.E2[tecnica=nada].sesgo_residual:max",
        "C.E3.m6_bits_por_s:sem=1",
    ],
)
def test_un_marcador_roto_falla(spec):
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        resolver_corrida(spec)
