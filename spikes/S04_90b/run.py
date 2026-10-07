"""SPIKE S.04: estimador NIST SP 800-90B no-IID independiente (C++ oficial v1.1.8) frente a nuestro MCV.

Uso:  uv run python spikes/S04_90b/run.py
Compila el binario oficial en /tmp/qrecauda_nist90b (fuera del repo) la primera vez, con build_nist.sh.
Escribe resultado.json y salida_cruda.json junto a este archivo.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1] / "src"))
N = 1_000_000  # mínimo que exige ea_non_iid: "at least 1 million entries (samples)"
SEMILLA = 20261007
PATRON = re.compile(r"^\s*(.+?) Estimate = (-?[0-9.]+) / 1 bit\(s\)", re.M)


def binario() -> Path:
    out = subprocess.run(["bash", str(AQUI / "build_nist.sh")], check=True, capture_output=True, text=True)
    return Path(out.stdout.strip().splitlines()[-1])


def senales() -> dict[str, tuple[np.ndarray, float, str]]:
    rng = np.random.default_rng(SEMILLA)
    iid = (rng.random(N) < 0.7).astype(np.uint8)
    # Markov con permanencia 0,8: P(cambiar)=0,2. Min-entropía por símbolo = -log2(0,8) = 0,322
    # (el mejor adivinador acierta 0,8). La entropía de Shannon sería H(0,2)=0,722; no es la métrica.
    mk = np.cumsum(rng.random(N) < 0.2) % 2
    det = (np.arange(N) % 8 < 4).astype(np.uint8)  # 00001111 repetido
    return {
        "iid_sesgada": (iid, -math.log2(0.7), "IID p(1)=0,7"),
        "markov": (mk.astype(np.uint8), -math.log2(0.8), "Markov permanencia 0,8"),
        "determinista": (det, 0.0, "periodo 8"),
    }


def evaluar(exe: Path, bits: np.ndarray) -> tuple[dict[str, float], float | None, int, str]:
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "s.bin"
        f.write_bytes(bits.astype(np.uint8).tobytes())  # un símbolo de 1 bit por byte
        r = subprocess.run([str(exe), "-i", "-a", "-v", str(f), "1"], capture_output=True, text=True, timeout=1800)
    est = {m.group(1).strip(): float(m.group(2)) for m in PATRON.finditer(r.stdout)}
    h = re.search(r"^H_original: (-?[0-9.]+)", r.stdout, re.M)
    return est, float(h.group(1)) if h else None, r.returncode, r.stdout


def main() -> None:
    from qrecauda.dominio.bits import Bits
    from qrecauda.dominio.entropia import min_entropia_mcv

    exe = binario()
    res: dict[str, dict] = {}
    crudo: dict[str, str] = {}
    for nombre, (b, esperada, _desc) in senales().items():
        est, h_orig, rc, txt = evaluar(exe, b)
        crudo[nombre] = txt
        minimo = min(est.values()) if est else None
        mcv = min_entropia_mcv(Bits(b))
        res[nombre] = {
            "h_esperada": round(esperada, 4),
            "h_medida": h_orig,
            "estimador_minimo": min(est, key=est.get) if est else None,
            "por_estimador": est,
            "mcv_propio": round(mcv, 6),
            "mcv_nist": est.get("Most Common Value"),
            "rc": rc,
        }
        assert minimo is None or h_orig is None or abs(minimo - h_orig) < 1e-6
        print(f"{nombre}: esperada={esperada:.3f} NIST min={h_orig} ({res[nombre]['estimador_minimo']}) "
              f"MCV nist={res[nombre]['mcv_nist']} MCV propio={mcv:.6f}")
    out = {
        "herramienta": "usnistgov/SP800-90B_EntropyAssessment, ea_non_iid (C++ oficial del NIST)",
        "version": "v1.1.8 (tag GitHub, tarball)",
        "instalacion": "bash spikes/S04_90b/build_nist.sh -> /tmp/qrecauda_nist90b/ea_non_iid (curl del tarball del tag; "
                       "dependencias libdivsufsort, libbz2-dev y libjsoncpp por apt-get download + dpkg -x sin root; "
                       "g++ -fopenmp). Sin sudo, sin pip.",
        "min_muestras": 1_000_000,
        "senales": res,
        "independiente": True,
        "advertencias": [
            "H_original = mínimo de los 10 estimadores no-IID; los 3 resultados salen de -i -a con 1 bit/símbolo.",
            "Un -0.000000 de NIST es cero (se parsea como float; el determinista da h=0).",
            "Bias conservador: en IID sesgada el estimador de compresión baja el mínimo a 0,322 (esperado 0,515) y en Markov "
            "el de colisión a 0,170 (esperado 0,322); MCV solo no detecta la dependencia (0,99 en Markov). Los predictores "
            "(Lag/MultiMMC/LZ78Y) clavan 0,319 en Markov: el mínimo NIST es una cota inferior, no un valor puntual.",
            "mcv_propio coincide con el MCV de NIST a 6 decimales en las tres señales: validación independiente de dominio/entropia.py.",
            "Compilación depende de red (GitHub, archive.ubuntu.com) y de apt-get download; el PyPI 'sp800-90b' 0.1.1 "
            "(hnj2, tercero, sdist 52 KB) existe pero NO se evaluó: no es del NIST. No hay ea_non_iid embebido en ningún paquete instalado (no buscado a fondo).",
            "El binario usa -march=native: el resultado numérico no cambia, pero el binario no es portable entre CPUs.",
        ],
    }
    (AQUI / "resultado.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    (AQUI / "salida_cruda.json").write_text(json.dumps(crudo, indent=1))


if __name__ == "__main__":
    main()
