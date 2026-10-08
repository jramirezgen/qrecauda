#!/usr/bin/env python3
"""Figuras del informe técnico, generadas desde los datos del repositorio (nada se teclea a mano).

Lee   plan/plan.json, registro/nodos.jsonl, registro/veredictos.jsonl, registro/corridas/*.json y `git log`.
Escribe docs/paper/fig/<nombre>.{pdf,svg,png}.

Uso (desde la raíz del repo, con el entorno del proyecto):
    .venv/bin/python docs/paper/figuras.py            # todas
    .venv/bin/python docs/paper/figuras.py pipeline   # sólo una

Paleta Okabe-Ito (apta para daltonismo); cada figura repite en texto lo que codifica el color.
"""
from __future__ import annotations

import glob
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = Path(__file__).resolve().parent / "fig"

# ── paleta Okabe-Ito ──────────────────────────────────────────────────────────────────────────
NEGRO, NARANJA, CIELO, VERDE = "#000000", "#E69F00", "#56B4E9", "#009E73"
AMARILLO, AZUL, BERMELLON, PURPURA = "#F0E442", "#0072B2", "#D55E00", "#CC79A7"
GRIS, GRIS_CLARO, TINTA = "#8A8A8A", "#E6E6E6", "#1A1A1A"


def aclara(color: str, f: float = 0.80) -> str:
    """Mezcla un color con blanco (f = fracción de blanco)."""
    c = np.array(matplotlib.colors.to_rgb(color))
    return matplotlib.colors.to_hex(c * (1 - f) + f)


def _fuentes() -> None:
    for ruta in ("/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheros-regular.otf",
                 "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheros-bold.otf",
                 "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheros-italic.otf"):
        if Path(ruta).exists():
            font_manager.fontManager.addfont(ruta)
    plt.rcParams.update({
        "font.family": ["TeX Gyre Heros", "DejaVu Sans"], "font.size": 7.5,
        "axes.titlesize": 8, "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
        "legend.fontsize": 7, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "pdf.fonttype": 42, "svg.fonttype": "path", "axes.spines.top": False, "axes.spines.right": False,
        "mathtext.fontset": "dejavusans", "figure.dpi": 100, "savefig.dpi": 220,
    })


# ── datos ─────────────────────────────────────────────────────────────────────────────────────
def leer_jsonl(ruta: Path) -> list[dict]:
    return [json.loads(x) for x in ruta.read_text().splitlines() if x.strip()]


def plan() -> list[dict]:
    return json.loads((RAIZ / "plan/plan.json").read_text())["nodos"]


def estados() -> dict[str, dict]:
    """nodo -> última línea del registro (manda la última)."""
    est: dict[str, dict] = {}
    for x in leer_jsonl(RAIZ / "registro/nodos.jsonl"):
        est[x["nodo"]] = x
    return est


def veredictos() -> dict[str, dict]:
    return {v["eureka"]: v for v in leer_jsonl(RAIZ / "registro/veredictos.jsonl")}


def corrida(nombre: str) -> dict:
    return json.loads((RAIZ / "registro/corridas" / f"{nombre}.json").read_text())


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True, text=True, check=True).stdout.strip()


def guardar(fig, nombre: str) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "svg", "png"):
        fig.savefig(SALIDA / f"{nombre}.{ext}", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print("fig", nombre)


def caja(ax, x, y, w, h, texto, color, *, sub=None, tam=7.5, borde=None, estilo="round,pad=0.02,rounding_size=0.8",
         negrita=True, ls="-", lw=0.9, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=estilo, fc=aclara(color, 0.78), ec=borde or color, lw=lw, ls=ls, zorder=z))
    if sub:
        ax.text(x + w / 2, y + h * 0.74, texto, ha="center", va="center", fontsize=tam, weight="bold" if negrita else None, color=TINTA, zorder=z + 1)
        ax.text(x + w / 2, y + h * 0.33, sub, ha="center", va="center", fontsize=tam - 1.6, color="#333333", zorder=z + 1, linespacing=1.25)
    else:
        ax.text(x + w / 2, y + h / 2, texto, ha="center", va="center", fontsize=tam, weight="bold" if negrita else None, color=TINTA, zorder=z + 1)


def flecha(ax, p, q, *, color=TINTA, lw=1.0, ls="-", rad=0.0, estilo="-|>", ms=7, z=1, alpha=1.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=estilo, mutation_scale=ms, color=color, lw=lw, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}", zorder=z, alpha=alpha, shrinkA=0, shrinkB=0))


