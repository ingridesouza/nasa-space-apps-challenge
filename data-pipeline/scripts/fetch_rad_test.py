"""Script de teste do adaptador RAD (radiação, PDS-PPI/UCLA).

Uso:
    python scripts/fetch_rad_test.py [sol]

Sem argumento, usa o sol 4650 (mesmo exemplo do REMS, para comparar).
Baixa o arquivo real do sol, extrai a dose do detector E por
observação (unidade: µGy/h) e imprime as primeiras leituras, além da
dose diária estimada (média das leituras × 24h) para comparar com a
faixa conhecida de Marte (~200-250 µGy/dia).
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.pds_rad import PDSRadAdapter


def main() -> None:
    sol = int(sys.argv[1]) if len(sys.argv) > 1 else 4650

    adapter = PDSRadAdapter()
    print(f"[1/2] Buscando arquivo RAD do sol {sol}...")
    resultado = adapter.fetch_sol(sol)
    print(f"      arquivo: {resultado['product_filename']}")
    print(f"      {len(resultado['leituras'])} leituras com dosimetria completa no sol")

    print("[2/2] Primeiras leituras:")
    doses = []
    for leitura in resultado["leituras"][:5]:
        dose = leitura["dose_e_ugy_por_hora"]
        print(
            f"      obs {leitura['indice']:>3} | {leitura['lmst']} (LMST) | "
            f"duração {leitura['duracao_s']:.0f}s | dose_E = {dose:.4f} µGy/h"
        )

    for leitura in resultado["leituras"]:
        if leitura["dose_e_ugy_por_hora"] is not None:
            doses.append(leitura["dose_e_ugy_por_hora"])

    if doses:
        media = sum(doses) / len(doses)
        print(f"\n      dose média do sol: {media:.4f} µGy/h -> ~{media * 24:.1f} µGy/dia estimado")


if __name__ == "__main__":
    main()
