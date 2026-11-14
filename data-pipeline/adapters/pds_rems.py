"""Adaptador para dados REMS (clima) do PDS Atmospheres Node -- item 7
da tabela da feature 01.

Diferente do Mars Trek (raster em tiles), REMS é uma série tabular por
sol: um sol = uma pasta `SOL<nnnn>/` com uma tabela ENVRDR (ambiental
calibrada) em texto delimitado por vírgula, com label PDS4 XML que
descreve as 71 colunas (pressão, temperatura do ar, UV, umidade, etc).

Confirmado em 2026-11-11 contra o sol 4650 real: pressão ~709 Pa,
temperatura do ar ~-69.5°C (madrugada), valores plausíveis para Marte.

Estrutura real do arquivo (não documentada publicamente, descoberta
navegando o diretório):
  https://atmos.nmsu.edu/PDS/data/PDS4/msl_rems_bundle/data_calibrated/
    SOL_<lo>_<hi>/SOL<sol>/RME_<sclk>RNV<sol>0000000_______P1.{xml,TAB}
  -- os buckets SOL_<lo>_<hi> cobrem faixas de ~90-135 sols cada.
"""

import csv
import io
import re

import requests

BASE_URL = "https://atmos.nmsu.edu/PDS/data/PDS4/msl_rems_bundle/data_calibrated"

#: colunas mais úteis pro painel de condições (feature 05) -- a tabela
#: real tem 71 colunas, a maioria incerteza/housekeeping.
CAMPOS_RELEVANTES = {
    "TIMESTAMP": None,
    "LMST": None,
    "BOOM1_AIR_TEMP": "kelvin",
    "BOOM2_AIR_TEMP": "kelvin",
    "BAROCAP_PRESSURE_1": "pascal",
    "BAROCAP_PRESSURE_2": "pascal",
    "UV_A": "W/m2",
    "UV_B": "W/m2",
    "UV_C": "W/m2",
    "UV_ABC": "W/m2",
    "HUMIDITY_CHANNEL_A": "%",
}


class PDSRemsAdapter:
    categoria = "atmosferica"

    def _find_bucket(self, sol: int) -> str:
        r = requests.get(f"{BASE_URL}/", timeout=20)
        r.raise_for_status()
        folders = re.findall(r'href="(SOL_\d+_\d+)/"', r.text)
        for f in folders:
            lo, hi = (int(v) for v in f.replace("SOL_", "").split("_"))
            if lo <= sol <= hi:
                return f
        raise ValueError(f"Nenhum bucket encontrado para o sol {sol}")

    def _find_product_prefix(self, sol: int, bucket: str) -> str:
        """Acha o nome do produto RNV (ambiental calibrado) daquele sol --
        o prefixo numérico (spacecraft clock) muda a cada sol."""
        url = f"{BASE_URL}/{bucket}/SOL{sol:05d}/"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        m = re.search(r'href="([^"]+RNV\d+_+P\d)\.TAB"', r.text)  # P1 nos sols novos, P3 nos antigos
        if not m:
            raise ValueError(f"Produto RNV não encontrado em {url}")
        return m.group(1)

    def fetch_sol(self, sol: int) -> dict:
        """Baixa a tabela ambiental (RNV) de um sol e devolve uma lista
        de leituras já filtradas pros campos relevantes (seções inválidas
        do instrumento vêm como -999/-999.00, descartadas aqui)."""
        bucket = self._find_bucket(sol)
        prefix = self._find_product_prefix(sol, bucket)
        base = f"{BASE_URL}/{bucket}/SOL{sol:05d}/"

        xml = requests.get(base + prefix + ".xml", timeout=20).text
        field_blocks = re.findall(r"<Field_Character>.*?</Field_Character>", xml, re.S)
        names = [re.search(r"<name>([^<]+)</name>", f).group(1) for f in field_blocks]

        tab = requests.get(base + prefix + ".TAB", timeout=60)
        text = tab.content.decode("ascii", errors="replace")
        return {"sol": sol, "product_id": prefix, "leituras": self._ler_linhas(text, names)}

    def fetch_sol_amostra(self, sol: int, n: int = 180) -> dict:
        """Igual a fetch_sol, mas baixa só n linhas espalhadas pelo sol num
        único pedido HTTP com vários Range (~120 KB em vez de ~20 MB). O Apache
        do PDS devolve o arquivo inteiro acima de 200 faixas (MaxRanges). A
        tabela é Table_Character: toda linha tem record_length bytes."""
        bucket = self._find_bucket(sol)
        prefix = self._find_product_prefix(sol, bucket)
        base = f"{BASE_URL}/{bucket}/SOL{sol:05d}/"

        xml = requests.get(base + prefix + ".xml", timeout=20).text
        field_blocks = re.findall(r"<Field_Character>.*?</Field_Character>", xml, re.S)
        names = [re.search(r"<name>([^<]+)</name>", f).group(1) for f in field_blocks]
        tam = int(re.search(r"<record_length[^>]*>(\d+)<", xml).group(1))
        total = int(re.search(r"<records>(\d+)</records>", xml).group(1))
        inicios = sorted({i * total // n * tam for i in range(n)})
        faixas = ",".join(f"{o}-{o + tam - 1}" for o in inicios)
        tab = requests.get(base + prefix + ".TAB", headers={"Range": f"bytes={faixas}"}, timeout=60)
        tab.raise_for_status()
        # resposta multipart: sobram só as linhas de dado (começam pelo relógio da sonda)
        linhas = [l for l in tab.content.decode("ascii", errors="replace").splitlines()
                  if re.match(r"\s*\d+,\"\d{5}M", l)]
        return {"sol": sol, "product_id": prefix, "leituras": self._ler_linhas("\n".join(linhas), names)}

    @staticmethod
    def _ler_linhas(text: str, names: list[str]) -> list[dict]:
        reader = csv.reader(io.StringIO(text), skipinitialspace=True)
        leituras = []
        for row in reader:
            row = [v.strip() for v in row]
            full = dict(zip(names, row))
            leitura = {}
            for campo in CAMPOS_RELEVANTES:
                val = full.get(campo, "")
                if val in ("-999.00", "-999.000", "-9.990E+02", ""):
                    leitura[campo] = None
                else:
                    try:
                        leitura[campo] = float(val)
                    except ValueError:
                        leitura[campo] = val.strip('"')
            leituras.append(leitura)
        return leituras