# ── (a) pipeline ──────────────────────────────────────────────────────────────────────────────
def fig_pipeline() -> None:
    fig, ax = plt.subplots(figsize=(6.5, 3.3))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 50)
    ax.axis("off")
    # Datos (mismos colores que la figura de capas): integración naranja, lógica azul.
    etapas = [
        ("Fuente", "FuenteDeBits\nprng · aer · ibm", NARANJA, "adaptador"),
        ("Mitigador", "twirling propio\n(opcional)", NARANJA, "adaptador"),
        ("Peres", "von Neumann\niterado, $d=8$", AZUL, "dominio"),
        ("Toeplitz", "hash universal\nLHL, ε = 2$^{-64}$", AZUL, "dominio"),
        ("Validador", "SP 800-22\nscipy · nistrng", NARANJA, "adaptador"),
        ("Clave", "bits de clave*", AZUL, "dominio"),
        ("Cifrador", "AES-256-GCM\nnonce de 96 bits", NARANJA, "adaptador"),
    ]
    w, g, y0, h = 11.6, 2.9, 24, 12
    xs = [1 + i * (w + g) for i in range(len(etapas))]
    for (nombre, sub, col, _), x in zip(etapas, xs):
        caja(ax, x, y0, w, h, nombre, col, sub=sub, tam=7.2)
    for i in range(len(etapas) - 1):
        flecha(ax, (xs[i] + w + 0.1, y0 + h / 2), (xs[i + 1] - 0.1, y0 + h / 2))
    # Puntos de medida M1, M3, M4, M5 (cruda, mitigada, clave)
    for (idx, rot) in ((0, "muestra cruda"), (1, "muestra mitigada"), (5, "clave")):
        xc = xs[idx] + w / 2
        ax.plot([xc, xc], [y0 - 0.2, y0 - 4.6], color=VERDE, lw=0.9)
        ax.add_patch(plt.Circle((xc, y0 - 5.6), 1.15, fc=VERDE, ec="white", lw=0.8, zorder=3))
        ax.text(xc, y0 - 5.6, "M", ha="center", va="center", fontsize=5.8, color="white", weight="bold", zorder=4)
        ax.text(xc, y0 - 8.3, rot, ha="center", va="top", fontsize=6.4, color="#222222")
        ax.text(xc, y0 - 10.7, "M1 M3 M4 M5" if idx != 5 else "M1–M5", ha="center", va="top", fontsize=6.2, color="#444444")
    # Estimador de entropía: de la muestra de entrada del extractor a la longitud de Toeplitz
    xe = xs[2] + w / 2
    caja(ax, xs[2] - 1.2, 3.3, 2 * w + g + 2.4 - 6.5, 7.2, "EstimadorDeEntropia", PURPURA,
         sub="MCV (dominio) · SP 800-90B (adaptador)", tam=6.9, estilo="round,pad=0.02,rounding_size=0.6")
    flecha(ax, (xs[2] + w + 0.5, 10.6), (xs[3] + w * 0.5, y0 - 0.2), color=PURPURA, rad=-0.15, lw=1.0)
    ax.text(xs[3] + w + 1.0, y0 - 6.8, "$h_{\\min}$ de entrada\n$m=\\lfloor n\\,h_{\\min}-128\\rfloor$", fontsize=6.4, ha="left", va="center", color=PURPURA)
    flecha(ax, (xs[1] + w * 0.5, y0 - 12.7), (xs[2] - 1.0, 8.0), color=PURPURA, rad=0.25, lw=0.8, estilo="-")
    # ZNE / PEC: otro observable
    ax.text(xs[1] + w / 2, y0 + h + 1.8, "ZNE · PEC actúan sobre ⟨Z⟩,\nno sobre los bits (rama aparte)", fontsize=6.2, ha="center", va="bottom", color=BERMELLON)
    ax.plot([xs[1] + w / 2, xs[1] + w / 2], [y0 + h + 0.2, y0 + h + 1.7], color=BERMELLON, lw=0.8, ls=":")
    # Leyenda de colores
    for k, (col, txt) in enumerate(((NARANJA, "integración (adaptador, un SDK por puerto)"), (AZUL, "lógica (dominio puro)"), (PURPURA, "estimador (dominio + adaptador)"), (VERDE, "punto de medida M1–M5"))):
        ax.add_patch(Rectangle((1 + 24 * (k % 2) * 1.0, 43.3 - 0 * k) if False else (1 + (k % 2) * 36, 47.0 - (k // 2) * 2.6), 1.7, 1.6, fc=aclara(col, 0.45), ec=col, lw=0.7))
        ax.text(3.4 + (k % 2) * 36, 47.8 - (k // 2) * 2.6, txt, fontsize=6.2, va="center")
    ax.text(99, 1.2, "* «certificada» = supera esta batería; no certifica origen cuántico.", ha="right", fontsize=6.2, color="#444444", style="italic")
    guardar(fig, "pipeline")


# ── (b) arquitectura en capas ─────────────────────────────────────────────────────────────────
def fig_capas() -> None:
    fig, ax = plt.subplots(figsize=(6.5, 4.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 68)
    ax.axis("off")
    GRIS_B = "#6E6E6E"
    cap = [  # (nombre, subtítulo, color, x, ancho)
        ("entrada", "CLI · códigos de salida", GRIS_B, 6, 52),
        ("api", "fachada pública (firmas congeladas)", GRIS_B, 6, 52),
        ("composicion", "raíz de composición: único sitio que elige adaptadores", NARANJA, 6, 52),
        ("adaptadores", "un adaptador por puerto; SDK confinado", NARANJA, 6, 33),
        ("presentacion", "formatea", GRIS_B, 41, 17),
        ("aplicacion", "casos de uso · orquestador", AZUL, 6, 52),
        ("puertos", "Protocol (diez)", AZUL, 6, 52),
        ("datos", "esquemas versionados · almacén append-only", VERDE, 6, 52),
        ("dominio", "puro: sin E/S, reloj, azar global ni SDK", AZUL, 6, 52),
    ]
    h, sep = 5.6, 1.9
    ys: dict[str, float] = {}
    y = 61.5
    for nom, sub, col, x, wd in cap:
        if nom == "presentacion":
            ys[nom] = ys["adaptadores"]
        else:
            ys[nom] = y
            y -= h + sep
        caja(ax, x, ys[nom], wd, h, nom, col, sub=sub, tam=7.4, estilo="round,pad=0.02,rounding_size=0.6")
    orden = ["entrada", "api", "composicion", "adaptadores", "aplicacion", "puertos", "datos", "dominio"]
    for a_, b_ in zip(orden, orden[1:]):
        xa = 32 if a_ == "composicion" else 30
        flecha(ax, (xa, ys[a_] - 0.1), (xa, ys[b_] + h + 0.1), lw=1.1)
    flecha(ax, (50, ys["composicion"] - 0.1), (50, ys["presentacion"] + h + 0.1), lw=1.1)
    flecha(ax, (50, ys["presentacion"] - 0.1), (50, ys["aplicacion"] + h + 0.1), lw=1.1)
    ax.text(4.6, 33, "C1: cada capa sólo importa las de abajo", fontsize=6.5, rotation=90, va="center", ha="center", color=TINTA)
    ax.text(39.5, ys["adaptadores"] + h / 2, "×", fontsize=11, color=BERMELLON, ha="center", va="center", weight="bold")
    # transversal
    xt, wt = 72, 26
    ax.add_patch(FancyBboxPatch((xt, 15), wt, 44, boxstyle="round,pad=0.02,rounding_size=0.8", fc=aclara(PURPURA, 0.78), ec=PURPURA, lw=0.9))
    ax.text(xt + wt / 2, 55.2, "transversal", ha="center", va="center", fontsize=7.6, weight="bold")
    for k, t in enumerate(("configuración", "errores", "observabilidad", "reproducibilidad", "seguridad", "concurrencia", "empaquetado")):
        ax.text(xt + wt / 2, 49.0 - k * 4.7, t, ha="center", va="center", fontsize=6.4, color="#222222")
    # puede importar transversal: entrada … adaptadores (llaves a la derecha de la pila)
    y_top, y_bot = ys["entrada"] + h, ys["adaptadores"]
    ax.plot([60.5, 61.5, 61.5, 60.5], [y_top, y_top, y_bot, y_bot], color=PURPURA, lw=1.0)
    flecha(ax, (61.5, (y_top + y_bot) / 2), (xt - 0.3, (y_top + y_bot) / 2), color=PURPURA, lw=1.1)
    ax.text(66.8, (y_top + y_bot) / 2 + 1.0, "usan", fontsize=6.4, color=PURPURA, ha="center", va="bottom")
    # no pueden: núcleo
    y_top2, y_bot2 = ys["aplicacion"] + h, ys["dominio"]
    ax.plot([60.5, 61.5, 61.5, 60.5], [y_top2, y_top2, y_bot2, y_bot2], color=BERMELLON, lw=1.0)
    ym = (y_top2 + y_bot2) / 2 + 3.0
    flecha(ax, (61.5, ym), (xt - 0.3, 22), color=BERMELLON, lw=1.1, ls=(0, (3, 2)))
    ax.text(66.8, ym - 3.6, "×", fontsize=13, color=BERMELLON, ha="center", va="center", weight="bold")
    ax.text(66.8, ym - 7.4, "C3, C6", fontsize=6.2, color=BERMELLON, ha="center", va="top")
    # texto de contratos
    ax.text(72, 12.3, "C2  los 14 adaptadores no se importan entre sí\nC4  dominio puro   C5  SDK sólo en adaptadores\nC6  transversal es hoja (sólo toca dominio.errores)",
            fontsize=6.0, ha="left", va="top", color="#222222", linespacing=1.35)
    leyenda = [(NARANJA, "Integración"), (AZUL, "Lógica"), (VERDE, "Datos"), (PURPURA, "Transversales"), (GRIS_B, "Bordes (no son capa)")]
    xl = 6
    for col, txt in leyenda:
        ax.add_patch(Rectangle((xl, 1.2), 2.0, 1.7, fc=aclara(col, 0.55), ec=col, lw=0.7))
        ax.text(xl + 2.6, 2.05, txt, fontsize=6.4, va="center")
        xl += 4.2 + 1.3 * len(txt) * 0.62 + 5.2
    guardar(fig, "capas")


# ── (c) DAG del plan por fases, coloreado por estado ───────────────────────────────────────────
def fig_dag() -> None:
    nodos = plan()
    est = estados()
    por_id = {n["id"]: n for n in nodos}
    estado = {i: est.get(i, {}).get("estado", "pendiente") for i in por_id}
    cerrado = {"hecho", "juzgado"}
    depth: dict[str, int] = {}

    def prof(i: str) -> int:
        if i not in depth:
            d = por_id[i]["depende_de"]
            depth[i] = 0 if not d else 1 + max(prof(j) for j in d)
        return depth[i]

    for i in por_id:
        prof(i)
    carriles = [("F0", "F0 Fundación"), ("F1", "F1 Dominio"), ("F2", "F2 Puertos y aplicación"), ("F3", "F3 Fuente y ruido"),
                ("F4", "F4 Mitigación"), ("F5", "F5 Validación"), ("F6", "F6 Cifrado"), ("E", "E Eurekas"),
                ("F7", "F7 Difusión"), ("R", "R Revisión y release")]
    lane_rows: dict[str, int] = {}
    sub: dict[str, int] = {}
    for fase, _ in carriles:
        ocupado: dict[int, int] = defaultdict(int)
        ids = sorted((i for i in por_id if por_id[i]["fase"] == fase), key=lambda i: (depth[i], i))
        for i in ids:
            sub[i] = ocupado[depth[i]]
            ocupado[depth[i]] += 1
        lane_rows[fase] = max(ocupado.values())
    dmax = max(depth.values())
    xstep, bw, bh, rstep = 1.0, 0.78, 0.62, 0.74
    y_lane: dict[str, float] = {}
    y = 0.0
    for fase, _ in carriles:
        y_lane[fase] = y
        y += lane_rows[fase] * rstep + 0.28
    ytot = y
    pos = {i: (depth[i] * xstep, ytot - (y_lane[por_id[i]["fase"]] + sub[i] * rstep) - rstep) for i in por_id}
    fig, ax = plt.subplots(figsize=(6.9, 6.0))
    ax.set_xlim(-2.9, dmax * xstep + 0.9)
    ax.set_ylim(-1.8, ytot + 0.1)
    ax.axis("off")
    for k, (fase, nom) in enumerate(carriles):
        top = ytot - y_lane[fase]
        hh = lane_rows[fase] * rstep + 0.14
        ax.add_patch(Rectangle((-0.5, top - hh - 0.07), dmax * xstep + 1.3, hh, fc="#F4F4F4" if k % 2 == 0 else "#FBFBFB", ec="none", zorder=0))
        ax.text(-0.6, top - hh / 2 - 0.07, nom, ha="right", va="center", fontsize=6.6, color="#333333", weight="bold")
    # aristas
    for n in nodos:
        for d in n["depende_de"]:
            (x0, y0), (x1, y1) = pos[d], pos[n["id"]]
            ax.add_patch(FancyArrowPatch((x0 + bw / 2 + 0.02, y0 + bh / 2), (x1 - bw / 2 - 0.02, y1 + bh / 2), arrowstyle="-|>", mutation_scale=3.2,
                                         lw=0.35, color="#7A7A7A", alpha=0.55, connectionstyle="arc3,rad=0.05", zorder=1, shrinkA=0, shrinkB=0))
    listo = {i for i in por_id if estado[i] not in cerrado and all(estado[d] in cerrado for d in por_id[i]["depende_de"])}
    color = {"hecho": VERDE, "juzgado": AZUL}
    for i, (x, yy) in pos.items():
        e = estado[i]
        t = por_id[i]["tipo"]
        if e in color:
            fc, tc = color[e], "white"
        elif i in listo:
            fc, tc = NARANJA, "black"
        else:
            fc, tc = "white", "#333333"
        ls = "-"
        lw = 0.6
        ec = "#222222"
        if t == "eureka":
            lw = 1.9
        elif t == "preinscripcion":
            ls = (0, (2.2, 1.2))
            lw = 1.1
        elif t in ("corrida", "medicion"):
            ls = (0, (1, 1))
            lw = 1.2
        ax.add_patch(FancyBboxPatch((x - bw / 2, yy), bw, bh, boxstyle="round,pad=0.0,rounding_size=0.1", fc=fc, ec=ec, lw=lw, ls=ls, zorder=3))
        ax.text(x, yy + bh / 2, i.replace("REL-0.1.0", "REL"), ha="center", va="center", fontsize=4.9, color=tc, zorder=4, weight="bold" if t == "eureka" else None)
    # leyenda
    n_hecho = sum(1 for i in por_id if estado[i] == "hecho")
    n_juz = sum(1 for i in por_id if estado[i] == "juzgado")
    n_listo = len(listo)
    n_pend = len(por_id) - n_hecho - n_juz - n_listo
    items = [(VERDE, f"hecho ({n_hecho})"), (AZUL, f"juzgado ({n_juz})"), (NARANJA, f"listo, no hecho ({n_listo})"), ("white", f"pendiente, bloqueado ({n_pend})")]
    xl = -2.8
    for fc, txt in items:
        ax.add_patch(Rectangle((xl, -0.62), 0.5, 0.34, fc=fc, ec="#222222", lw=0.6))
        ax.text(xl + 0.62, -0.45, txt, fontsize=6.3, va="center")
        xl += 0.62 + 0.150 * len(txt) + 0.5
    xl = -2.8
    for lw, ls, txt in ((1.9, "-", "borde grueso: eureka"), (1.1, (0, (2.2, 1.2)), "discontinuo: preinscripción"), (1.2, (0, (1, 1)), "punteado: corrida / medición")):
        ax.add_patch(Rectangle((xl, -1.1), 0.5, 0.34, fc="white", ec="#222222", lw=lw, ls=ls))
        ax.text(xl + 0.62, -0.93, txt, fontsize=6.3, va="center")
        xl += 0.62 + 0.150 * len(txt) + 0.5
    ax.text(dmax * xstep + 0.85, -1.55, f"Estado: registro/nodos.jsonl · plan: {len(por_id)} nodos · eje x: profundidad en el DAG", fontsize=5.8, ha="right", color="#555555", va="center")
    guardar(fig, "dag")


# ── (d) línea de tiempo preinscripción → corrida → veredicto ──────────────────────────────────
def fig_cronologia() -> None:
    ver = veredictos()
    hitos = [  # (carril, etiqueta, sha, tipo, arriba?)
        ("E1", "P.E1", "dae22a6", "pre", True), ("E1", "enmienda 1\n(M4 informativa)", "1a06602", "enm", False),
        ("E1", "ejecutor", "ce8ba23", "cod", True), ("E1", "enmienda 2\n(piso de P1)", "37b89ca", "enm", False),
        ("E1", "juez P1", "447c907", "cod", True), ("E1", "C.E1 + veredicto", "89cdaba", "run", True),
        ("E2", "P.E2", "43e2649", "pre", True), ("E2", "ejecutor", "26e5b41", "cod", False), ("E2", "C.E2 + veredicto", "f22ffd3", "run", True),
        ("E3", "P.E3", "d0f062a", "pre", True), ("E3", "enmienda\n(guard)", "09da88c", "enm", False),
        ("E3", "enmienda\n(M1–M5 inf.)", "5a72939", "enm", True),
        ("E3", "carga\n< 2,0", "15bd897", "enm", False), ("E3", "clave\nrechazada", "8cc0ec1", "enm", True),
        ("E3", "reposo", "41cd058", "enm", False), ("E3", "C.E3 + veredicto", "fdb4386", "run", True),
        ("P.E0", "P.E0", "f8e21d0", "pre", True),
    ]

    def fecha_minutos(sha: str) -> tuple[str, int]:
        d, h, m = git("show", "-s", "--format=%cd", "--date=format:%d %H %M", sha).split()
        return d, int(h) * 60 + int(m)

    def minutos(sha: str) -> float:
        return fecha_minutos(sha)[1]

    t = {h[2]: minutos(h[2]) for h in hitos}
    # coherencia con el registro: la preinscripción de cada veredicto precede a su corrida (git lo dice)
    for e, pre in (("E1", "37b89ca"), ("E2", "43e2649"), ("E3", "41cd058")):
        assert ver[e]["preinscripcion_sha"].startswith(pre), (e, pre)
        subprocess.run(["git", "-C", str(RAIZ), "merge-base", "--is-ancestor", ver[e]["preinscripcion_sha"], ver[e]["commit"]], check=True)
    carriles = ["P.E0", "E1", "E2", "E3"]
    yc = {c: 3 - i for i, c in enumerate(carriles)}
    estilos = {"pre": ("D", AZUL, 38), "enm": ("^", NARANJA, 46), "cod": ("s", GRIS, 24), "run": ("o", VERDE, 54)}
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(6.5, 3.0), sharey=True, gridspec_kw={"width_ratios": [4.6, 1.3, 2.2], "wspace": 0.07})
    rangos = ((17 * 60 + 56, 19 * 60 + 32), (21 * 60 + 28, 21 * 60 + 53), (14 * 60 + 12, 14 * 60 + 52))
    for ax, (lo, hi) in zip((a1, a2, a3), rangos):
        ax.set_xlim(lo, hi)
        ax.set_ylim(-0.7, 3.8)
        ax.spines["left"].set_visible(False)
        for c in carriles:
            ax.axhline(yc[c], color="#DDDDDD", lw=0.7, zorder=0)
        ticks = [m for m in range((lo // 30) * 30, hi + 1, 30) if lo <= m <= hi and m != 19 * 60 + 30]
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{m // 60:02d}:{m % 60:02d}" for m in ticks])
        ax.tick_params(axis="y", length=0)
    a1.spines["right"].set_visible(False)
    a2.spines["right"].set_visible(False)
    a3.spines["right"].set_visible(False)
    a1.set_yticks([yc[c] for c in carriles])
    a1.set_yticklabels(["P.E0", "E1", "E2", "E3"], fontweight="bold")
    alto = defaultdict(int)
    for car, et, sha, tipo, arriba in hitos:
        x = t[sha]
        dia = fecha_minutos(sha)[0]
        ax = a3 if dia == "08" else (a1 if x < 20 * 60 else a2)
        mk, col, sz = estilos[tipo]
        y = yc[car]
        ax.scatter([x], [y], marker=mk, s=sz, color=col, ec="black", lw=0.5, zorder=3)
        ax.annotate(et, (x, y), xytext=(0, 8 if arriba else -8), textcoords="offset points", ha="center", va="bottom" if arriba else "top", fontsize=5.8, color="#222222")
    # corte del eje
    d = 0.012
    kw = dict(transform=a1.transAxes, color="k", clip_on=False, lw=0.7)
    a1.plot((1 - d, 1 + d), (-0.03, 0.03), **kw)
    for ax_ in (a2, a3):
        kw["transform"] = ax_.transAxes
        ax_.plot((-d * 3.4, d * 3.4), (-0.03, 0.03), **kw)
    a2.plot((1 - d * 3.4, 1 + d * 3.4), (-0.03, 0.03), transform=a2.transAxes, color="k", clip_on=False, lw=0.7)
    a1.set_xlabel("hora del commit, 2026-10-07 (eje cortado entre 19:30 y 21:30)", loc="left")
    a3.set_xlabel("2026-10-08", loc="left")
    # leyenda
    from matplotlib.lines import Line2D
    leyenda = [Line2D([], [], marker="D", ls="", color=AZUL, mec="k", mew=0.5, label="preinscripción"),
               Line2D([], [], marker="^", ls="", color=NARANJA, mec="k", mew=0.5, label="enmienda fechada"),
               Line2D([], [], marker="s", ls="", color=GRIS, mec="k", mew=0.5, label="código del ejecutor/juez"),
               Line2D([], [], marker="o", ls="", color=VERDE, mec="k", mew=0.5, label="corrida y veredicto"),
               ]
    a1.legend(handles=leyenda, loc="upper center", bbox_to_anchor=(0.62, 1.2), ncol=4, frameon=False, handletextpad=0.3, columnspacing=1.0, fontsize=6.2)
    guardar(fig, "cronologia")


# ── (e) E2: sesgo crudo y residual con IC95 ───────────────────────────────────────────────────
def fig_e2() -> None:
    celdas = defaultdict(dict)  # (nivel, semilla) -> tecnica -> artefacto
    for f in sorted(glob.glob(str(RAIZ / "registro/corridas/C.E2_*_e2_*.json"))):
        d = json.load(open(f))
        celdas[(d["nivel"], d["semilla"])][d["tecnica"]] = d
    grupos = [("bajo", "bajo\n(0,01; 0,03)"), ("medio", "medio\n(0,02; 0,08)"), ("alto", "alto\n(0,05; 0,15)"),
              ("realista", "realista\n(backend falso)"), ("sin_ruido", "C2: sin\nruido"), ("simetrico", "C3: simétrico\n(0,05; 0,05)")]
    semillas = [20261007, 20261008, 20261009]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(6.5, 3.15), gridspec_kw={"width_ratios": [3.3, 1], "wspace": 0.28})
    for gi, (nivel, _) in enumerate(grupos):
        for si, s in enumerate(semillas):
            tw = celdas[(nivel, s)]["twirling_propio"]
            x = gi + (si - 1) * 0.22
            c0 = tw["sesgo_crudo"]
            ax.scatter([x - 0.045], [c0], marker="s", s=17, facecolors="white", edgecolors=BERMELLON, lw=0.9, zorder=3)
            lo, hi = tw["intervalo_residual"]
            r = tw["sesgo_residual"]
            ax.errorbar([x + 0.045], [r], yerr=[[max(r - lo, 0)], [max(hi - r, 0)]], fmt="o", ms=3.6, color=AZUL, ecolor=AZUL, elinewidth=0.9, capsize=1.6, zorder=3)
    ax.axhline(0.01, color=BERMELLON, lw=0.8, ls="--")
    ax.text(5.45, 0.0108, "M1 = 0,01", color=BERMELLON, fontsize=6.3, ha="right", va="bottom")
    ax.axhline(0.003, color=NARANJA, lw=0.8, ls=":")
    ax.text(5.45, 0.00322, "K3 = 0,003", color="#9A6A00", fontsize=6.3, ha="right", va="bottom")
    ax.axhline(0.0006, color=GRIS, lw=0.7, ls="-.")
    ax.text(-0.55, 0.00055, "piso analítico ≈ 0,0006", color="#555555", fontsize=6.3, ha="left", va="top")
    ax.set_yscale("log")
    ax.set_ylim(2.2e-4, 0.12)
    ax.set_xlim(-0.6, 5.5)
    ax.set_xticks(range(len(grupos)))
    ax.set_xticklabels([g[1] for g in grupos], fontsize=6.2)
    ax.set_ylabel("sesgo medio por qubit, $|\\hat p-\\frac{1}{2}|$ (escala log.)")
    ax.set_title("(a) Twirling propio: crudo vs. residual (IC95, 3 semillas por grupo)", loc="left", fontsize=7.4)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="s", ls="", mfc="white", mec=BERMELLON, label="crudo (sin mitigar)"),
                       Line2D([], [], marker="o", ls="", color=AZUL, label="residual con twirling ± IC95")],
              loc="upper right", bbox_to_anchor=(1.0, 1.0), frameon=False, ncol=1, fontsize=6.3)
    # panel B: ZNE y PEC
    rel = {"zne": [], "pec": []}
    for s in semillas:
        for tec in rel:
            d = celdas[("medio", s)][tec]
            rel[tec].append(100 * (d["sesgo_residual"] - d["sesgo_crudo"]) / d["sesgo_crudo"])
    xs = np.arange(2)
    for ti, tec in enumerate(("zne", "pec")):
        for si, v in enumerate(rel[tec]):
            bx.bar(ti + (si - 1) * 0.26, v, width=0.22, color=[CIELO, AZUL, "#003F66"][si], ec="black", lw=0.4)
    bx.axhspan(-10, 10, color=aclara(NARANJA, 0.75), zorder=0)
    bx.axhline(0, color="black", lw=0.6)
    bx.text(1.55, 9.3, "«sin efecto»\n(<10 %, C4)", fontsize=6.0, ha="right", va="top", color="#7A5200")
    bx.set_xticks(xs)
    bx.set_xticklabels(["ZNE", "PEC"])
    bx.set_xlim(-0.6, 1.6)
    bx.set_ylim(-14, 14)
    bx.set_ylabel("cambio relativo del sesgo (%)")
    bx.set_title("(b) Nivel medio", loc="left", fontsize=7.4)
    guardar(fig, "e2_sesgo")


# ── (f) E1: p-valores y estado por métrica y semilla ──────────────────────────────────────────
def fig_e1() -> None:
    inf = {}
    for f in sorted(glob.glob(str(RAIZ / "registro/corridas/C.E1_*_informe_*.json"))):
        d = json.load(open(f))
        inf[(d["corrida"], d["semilla"])] = d
    semillas = [20261007, 20261008, 20261009]
    # (corrida, punto, etiqueta, decide)
    cols = [("C.E1a", "cruda", "E1a\ncruda", True), ("C.E1a", "clave", "E1a\nclave", True),
            ("C.E1b", "cruda", "E1b\ncruda", True), ("C.E1b", "clave", "E1b\nclave", False),
            ("C.E1c", "mitigada", "E1c\nmitigada", False), ("C.E1c", "clave", "E1c\nclave", True)]
    metricas = [("M1_sesgo", "M1: sesgo $|\\hat p-\\frac{1}{2}|$", 0.01), ("M3_nist_monobit", "M3: monobit (valor $p$)", 0.01),
                ("M4_nist_runs", "M4: rachas (valor $p$)", 0.01), ("M5_chi_cuadrado", "M5: frecuencia por bloques (valor $p$)", 0.01)]
    piso = 1e-16
    fig, axs = plt.subplots(2, 2, figsize=(6.5, 4.6), sharex=True)
    for ax, (clave, titulo, umbral) in zip(axs.flat, metricas):
        for ci, (cor, punto, _, decide) in enumerate(cols):
            for si, s in enumerate(semillas):
                vals = {m[0]: m for m in inf[(cor, s)]["etapas"][punto]}
                v = vals[clave][1]
                ok = vals[clave][3]
                x = ci + (si - 1) * 0.22
                vv = max(v, piso)
                col = VERDE if ok else BERMELLON
                mk = "o" if ok else "X"
                if decide:
                    ax.scatter([x], [vv], marker=mk, s=26, color=col, ec="black", lw=0.4, zorder=3)
                else:
                    ax.scatter([x], [vv], marker=mk, s=26, facecolors="white", edgecolors=col, lw=1.1, zorder=3)
                if v < piso:
                    ax.annotate("", (x, piso * 0.75), (x, piso * 3), arrowprops=dict(arrowstyle="-|>", color=col, lw=0.6, mutation_scale=5))
        ax.axhline(umbral, color=NEGRO, lw=0.8, ls="--")
        ax.text(5.55, umbral * (1.25 if clave == "M1_sesgo" else 1.25), "umbral 0,01", fontsize=6.0, ha="right", va="bottom")
        ax.set_yscale("log")
        ax.set_ylim(5e-17, 3 if clave != "M1_sesgo" else 0.3)
        if clave == "M1_sesgo":
            ax.set_ylim(5e-6, 0.3)
        ax.set_xlim(-0.55, 5.6)
        ax.set_title(titulo, loc="left", fontsize=7.3)
        ax.axvspan(3.5 - 1, 4.5, color="#F2F2F2", zorder=0) if False else None
        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels([c[2] for c in cols], fontsize=6.2)
    axs[0, 0].set_ylabel("valor (log.)")
    axs[1, 0].set_ylabel("valor $p$ (log.; flecha: ≤ $10^{-16}$ o $p$=0)")
    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([], [], marker="o", ls="", color=VERDE, mec="black", mew=0.4, label="pasa · decide"),
                        Line2D([], [], marker="X", ls="", color=BERMELLON, mec="black", mew=0.4, label="falla · decide"),
                        Line2D([], [], marker="o", ls="", mfc="white", mec=VERDE, mew=1.1, label="pasa · informativa"),
                        Line2D([], [], marker="X", ls="", mfc="white", mec=BERMELLON, mew=1.1, label="falla · informativa")],
               loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.03), fontsize=6.5)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    guardar(fig, "e1_metricas")


# ── (g) E1d: 90B frente a MCV para cada fuente ────────────────────────────────────────────────
def fig_e1d() -> None:
    fuentes = defaultdict(list)
    for f in sorted(glob.glob(str(RAIZ / "registro/corridas/C.E1_*_fuente_*.json"))):
        d = json.load(open(f))
        fuentes[d["fuente"]].append(d)
    nombres = [("sesgada", "sesgada\n$p(1)=0{,}7$", 0.5146), ("periodica", "periódica\n00001111", 0.0),
               ("markov", "Markov\npermanencia 0,8", 0.3219), ("ideal", "ideal\n(PRNG)", 1.0)]
    # entropía real (analítica): H(0,7)=0,8813 bit/bit; min-entropía = -log2(0,7)=0,5146; Markov: -log2(0,8)=0,3219
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.axhspan(0, 0.5, color=aclara(BERMELLON, 0.86), zorder=0)
    ax.axhspan(0.8, 1.02, color=aclara(VERDE, 0.86), zorder=0)
    ax.axhspan(0.5, 0.8, color="#F4F4F4", zorder=0, hatch="////", ec="#DDDDDD", lw=0)
    ax.text(-0.46, 0.10, "techo de rechazo: 90B < 0,5", fontsize=6.2, ha="left", va="center", color="#7A2F00")
    ax.text(-0.46, 0.65, "hueco declarado (0,5 – 0,8)", fontsize=6.2, ha="left", va="center", color="#444444")
    ax.text(-0.46, 0.83, "piso de aceptación: 90B ≥ 0,8", fontsize=6.2, ha="left", va="center", color="#005F46")
    ax.axhline(0.9, color=NEGRO, lw=0.7, ls=":")
    ax.text(-0.46, 0.912, "0,9", fontsize=6.2, va="bottom", ha="left", color="#222222")
    for i, (clave, etiqueta, real) in enumerate(nombres):
        for k, d in enumerate(sorted(fuentes[clave], key=lambda z: z["semilla"])):
            x = i + (k - 1) * 0.15
            ax.scatter([x - 0.035], [d["h_90b"]], marker="o", s=28, color=AZUL, ec="black", lw=0.4, zorder=4)
            ax.scatter([x + 0.035], [d["mcv"]], marker="D", s=24, color=NARANJA, ec="black", lw=0.4, zorder=4)
        m90 = np.mean([d["h_90b"] for d in fuentes[clave]])
        mmcv = np.mean([d["mcv"] for d in fuentes[clave]])
        ax.plot([i + 0.34, i + 0.34], [m90, mmcv], color="black", lw=0.7, zorder=3)
        ax.text(i + 0.38, (m90 + mmcv) / 2, f"Δ = {mmcv - m90:+.2f}".replace(".", ","), fontsize=6.3, va="center", ha="left")
        ax.scatter([i], [real], marker="_", s=420, color="black", lw=1.4, zorder=2)
    ax.set_xticks(range(len(nombres)))
    ax.set_xticklabels([n[1] for n in nombres])
    ax.set_xlim(-0.5, 3.8)
    ax.set_ylim(-0.03, 1.03)
    ax.set_ylabel("min-entropía estimada (bit/bit)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.1f}".replace(".", ",")))
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=AZUL, mec="black", mew=0.4, label="SP 800-90B (mínimo de 10 estimadores)"),
                       Line2D([], [], marker="D", ls="", color=NARANJA, mec="black", mew=0.4, label="MCV (cota al 99 %)"),
                       Line2D([], [], marker="_", ls="", color="black", mew=1.4, markersize=10, label="min-entropía real (analítica)")],
              loc="upper center", bbox_to_anchor=(0.44, 1.2), ncol=3, frameon=False, fontsize=6.3, columnspacing=1.0, handletextpad=0.3)
    guardar(fig, "e1d_90b_vs_mcv")


