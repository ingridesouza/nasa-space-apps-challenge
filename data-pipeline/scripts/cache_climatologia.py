"""Feature 06: climatologia do REMS para a previsão local offline.

Baixa uma amostra de 1 sol a cada PASSO sols da missão inteira (~3 anos
marcianos) e grava em data/local/conditions/climatologia.json o resumo de
cada sol com o Ls (estação) do Mars24. A API (api/previsao.py) só lê esse
arquivo.

Cada sol vem de fetch_sol_amostra (180 linhas espalhadas, ~120 KB). Por isso
máx./mín. são "das 180 leituras", não o pico de 1 Hz do sol_<n>.json:
a previsão usa só esta definição, nos dois lados da conta.

Uso:
    python scripts/cache_climatologia.py        # retoma de onde parou
"""

import json
import os
import sys
from statistics import mean, median

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from adapters.pds_rad import PDSRadAdapter  # noqa: E402
from adapters.pds_rems import PDSRemsAdapter  # noqa: E402
from tempo_marte import data_do_sol, ls  # noqa: E402 -- uma só implementação do Mars24

PASSO = 20
ULTIMO_SOL = 4843  # último bucket publicado no PDS em 14/11/2026 (SOL_04710_04843)
EXTRAS = (4650,)  # sol de referência da API: precisa estar na mesma definição
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "conditions", "climatologia.json")


def solo_valido(l: dict) -> bool:
    """Leitura do sensor de solo usável: só de dia (08h–17h locais; à noite o canal B dá
    2–13 K, lixo), recalibração boa (byte 3) e sem sombra no campo de visão (byte 5),
    pelas marcas do próprio PDS, e dentro da física (150–320 K)."""
    t, conf, lmst = l.get("BRIGHTNESS_TEMP_B"), l.get("GTS_CONFIDENCE_LEVEL"), l.get("LMST")
    if not isinstance(t, float) or not isinstance(conf, float) or not isinstance(lmst, str) or "M" not in lmst:
        return False
    bytes_ = f"{int(conf):06d}"
    return 8 <= int(lmst.split("M")[1][:2]) <= 17 and bytes_[3] == "1" and bytes_[5] == "1" and 150 <= t <= 320


def resumo_amostra(leituras: list[dict]) -> dict:
    temps = [l["BOOM1_AIR_TEMP"] - 273.15 for l in leituras if l.get("BOOM1_AIR_TEMP") is not None]
    pressoes = [l["BAROCAP_PRESSURE_1"] for l in leituras if l.get("BAROCAP_PRESSURE_1") is not None]
    # chão ao meio-dia (11h–14h): mediana aguenta o ruído do GTS melhor que mín./máx. de leituras soltas
    solo = [l["BRIGHTNESS_TEMP_B"] - 273.15 for l in leituras
            if solo_valido(l) and 11 <= int(l["LMST"].split("M")[1][:2]) <= 14]
    # curva do dia por hora solar local (LMST "04650M12:15:35.532" -> 12): janela de EVA da F06
    por_hora = {}
    for l in leituras:
        if l.get("BOOM1_AIR_TEMP") is not None and isinstance(l.get("LMST"), str) and "M" in l["LMST"]:
            por_hora.setdefault(int(l["LMST"].split("M")[1][:2]), []).append(l["BOOM1_AIR_TEMP"] - 273.15)
    return {
        "temp_min_c": round(min(temps), 1) if temps else None,
        "temp_max_c": round(max(temps), 1) if temps else None,
        "pressao_pa": round(mean(pressoes), 1) if pressoes else None,
        "temp_por_hora": {str(h): round(mean(v), 1) for h, v in sorted(por_hora.items())},
        "solo_meio_dia_c": round(median(solo), 1) if len(solo) >= 5 else None,
    }


def dose_do_sol(rad: PDSRadAdapter, sol: int) -> float | None:
    """Dose RAD do sol inteiro (µGy/dia, detector E), como em cache_conditions.py."""
    doses = [l["dose_e_ugy_por_hora"] for l in rad.fetch_sol(sol)["leituras"] if l.get("dose_e_ugy_por_hora") is not None]
    return round(mean(doses) * 24, 1) if doses else None


def main() -> None:
    clima = {}
    if os.path.isfile(OUT):
        with open(OUT, encoding="utf-8") as f:
            clima = {c["sol"]: c for c in json.load(f)["sols"]}
    adapter, rad = PDSRemsAdapter(), PDSRadAdapter()
    sols = sorted(set(range(PASSO, ULTIMO_SOL + 1, PASSO)) | set(EXTRAS))
    for i, sol in enumerate(sols, 1):
        if "dose_ugy_dia" in clima.get(sol, {}):
            continue
        try:
            leituras = adapter.fetch_sol_amostra(sol)["leituras"]
        except Exception as e:  # sol sem produto RNV no PDS (buraco) ou rede: segue sem ele
            print(f"[{i}/{len(sols)}] sol {sol}: sem dado ({e.__class__.__name__})")
            continue
        try:
            dose = dose_do_sol(rad, sol)
        except Exception as e:  # sol sem arquivo RAD: segue só com o REMS
            print(f"   sol {sol}: sem RAD ({e.__class__.__name__})")
            dose = None
        clima[sol] = {"sol": sol, "ls": round(ls(data_do_sol(sol)), 1), **resumo_amostra(leituras), "dose_ugy_dia": dose}
        print(f"[{i}/{len(sols)}] sol {sol}: {clima[sol]}")
        # grava a cada sol: download longo, retomável
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump({"fonte": "MSL REMS RNV (PDS Atmospheres), 180 leituras por sol; MSL RAD RDR (PDS-PPI), dose do detector E; Ls pelo Mars24",
                       "passo_sols": PASSO, "sols": sorted(clima.values(), key=lambda c: c["sol"])},
                      f, ensure_ascii=False, indent=1)
    print(f"\n{len(clima)} sols em {OUT}")


if __name__ == "__main__":
    main()
