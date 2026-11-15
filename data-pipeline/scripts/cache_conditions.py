"""Baixa REMS+RAD de um sol e grava um resumo local em JSON --
`api/conditions.py` lê só esse arquivo (sem chamada de rede a cada
request, consistente com rodar 100% offline no evento).

Uso:
    python scripts/cache_conditions.py [sol]

Sem argumento, usa o sol 4650 (mesmo exemplo citado no doc da feature 01
e já usado nos testes de REMS/RAD).
"""

import json
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.pds_rad import PDSRadAdapter
from adapters.pds_rems import PDSRemsAdapter

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "conditions")


def summarize_rems(leituras: list[dict]) -> dict:
    validas = [l for l in leituras if l.get("BOOM1_AIR_TEMP") is not None and l.get("BAROCAP_PRESSURE_1") is not None]
    temps_c = [l["BOOM1_AIR_TEMP"] - 273.15 for l in validas]
    pressoes = [l["BAROCAP_PRESSURE_1"] for l in validas]
    uvs = [l["UV_A"] for l in validas if l.get("UV_A") is not None]
    umidades = [l["HUMIDITY_CHANNEL_A"] for l in validas if l.get("HUMIDITY_CHANNEL_A") is not None]

    return {
        "temp_min_c": round(min(temps_c), 1) if temps_c else None,
        "temp_max_c": round(max(temps_c), 1) if temps_c else None,
        "pressao_pa": round(sum(pressoes) / len(pressoes), 1) if pressoes else None,
        "uv_pico": round(max(uvs), 2) if uvs else None,
        "umidade_pct": round(sum(umidades) / len(umidades), 1) if umidades else None,
        "n_leituras": len(validas),
    }


def summarize_rad(leituras: list[dict]) -> dict:
    doses = [l["dose_e_ugy_por_hora"] for l in leituras if l.get("dose_e_ugy_por_hora") is not None]
    media = sum(doses) / len(doses) if doses else None
    return {
        "dose_media_ugy_por_hora": round(media, 2) if media is not None else None,
        "dose_estimada_ugy_por_dia": round(media * 24, 1) if media is not None else None,
        "n_leituras": len(doses),
    }


def main() -> None:
    sol = int(sys.argv[1]) if len(sys.argv) > 1 else 4650
    out_path = os.path.join(OUT_DIR, f"sol_{sol}.json")
    if os.path.exists(out_path):
        # já em cache: não depende do PDS (arquivos de ~20 MB, conexão instável) a cada make build
        print(f"Sol {sol} já em {out_path}; pulando download (apague para baixar de novo)")
        return

    print(f"[1/2] Baixando REMS do sol {sol}...")
    rems = PDSRemsAdapter().fetch_sol(sol)
    rems_resumo = summarize_rems(rems["leituras"])
    print("     ", rems_resumo)

    print(f"[2/2] Baixando RAD do sol {sol}...")
    rad = PDSRadAdapter().fetch_sol(sol)
    rad_resumo = summarize_rad(rad["leituras"])
    print("     ", rad_resumo)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"sol": sol, "rems": rems_resumo, "rad": rad_resumo}, f, ensure_ascii=False, indent=2)

    print(f"\nSalvo em {out_path}")


if __name__ == "__main__":
    main()
