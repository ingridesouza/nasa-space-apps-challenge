"""Script de teste do adaptador REMS (clima, PDS Atmospheres Node).

Uso:
    python scripts/fetch_rems_test.py [sol]

Sem argumento, usa o sol 4650 (mesmo exemplo citado no doc da feature
01, seção 3.2: "140 m · olhando para NE · sol 4650 · Mastcam"). Baixa a
tabela ambiental real daquele sol e imprime algumas leituras com valor
válido (descarta -999 = sem dado).
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.pds_rems import PDSRemsAdapter


def main() -> None:
    sol = int(sys.argv[1]) if len(sys.argv) > 1 else 4650

    adapter = PDSRemsAdapter()
    print(f"[1/2] Buscando tabela ambiental do sol {sol}...")
    resultado = adapter.fetch_sol(sol)
    print(f"      product_id: {resultado['product_id']}")
    print(f"      {len(resultado['leituras'])} leituras no sol")

    print("[2/2] Primeiras leituras com valor válido de pressão e temperatura:")
    count = 0
    for leitura in resultado["leituras"]:
        pressao = leitura.get("BAROCAP_PRESSURE_1")
        temp = leitura.get("BOOM1_AIR_TEMP")
        if pressao is not None and temp is not None:
            temp_c = temp - 273.15
            print(
                f"      {leitura['LMST']}: "
                f"pressão={pressao:.2f} Pa | "
                f"temp_ar={temp_c:.1f}°C | "
                f"UV_A={leitura.get('UV_A')} | "
                f"umidade={leitura.get('HUMIDITY_CHANNEL_A')}%"
            )
            count += 1
        if count >= 5:
            break


if __name__ == "__main__":
    main()
