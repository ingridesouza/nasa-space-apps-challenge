"""Adaptador para dados RAD (radiação) do PDS-PPI (UCLA) -- item 8 da
tabela da feature 01.

Formato real (não documentado publicamente de forma clara, confirmado
em 2026-11-11 contra o RAD_RDR_SIS.HTM e o arquivo real do sol 4650):
um único arquivo .TXT por sol, com **1306 seções** no formato
`[NOME_DA_SECAO: NN]` seguidas de linhas de corpo livre. A maioria
(COUNTERS, HISTOGRAMS, PHA, LET...) é dado de engenharia/ciência fina,
fora de escopo deste adaptador -- aqui extraímos só o que a feature 05
(painel de condições) precisa: a dose total por observação.

Como juntar as peças:
  - `[OBSERVATION: NN]` existe para toda observação do sol (NN =
    00, 01, 02, 03...) e tem `START_OBS_MARS`/`START_OBS_UTC` (hora de
    início, LMST e UTC) e `OBS_DURATION` (segundos).
  - `[DOSIMETRY_TOTAL_DOSE_E: NN]` só existe nos índices PARES (nem
    toda observação baixa telemetria de dosimetria completa) e traz um
    único valor numérico: a dose do detector E, em microGy/hora
    (confirmado no RAD_RDR_SIS.HTM, seção 4.2.1.6 -- unidade registrada
    como "microGray/hour" apesar da nota não ser 100% explícita sobre
    se é taxa ou dose acumulada da janela).
  - O "join" entre as duas seções é pelo mesmo índice NN.

Validado contra o sol 4650: dose ~6.6 µGy/h -> ~158 µGy/dia, mesma
ordem de grandeza da dose diária conhecida na superfície de Marte
(~200-250 µGy/dia).

Estrutura do diretório (mesma convenção de buckets do REMS, host
diferente):
  https://pds-ppi.igpp.ucla.edu/data/MSL-M-RAD-3-RDR-V1.0/DATA/
    SOL_<lo>_<hi>/RAD_RDR_<ano>_<doy>_<hh>_<mm>_<sol>_V00.TXT
"""

import re

import requests

BASE_URL = "https://pds-ppi.igpp.ucla.edu/data/MSL-M-RAD-3-RDR-V1.0/DATA"

SECTION_HEADER_RE = re.compile(r"^\[([A-Z_0-9]+): (\d+)\]$")


class PDSRadAdapter:
    categoria = "radiacao"

    def _find_bucket(self, sol: int) -> str:
        r = requests.get(f"{BASE_URL}/", timeout=20)
        r.raise_for_status()
        folders = re.findall(r'href="(SOL_\d+_\d+)/"', r.text)
        for f in folders:
            lo, hi = (int(v) for v in f.replace("SOL_", "").split("_"))
            if lo <= sol <= hi:
                return f
        raise ValueError(f"Nenhum bucket encontrado para o sol {sol}")

    def _find_filename(self, sol: int, bucket: str) -> str:
        url = f"{BASE_URL}/{bucket}/"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        m = re.search(rf'href="(RAD_RDR_[^"]*_{sol}_V\d+\.TXT)"', r.text)
        if not m:
            raise ValueError(f"Arquivo RAD_RDR do sol {sol} não encontrado em {url}")
        return m.group(1)

    @staticmethod
    def _split_sections(text: str) -> dict[tuple[str, int], list[str]]:
        """Quebra o arquivo inteiro em {(nome_secao, indice): [linhas_do_corpo]}."""
        lines = text.splitlines()
        sections: dict[tuple[str, int], list[str]] = {}
        current_key = None
        current_body: list[str] = []

        for line in lines:
            m = SECTION_HEADER_RE.match(line.strip())
            if m:
                if current_key is not None:
                    sections[current_key] = current_body
                current_key = (m.group(1), int(m.group(2)))
                current_body = []
            elif current_key is not None:
                current_body.append(line)

        if current_key is not None:
            sections[current_key] = current_body

        return sections

    @staticmethod
    def _parse_observation_body(body: list[str]) -> dict:
        texto = "\n".join(body)
        campos = dict(re.findall(r'^(\w+)="?([^"\n]*)"?$', texto, re.M))
        return {
            "start_obs_mars": campos.get("START_OBS_MARS", "").strip('"'),
            "start_obs_utc": campos.get("START_OBS_UTC", "").strip('"'),
            "obs_duration_s": float(campos["OBS_DURATION"]) if "OBS_DURATION" in campos else None,
        }

    @staticmethod
    def _parse_dose_body(body: list[str]) -> float | None:
        for line in body:
            stripped = line.strip()
            if stripped:
                try:
                    return float(stripped)
                except ValueError:
                    return None
        return None

    def fetch_sol(self, sol: int) -> dict:
        bucket = self._find_bucket(sol)
        filename = self._find_filename(sol, bucket)

        resp = requests.get(f"{BASE_URL}/{bucket}/{filename}", timeout=60)
        resp.encoding = "latin-1"
        sections = self._split_sections(resp.text)

        observacoes = {
            idx: self._parse_observation_body(body)
            for (nome, idx), body in sections.items()
            if nome == "OBSERVATION"
        }
        doses_e = {
            idx: self._parse_dose_body(body)
            for (nome, idx), body in sections.items()
            if nome == "DOSIMETRY_TOTAL_DOSE_E"
        }

        leituras = []
        for idx in sorted(doses_e):
            obs = observacoes.get(idx, {})
            leituras.append(
                {
                    "indice": idx,
                    "lmst": obs.get("start_obs_mars"),
                    "utc": obs.get("start_obs_utc"),
                    "duracao_s": obs.get("obs_duration_s"),
                    "dose_e_ugy_por_hora": doses_e[idx],
                }
            )

        return {"sol": sol, "product_filename": filename, "leituras": leituras}