# ── (f) E3: latencia por etapas y por repetición ──────────────────────────────────────────────
def fig_e3() -> None:
    semillas = (20261007, 20261008, 20261009)
    datos = {s: json.load(open(RAIZ / f"registro/corridas/C.E3_{s}_e3_000.json")) for s in semillas}
    etapas = [("fuente", "fuente (Aer)", CIELO), ("mitigacion", "mitigación (*twirling*)", NARANJA), ("extraccion", "extracción", PURPURA),
              ("validacion", "validación", VERDE), ("cifrado", "cifrado (0,19 ms)", NEGRO)]
    fig, (a, b) = plt.subplots(1, 2, figsize=(6.5, 2.7), gridspec_kw={"width_ratios": [1, 1.25], "wspace": 0.3})
    # (a) mediana por etapa, apilada
    for i, s in enumerate(semillas):
        base = 0.0
        e = datos[s]["reporte"]["etapas_ms"]
        for clave, nombre, col in etapas:
            v = float(np.median(e[clave])) / 1000
            a.bar(i, v, bottom=base, color=col, ec="black", lw=0.4, width=0.6, label=nombre.replace("*", "") if i == 0 else None)
            base += v
        a.text(i, base + 0.08, f"{base:.2f}".replace(".", ",") + " s", ha="center", fontsize=6.5)
    a.axhline(0.5, color=BERMELLON, lw=1.0, ls="--")
    a.text(2.38, 0.5, "M7\n0,5 s", color=BERMELLON, fontsize=6.3, ha="left", va="center")
    a.set_xlim(-0.5, 2.95)
    a.set_xticks(range(3))
    a.set_xticklabels([str(s) for s in semillas], fontsize=6.3)
    a.set_ylabel("mediana de $t_{rep}$ por etapa (s)")
    a.set_ylim(0, 8.3)
    a.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}"))
    a.legend(loc="upper left", frameon=False, fontsize=5.8, handlelength=1.0, labelspacing=0.25, ncol=2, columnspacing=0.8, bbox_to_anchor=(-0.02, 1.0))
    a.set_title("(a) etapas", loc="left", fontsize=7.5)
    # (b) t_rep por repetición, escala log
    marcas = {7: "o", 8: "s", 9: "D"}
    cols = {7: AZUL, 8: NARANJA, 9: VERDE}
    for s in semillas:
        r = datos[s]["reporte"]
        t = np.array(r["t_rep_ms"]) / 1000
        rech = np.array(r["claves_rechazadas"][3:]) > 0
        k = int(str(s)[-1])
        x = np.arange(1, len(t) + 1)
        b.scatter(x[~rech], t[~rech], marker=marcas[k], s=14, color=cols[k], ec="black", lw=0.3, zorder=3, label=f"{s}")
        b.scatter(x[rech], t[rech], marker=marcas[k], s=30, facecolors="white", edgecolors=cols[k], lw=1.3, zorder=4)
        b.axhline(datos[s]["m7_p95_ms"] / 1000, color=cols[k], lw=0.7, ls=":")
    b.axhline(0.5, color=BERMELLON, lw=1.0, ls="--")
    b.text(30.5, 0.5, "M7: 0,5 s", color=BERMELLON, fontsize=6.3, ha="right", va="bottom")
    b.set_yscale("log")
    b.set_ylim(0.3, 14)
    b.set_xlim(0, 31)
    b.set_yticks([0.5, 1, 2, 5, 10])
    b.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
    b.set_xlabel("repetición medida")
    b.set_ylabel("$t_{rep}$ (s, escala logarítmica)")
    b.set_title("(b) por repetición; hueco: clave regenerada; punteado: p95", loc="left", fontsize=7.0)
    b.legend(loc="center right", frameon=False, fontsize=6.0, handletextpad=0.2, title="semilla", title_fontsize=6.0)
    guardar(fig, "e3_latencia")


