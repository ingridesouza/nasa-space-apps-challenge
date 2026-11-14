"""F03/F04 do subprojeto servidas pela API principal (mesma origem).

Rodar: make test   (ou: cd api && python test_f03.py)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from main import F03_ROTAS, app


def test_rotas_f03_antes_do_mount_do_front():
    caminhos = [r.path for r in app.routes]
    assert F03_ROTAS <= set(caminhos), F03_ROTAS - set(caminhos)
    # o mount de "/" (web/) engole tudo que vier depois dele
    assert caminhos[-1] == "" and caminhos.count("") == 1, caminhos[-3:]


def test_ficha_nunca_aponta_pra_fora():
    from api.main import science_card  # pacote "api" do subprojeto, já no sys.path via main
    ficha = science_card(lat=-4.8036, lon=137.3805, radius=150)
    assert ficha["mastcam"] is None or ficha["mastcam"]["img"].startswith("/bundle/")


if __name__ == "__main__":
    for nome, t in list(globals().items()):
        if nome.startswith("test_"):
            t()
            print(f"ok  {nome}")
