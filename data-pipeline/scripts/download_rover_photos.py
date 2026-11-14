"""Baixa de verdade os arquivos de imagem das ~200 fotos já cadastradas
em `rover_images` -- hoje `local_path` guarda a URL remota
(mars.nasa.gov), apesar do nome da coluna. Sem isso, o projeto quebra
inteiro sem internet no evento (toda foto -- grid, lightbox, rastro do
rover -- vira ícone de imagem quebrada).

Depois de rodar, `local_path` passa a guardar só o nome do arquivo
local (ex. "4560MD0016870000303083I01_DXXX.jpg"), salvo em
data/local/rover_photos/, servido pela API via StaticFiles em
/rover-photos (ver api/main.py).

Uso:
    python scripts/download_rover_photos.py
"""

import os
import sys
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "db"))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from connection import get_connection  # noqa: E402

PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "rover_photos")


def main() -> None:
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    conn = get_connection()

    rows = conn.execute("SELECT id, local_path FROM rover_images").fetchall()
    ja_e_url_remota = [r for r in rows if r["local_path"] and r["local_path"].startswith("http")]

    print(f"{len(rows)} fotos no banco, {len(ja_e_url_remota)} ainda apontam pra URL remota.")

    ok, falhas = 0, 0
    for row in ja_e_url_remota:
        url = row["local_path"]
        nome_arquivo = os.path.basename(urlparse(url).path)
        destino = os.path.join(PHOTOS_DIR, nome_arquivo)

        if not os.path.isfile(destino):
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                with open(destino, "wb") as f:
                    f.write(resp.content)
            except requests.RequestException as e:
                print(f"  falhou id={row['id']}: {e}")
                falhas += 1
                continue

        conn.execute(
            "UPDATE rover_images SET local_path = ?, thumbnail_path = ? WHERE id = ?",
            (nome_arquivo, nome_arquivo, row["id"]),
        )
        ok += 1

    conn.commit()
    conn.close()
    print(f"\n{ok} fotos baixadas/atualizadas pra arquivo local, {falhas} falharam.")


if __name__ == "__main__":
    main()