def _coma(v, d=2):
    return f"{v:.{d}f}".replace(".", ",")


def fig_e3b() -> None:
    semillas = (20261007, 20261008, 20261009)
    e3 = {s: json.load(open(RAIZ / f"registro/corridas/C.E3_{s}_e3_000.json")) for s in semillas}
    e3b = {s: json.load(open(RAIZ / f"registro/corridas/C.E3b_{s}_e3b_000.json")) for s in semillas}
    cols = {20261007: AZUL, 20261008: NARANJA, 20261009: VERDE}
    fig, (a, b) = plt.subplots(1, 2, figsize=(6.5, 2.7), gridspec_kw={"width_ratios": [1, 1.25], "wspace": 0.38})
    # (a) p95 por semilla: E3 frente a E3b, escala log
    w = 0.36
    for i, s in enumerate(semillas):
        v3, vb = e3[s]["m7_p95_ms"], e3b[s]["reporte"]["latencias_ms"]
        v3b = float(e3b[s]["p95_ms"])
        a.bar(i - w / 2, v3, w, color=GRIS, ec="black", lw=0.4, label="E3: generar y cifrar" if i == 0 else None)
        a.bar(i + w / 2, v3b, w, color=CIELO, ec="black", lw=0.4, label="E3b: cifrar con reserva cebada" if i == 0 else None)
        a.text(i - w / 2, v3 * 1.25, _coma(v3 / 1000, 1) + " s", ha="center", fontsize=5.8)
        a.text(i + w / 2 + 0.02, v3b * 1.3, _coma(v3b, 2) + " ms", ha="left", fontsize=5.6, rotation=90, va="bottom")
    a.axhline(500, color=BERMELLON, lw=1.0, ls="--")
    a.text(2.62, 500, "M7\n500 ms", color=BERMELLON, fontsize=6.0, ha="left", va="center")
    a.set_yscale("log")
    a.set_ylim(0.05, 1e5)
    a.set_yticks([0.1, 1, 10, 100, 1000, 10000])
    a.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " ") if v >= 1 else _coma(v, 1)))
    a.set_xlim(-0.55, 3.2)
    a.set_xticks(range(3))
    a.set_xticklabels([str(s) for s in semillas], fontsize=6.0)
    a.set_ylabel("p95 de latencia por transacción (ms)")
    a.legend(loc="upper right", frameon=False, fontsize=5.4, handlelength=1.0, labelspacing=0.3, bbox_to_anchor=(1.0, 1.0))
    a.set_title("(a) p95, no equivalentes", loc="left", fontsize=7.5)
    # (b) distribución de las latencias de E3b
    todas = {s: np.array(e3b[s]["reporte"]["latencias_ms"]) for s in semillas}
    cat = np.concatenate(list(todas.values()))
    bins = np.logspace(np.log10(cat.min()), np.log10(cat.max()), 60)
    b.hist([todas[s] for s in semillas], bins=bins, stacked=True, color=[cols[s] for s in semillas], ec="black", lw=0.2,
           label=[str(s) for s in semillas])
    p95 = float(np.percentile(cat, 95))
    b.axvline(p95, color=TINTA, lw=1.0, ls=":")
    b.text(p95 * 1.08, 0.97, f"p95 = {_coma(p95, 2)} ms", transform=b.get_xaxis_transform(), fontsize=6.0, va="top")
    b.axvline(500, color=BERMELLON, lw=1.0, ls="--")
    b.text(450, 0.97, "M7: 500 ms", transform=b.get_xaxis_transform(), color=BERMELLON, fontsize=6.0, va="top", ha="right")
    b.set_xscale("log")
    b.set_xlim(0.04, 1000)
    b.set_xticks([0.1, 1, 10, 100, 1000])
    b.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " ") if v >= 1 else _coma(v, 1)))
    b.set_xlabel("latencia por transacción (ms, escala logarítmica); n = " + f"{len(cat):,}".replace(",", " "))
    b.set_ylabel("transacciones")
    b.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " ")))
    b.legend(loc="center right", frameon=False, fontsize=5.8, handlelength=1.0, title="semilla", title_fontsize=5.8, bbox_to_anchor=(0.80, 0.55))
    b.set_title("(b) E3b, tres semillas apiladas", loc="left", fontsize=7.5)
    guardar(fig, "e3b_latencia")


