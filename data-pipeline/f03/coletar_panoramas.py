#!/usr/bin/env python3
"""
coletar_panoramas.py · H2G2 · Feature 03 · Tarefas M4 + M5

Varre as páginas "Sol XXXX: Right/Left Navigation Camera, Cylindrical Projection"
do science.nasa.gov na janela de sols do boxwork, extrai os metadados de cada
panorama Navcam (sol, site, drive, azimute central...), baixa o PNG em resolução
total e grava tudo num CSV em que cada linha aponta para o seu arquivo de imagem.

Uso:
    pip install requests beautifulsoup4 pillow
    python coletar_panoramas.py                         # sols 4550 a 4845
    python coletar_panoramas.py --sol-ini 4640 --sol-fim 4660   # teste rápido
    python coletar_panoramas.py --urls extras.txt       # + páginas achadas no Google
    python coletar_panoramas.py --sem-imagens           # só o CSV
    python coletar_panoramas.py --max-imagens 50        # muda o teto de downloads

Janela padrão: sols 4550 a 4845, a mesma do plano da feature (tarefas 2, 4 e 7),
que cobre a aproximação e a travessia do boxwork. O CSV lista todos os panoramas
achados; só até 100 imagens (--max-imagens) são baixadas, escolhidas assim:
  1. só panoramas com azimute central e site/drive (sem isso não dá para
     posicionar nem orientar no mapa);
  2. um por parada do rover (rmc), preferindo a câmera direita;
  3. se ainda passar do teto, amostra espaçada ao longo dos sols, para
     cobrir o trajeto inteiro em vez de amontoar no começo.

Saída (pasta --saida, padrão ./dados_panoramas):
    panoramas.csv        uma linha por panorama
    panos/*.png          um PNG por linha selecionada (coluna arquivo_local)

O script pode ser interrompido e rodado de novo: páginas já presentes no CSV e
imagens já baixadas são puladas.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None  # panoramas são largos; desliga o alerta de "bomba"
except ImportError:  # sem Pillow, só não calcula largura/altura/vaov
    Image = None

# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #

URL_PAGINA = (
    "https://science.nasa.gov/resource/"
    "sol-{sol}-{camera}-navigation-camera-cylindrical-projection{sufixo}/"
)
CAMERAS = ("right", "left")
SUFIXOS = ("", "-2", "-3")  # o WordPress acrescenta -2, -3 quando o título se repete
USER_AGENT = "H2G2-DETON8/1.0 (NASA Space Apps Salvador 2026; coleta educacional)"
CREDITO = "NASA/JPL-Caltech"

# --------------------------------------------------------------------------- #
# Expressões regulares (baseadas no texto padrão das páginas, ex. sol 4653):
# "Curiosity took 31 images ... Right Navigation Camera (Navcam) ... centered at
#  185 degrees azimuth (measured clockwise from north). Curiosity took the images
#  on September 08, 2025, Sol 4653 of the Mars Science Laboratory mission at
#  drive 2466, site number 118. The local mean solar time for the image
#  exposures was 3 PM."
# --------------------------------------------------------------------------- #

RE_SOL_TITULO = re.compile(r"Sol\s+(\d{3,5})\s*:", re.I)
RE_CAMERA = re.compile(r"\b(Right|Left)\s+Navigation\s+Camera", re.I)
RE_N_IMAGENS = re.compile(r"took\s+(\d+)\s+images", re.I)
RE_AZIMUTE = re.compile(r"centered\s+at\s+([\d.]+)\s+degrees?\s+azimuth", re.I)
RE_SOLS = re.compile(r"Sols?\s+(\d{3,5}(?:\s*[-–]\s*\d{3,5})?)\s+of\s+the\s+Mars", re.I)
RE_DRIVE = re.compile(r"at\s+drive\s+(\d+)", re.I)
RE_SITE = re.compile(r"site\s+number\s+(\d+)", re.I)
RE_LMST = re.compile(
    r"local\s+mean\s+solar\s+time\s+for\s+the\s+image\s+exposures\s+was\s+(.+?)\.", re.I
)
RE_DATA_CAPTURA = re.compile(r"took\s+the\s+images\s+on\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", re.I)
RE_PNG = re.compile(r"https://assets\.science\.nasa\.gov/content/dam/[^\s\"'<>()]+?\.png", re.I)
# Nome do mosaico: N_R000_4653_EDR118CYLASB2466_AUTOLM1.PNG
#   R = câmera direita (L = esquerda), 4653 = sol, 118 = site, 2466 = drive
RE_NOME_ARQUIVO = re.compile(r"N_([RL])\d{3}_(\d{4})_EDR(\d{3})CYL[A-Z0-9]*?(\d{4})_", re.I)

# --------------------------------------------------------------------------- #
# Modelo de dados: uma linha do CSV
# --------------------------------------------------------------------------- #


@dataclass
class Panorama:
    sol: int | None = None             # sol do título da página
    sols_texto: str = ""               # como aparece no texto (pode ser "4693-4687")
    site: int | None = None
    drive: int | None = None
    rmc: str = ""                      # "site_drive", chave para cruzar com o MMGIS
    azimute_central: float | None = None   # graus, sentido horário a partir do norte
    camera: str = ""                   # right | left
    n_imagens: int | None = None
    data_captura: str = ""             # data terrestre da captura
    lmst: str = ""                     # hora solar local média
    png_url: str = ""
    png_arquivo_original: str = ""
    arquivo_local: str = ""            # caminho do PNG baixado (liga imagem -> linha)
    largura_px: int | None = None
    altura_px: int | None = None
    vaov_graus: float | None = None    # campo de visão vertical = 360 * altura / largura
    tamanho_bytes: int | None = None
    sha256: str = ""
    page_url: str = ""
    credito: str = CREDITO
    verificacao: str = ""              # "ok" ou lista de alertas separados por ";"
    selecionado: str = ""              # "sim" se entrou nas até 100 imagens baixadas


CAMPOS_CSV = [f.name for f in fields(Panorama)]

# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


def nova_sessao() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def get(sessao: requests.Session, url: str, atraso: float, tentativas: int = 3, **kw):
    """GET educado: espera `atraso` segundos, tenta de novo em erro de rede/5xx.
    Devolve a resposta, ou None se a página não existe (404)."""
    for i in range(tentativas):
        try:
            r = sessao.get(url, timeout=60, **kw)
        except requests.RequestException as e:
            print(f"   ! erro de rede ({e.__class__.__name__}), tentativa {i + 1}/{tentativas}")
            time.sleep(atraso * (2 ** (i + 1)))
            continue
        time.sleep(atraso)
        if r.status_code == 404:
            return None
        if r.status_code >= 500 or r.status_code == 429:
            print(f"   ! HTTP {r.status_code}, tentativa {i + 1}/{tentativas}")
            time.sleep(atraso * (2 ** (i + 1)))
            continue
        r.raise_for_status()
        return r
    print(f"   ! desisti de {url}")
    return None


def mesma_url(a: str, b: str) -> bool:
    return a.rstrip("/").lower() == b.rstrip("/").lower()

# --------------------------------------------------------------------------- #
# Leitura de uma página
# --------------------------------------------------------------------------- #


def _int(m: re.Match | None) -> int | None:
    return int(m.group(1)) if m else None


def extrair_png_url(soup: BeautifulSoup, html: str) -> str:
    """Link do PNG em resolução total (o da seção Downloads), não as miniaturas."""
    candidatos = [a["href"] for a in soup.find_all("a", href=True) if RE_PNG.fullmatch(a["href"])]
    candidatos += RE_PNG.findall(html)
    for url in candidatos:
        if "jcr:content" not in url and "renditions" not in url:
            return url
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):  # .../X.PNG/jcr:content/renditions/... -> .../X.PNG
        return og["content"].split("/jcr:content")[0]
    return ""


def ler_pagina(html: str, url: str) -> Panorama | None:
    soup = BeautifulSoup(html, "html.parser")
    og_titulo = soup.find("meta", property="og:title")
    titulo = og_titulo["content"] if og_titulo and og_titulo.get("content") else ""
    if not titulo and soup.h1:
        titulo = soup.h1.get_text(" ", strip=True)
    if "cylindrical projection" not in titulo.lower():
        return None

    texto = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    p = Panorama(page_url=url)
    p.sol = _int(RE_SOL_TITULO.search(titulo))
    m = RE_CAMERA.search(titulo) or RE_CAMERA.search(texto)
    p.camera = m.group(1).lower() if m else ""
    p.n_imagens = _int(RE_N_IMAGENS.search(texto))
    m = RE_AZIMUTE.search(texto)
    p.azimute_central = float(m.group(1)) if m else None
    m = RE_SOLS.search(texto)
    p.sols_texto = re.sub(r"\s+", "", m.group(1)) if m else ""
    p.drive = _int(RE_DRIVE.search(texto))
    p.site = _int(RE_SITE.search(texto))
    m = RE_LMST.search(texto)
    p.lmst = m.group(1).strip() if m else ""
    m = RE_DATA_CAPTURA.search(texto)
    p.data_captura = m.group(1) if m else ""
    p.png_url = extrair_png_url(soup, html)
    p.png_arquivo_original = p.png_url.rsplit("/", 1)[-1] if p.png_url else ""

    verificar(p)
    return p


def verificar(p: Panorama) -> None:
    """Confere o texto contra o nome do arquivo e preenche o que faltar."""
    alertas = []
    m = RE_NOME_ARQUIVO.search(p.png_arquivo_original)
    if m:
        cam_n, sol_n, site_n, drive_n = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        if p.site is None or p.drive is None:
            p.site = p.site if p.site is not None else site_n
            p.drive = p.drive if p.drive is not None else drive_n
            alertas.append("site_drive_do_nome")
        elif (p.site, p.drive) != (site_n, drive_n):
            alertas.append(f"divergencia_nome(texto={p.site}_{p.drive},nome={site_n}_{drive_n})")
        if p.sol is not None and sol_n != p.sol:
            alertas.append(f"sol_nome={sol_n}")
        if not p.camera:
            p.camera = "right" if cam_n.upper() == "R" else "left"
    else:
        alertas.append("nome_fora_do_padrao")
    if p.azimute_central is None:
        alertas.append("sem_azimute")
    if p.site is None or p.drive is None:
        alertas.append("sem_site_drive")
    if not p.png_url:
        alertas.append("sem_png")
    p.rmc = f"{p.site}_{p.drive}" if p.site is not None and p.drive is not None else ""
    p.verificacao = ";".join(alertas) or "ok"

# --------------------------------------------------------------------------- #
# Seleção e download (liga imagem -> linha pela coluna arquivo_local)
# --------------------------------------------------------------------------- #


def _sol(l: dict) -> int:
    return int(l["sol"]) if str(l.get("sol", "")).isdigit() else 10**9


def selecionar(linhas: dict[str, dict], maximo: int) -> list[dict]:
    """Escolhe até `maximo` panoramas para baixar (regras no topo do arquivo)."""
    validos = [l for l in linhas.values()
               if l.get("png_url") and l.get("rmc") and l.get("azimute_central")]
    por_parada: dict[str, dict] = {}
    for l in sorted(validos, key=lambda l: (l["camera"] != "right", l["page_url"])):
        por_parada.setdefault(l["rmc"], l)
    unicos = sorted(por_parada.values(), key=lambda l: (_sol(l), l["rmc"]))
    if len(unicos) <= maximo:
        return unicos
    passo = len(unicos) / maximo
    return [unicos[int(i * passo)] for i in range(maximo)]


def nome_local(l: dict) -> str:
    cam = (l.get("camera") or "x")[0].upper()
    if l.get("rmc"):
        site, drive = (int(x) for x in l["rmc"].split("_"))
        return f"pano_{l['sol']}_{site:03d}_{drive:04d}_{cam}.png"
    return f"pano_{l['sol']}_{Path(l['png_arquivo_original']).stem}.png"


def baixar_imagem(sessao, l: dict, pasta: Path, atraso: float) -> bool:
    destino = pasta / nome_local(l)
    if not destino.exists():
        r = get(sessao, l["png_url"], atraso, stream=True)
        if r is None:
            if "falha_download" not in l["verificacao"]:
                l["verificacao"] += ";falha_download"
            return False
        tmp = destino.with_suffix(".part")
        with open(tmp, "wb") as f:
            for bloco in r.iter_content(1 << 16):
                f.write(bloco)
        tmp.replace(destino)
    l["arquivo_local"] = destino.as_posix()
    dados = destino.read_bytes()
    l["tamanho_bytes"] = str(len(dados))
    l["sha256"] = hashlib.sha256(dados).hexdigest()
    if Image is not None:
        with Image.open(destino) as im:
            w, h = im.size
        l["largura_px"], l["altura_px"] = str(w), str(h)
        l["vaov_graus"] = str(round(360 * h / w, 2))
    return True

# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #


def carregar_csv(caminho: Path) -> dict[str, dict]:
    if not caminho.exists():
        return {}
    with open(caminho, newline="", encoding="utf-8") as f:
        return {linha["page_url"]: {k: linha.get(k, "") for k in CAMPOS_CSV}
                for linha in csv.DictReader(f)}


def salvar_csv(caminho: Path, linhas: dict[str, dict]) -> None:
    tmp = caminho.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CSV)
        w.writeheader()
        for linha in sorted(linhas.values(), key=lambda l: (_sol(l), l["page_url"])):
            w.writerow({k: linha.get(k, "") for k in CAMPOS_CSV})
    tmp.replace(caminho)

# --------------------------------------------------------------------------- #
# Descoberta das páginas (fase 1: só metadados, sem imagens)
# --------------------------------------------------------------------------- #


def urls_candidatas(sol_ini: int, sol_fim: int):
    """Gera (sol, câmera, lista de URLs em ordem de sufixo)."""
    for sol in range(sol_ini, sol_fim + 1):
        for camera in CAMERAS:
            yield sol, camera, [URL_PAGINA.format(sol=sol, camera=camera, sufixo=s) for s in SUFIXOS]


def processar(r, linhas, args, csv_path) -> bool:
    """Lê a página já baixada e grava a linha no CSV; True se era um panorama."""
    url_final = r.url
    if url_final in linhas and not args.refazer:
        return True
    p = ler_pagina(r.text, url_final)
    if p is None:
        return False
    if p.sol is not None and not (args.sol_ini <= p.sol <= args.sol_fim) and not args.aceitar_fora:
        print(f"   - {url_final} é do sol {p.sol}, fora da janela; ignorado")
        return True
    linhas[url_final] = {k: "" if v is None else str(v) for k, v in asdict(p).items()}
    salvar_csv(csv_path, linhas)  # salva a cada página: dá para interromper e retomar
    print(f"   + sol {p.sol} · {p.camera} · site {p.site} drive {p.drive} · "
          f"az {p.azimute_central} · {p.verificacao}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sol-ini", type=int, default=4550)
    ap.add_argument("--sol-fim", type=int, default=4845)
    ap.add_argument("--max-imagens", type=int, default=100, help="teto de PNGs baixados")
    ap.add_argument("--saida", default="dados_panoramas")
    ap.add_argument("--urls", help="arquivo .txt com URLs extras de páginas (uma por linha)")
    ap.add_argument("--atraso", type=float, default=0.7, help="segundos entre requisições")
    ap.add_argument("--sem-imagens", action="store_true", help="só monta o CSV")
    ap.add_argument("--refazer", action="store_true", help="reprocessa páginas já no CSV")
    ap.add_argument("--aceitar-fora", action="store_true", help="aceita sols fora da janela")
    args = ap.parse_args()

    saida = Path(args.saida)
    pasta_img = saida / "panos"
    pasta_img.mkdir(parents=True, exist_ok=True)
    csv_path = saida / "panoramas.csv"
    linhas = carregar_csv(csv_path)
    sessao = nova_sessao()
    print(f"CSV atual: {len(linhas)} panoramas · janela de sols {args.sol_ini}–{args.sol_fim}")

    # Fase 1a) URLs extras (ex.: achadas no Google na tarefa M4)
    if args.urls:
        for url in Path(args.urls).read_text(encoding="utf-8").split():
            print(f"> {url}")
            r = get(sessao, url, args.atraso)
            if r is None or not processar(r, linhas, args, csv_path):
                print("   - não é uma página de panorama")

    # Fase 1b) Varredura por sol: tenta a URL padrão; se existir, tenta -2 e -3
    for sol, camera, candidatas in urls_candidatas(args.sol_ini, args.sol_fim):
        for url in candidatas:
            r = get(sessao, url, args.atraso)
            if r is None:
                break  # sem a página-base, não há -2 nem -3
            if not mesma_url(r.url, url):
                # o WordPress às vezes redireciona um endereço inexistente para outra
                # página parecida; aproveita a página de destino só se for panorama
                processar(r, linhas, args, csv_path)
                break
            print(f"> sol {sol} · {camera} · {url}")
            if not processar(r, linhas, args, csv_path):
                break

    # Fase 2) Seleção de até --max-imagens e download
    escolhidos = selecionar(linhas, args.max_imagens)
    ids = {id(l) for l in escolhidos}
    for l in linhas.values():
        l["selecionado"] = "sim" if id(l) in ids else "nao"
    if not args.sem_imagens:
        print(f"\nBaixando {len(escolhidos)} panoramas (teto {args.max_imagens})...")
        for i, l in enumerate(escolhidos, 1):
            ok = baixar_imagem(sessao, l, pasta_img, args.atraso)
            print(f"  [{i}/{len(escolhidos)}] sol {l['sol']} · {l['rmc']} · {'ok' if ok else 'FALHOU'}")
            salvar_csv(csv_path, linhas)
    salvar_csv(csv_path, linhas)

    alertas = [l for l in linhas.values() if l["verificacao"] != "ok"]
    print(f"\nPronto: {len(linhas)} panoramas no CSV, {len(escolhidos)} selecionados · {csv_path}")
    print(f"Imagens em {pasta_img}/")
    if alertas:
        print(f"{len(alertas)} linha(s) com alerta na coluna 'verificacao' — confira à mão:")
        for l in alertas:
            print(f"  sol {l['sol']}: {l['verificacao']}  {l['page_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())