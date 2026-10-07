import subprocess
import sys
import textwrap
import time

import pytest

from qrecauda.dominio.errores import CandadoOcupado
from qrecauda.transversal.concurrencia import candado


def test_candado_se_libera_y_es_reentrante_entre_usos(tmp_path):
    ruta = tmp_path / "sub" / "m.lock"
    with candado(ruta):
        pass
    with candado(ruta):
        pass


def test_otro_proceso_no_entra_mientras_se_sostiene(tmp_path):
    ruta = tmp_path / "m.lock"
    codigo = textwrap.dedent(
        f"""
        import sys
        from pathlib import Path
        from qrecauda.dominio.errores import CandadoOcupado
        from qrecauda.transversal.concurrencia import candado
        try:
            with candado(Path({str(ruta)!r}), espera_s=0.2):
                print("ENTRO")
        except CandadoOcupado:
            print("OCUPADO")
        """
    )
    with candado(ruta):
        r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=30)
        assert r.stdout.strip() == "OCUPADO", r.stderr
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=30)
    assert r.stdout.strip() == "ENTRO", r.stderr


def test_espera_acotada(tmp_path):
    ruta = tmp_path / "m.lock"
    with candado(ruta):
        t0 = time.monotonic()
        with pytest.raises(CandadoOcupado), candado(ruta, espera_s=0.3):
            pass
        assert 0.25 <= time.monotonic() - t0 < 5