def fig_e5() -> None:
    import re
    semillas = (20261007, 20261008, 20261009)
    fuentes = ["buena", "markov", "markov_fuerte", "periodica"]
    nombres = {"buena": "buena", "markov": "Markov", "markov_fuerte": "Markov fuerte", "periodica": "periódica"}
    dims = [("mcv", "MCV", CIELO), ("min_mcv_90b", "mín(MCV, 90B)", NARANJA), ("conservador", "conservador", VERDE)]
    bits: dict = defaultdict(list)
    for f in sorted(glob.glob(str(RAIZ / "registro/corridas/C.E5_*_e5_*.json"))):
        d = json.load(open(f))
        for r in d["resultados"]:
            bits[(d["fuente"], r["dimensionado"])].append(r["bits_clave"])
    techo: dict = {}
    for x in leer_jsonl(RAIZ / "registro/veredictos.jsonl"):
        if x["eureka"] != "E5":
            continue
        for c in x["criterios"]:
            m = re.match(r"D/(\w+)/", c["id"])
            t = re.search(r"techo K1 (\d+)", c["detalle"])
            if m and t:
                techo[m.group(1)] = int(t.group(1))
    fig, ax = plt.subplots(figsize=(6.5, 2.7))
    w = 0.26
    for j, (clave, nom, col) in enumerate(dims):
        for i, fu in enumerate(fuentes):
            v = np.array(bits[(fu, clave)], dtype=float)
            assert len(v) == len(semillas), (fu, clave, len(v))
            x = i + (j - 1) * w
            ax.bar(x, v.mean(), w, color=col, ec="black", lw=0.4, label=nom if i == 0 else None)
            ax.errorbar(x, v.mean(), yerr=[[v.mean() - v.min()], [v.max() - v.mean()]], color=TINTA, lw=0.7, capsize=1.5, capthick=0.7)
            ax.text(x, v.max() * 1.12, f"{v.mean() / 1000:.0f}".replace(".", ",") + " k", ha="center", fontsize=5.0,
                    bbox=dict(fc="white", ec="none", pad=0.4), zorder=6)
    for i, fu in enumerate(fuentes):
        if fu in techo:
            ax.hlines(techo[fu], i - 0.42, i + 0.42, color=BERMELLON, lw=1.4, ls="--", zorder=5,
                      label="techo K1 teórico" if fu == "markov" else None)
    ax.set_yscale("log")
    ax.set_ylim(2e4, 3e6)
    ax.set_yticks([3e4, 1e5, 3e5, 1e6])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " ")))
    ax.set_xticks(range(len(fuentes)))
    ax.set_xticklabels([nombres[f] for f in fuentes])
    ax.set_ylabel("bits de clave (escala logarítmica)")
    ax.set_xlabel("fuente (media de tres semillas; barra: mínimo y máximo)")
    ax.legend(loc="upper right", frameon=False, fontsize=6.0, ncol=2, handlelength=1.2, columnspacing=1.0, bbox_to_anchor=(1.0, 1.04))
    guardar(fig, "e5_dimensionado")


FIGS = {"pipeline": fig_pipeline, "capas": fig_capas, "dag": fig_dag, "cronologia": fig_cronologia,
        "e2": fig_e2, "e1": fig_e1, "e1d": fig_e1d, "e3": fig_e3, "e3b": fig_e3b, "e5": fig_e5}

if __name__ == "__main__":
    _fuentes()
    pedidas = sys.argv[1:] or list(FIGS)
    for n in pedidas:
        FIGS[n]()
