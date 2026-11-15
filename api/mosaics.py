"""Monta um mosaico único a partir dos tiles WMTS já baixados pra uma
camada -- é a alternativa real ao que a gente tentou primeiro (servir
como fonte `tiles` padrão XYZ do MapLibre).

Por que não dá pra usar `tiles` XYZ direto: o MapLibre assume Web
Mercator (EPSG:3857) pra decidir qual x/y pedir em cada zoom. Nossos
tiles vêm da grade própria do WMTS do Mars Trek (CRS geográfico/Marte,
origem e espaçamento diferentes -- ver
data-pipeline/adapters/mars_trek_wmts.py). Então o x/y que o navegador
pede quase nunca bate com o arquivo que baixamos -- tudo 404, mapa em
branco.

Solução: já que só temos uma amostra pequena de tiles (uma única área
de teste, poucos deles), stitch tudo numa imagem só e exibe via
`ImageSource` do MapLibre, que aceita as 4 coordenadas reais do canto
em vez de depender de um esquema de tile padrão.
"""

import io
import os
import re

import numpy as np
import rasterio
from PIL import Image

from geo import MARS_METERS_PER_DEGREE

TILE_FILENAME_RE = re.compile(r"^(\d+)_(\d+)_(\d+)\.png$")


def _list_tiles(folder: str) -> list[tuple[int, int, int, str]]:
    """Devolve [(z, row, col, caminho)] só pro z que efetivamente existe
    -- nossos adaptadores salvam um único nível de zoom por amostra."""
    tiles = []
    for nome in os.listdir(folder):
        m = TILE_FILENAME_RE.match(nome)
        if m:
            z, row, col = (int(v) for v in m.groups())
            tiles.append((z, row, col, os.path.join(folder, nome)))
    return tiles


def build_mosaic_image(local_tile_path: str) -> Image.Image | None:
    """Stitch em memória (devolve a imagem, não PNG já codificado) --
    reaproveitado tanto pelo endpoint de thumbnail (`build_mosaic_png`)
    quanto pelo tile server (`tile_server.py`), que precisa do array de
    pixel pra recortar janelas, não de bytes PNG prontos."""
    tiles = _list_tiles(local_tile_path)
    if not tiles:
        return None

    rows = sorted({t[1] for t in tiles})
    cols = sorted({t[2] for t in tiles})
    row_min, col_min = rows[0], cols[0]

    with Image.open(tiles[0][3]) as amostra:
        tile_w, tile_h = amostra.size

    mosaico = Image.new("RGB", (len(cols) * tile_w, len(rows) * tile_h))
    for _z, row, col, caminho in tiles:
        with Image.open(caminho) as tile_img:
            mosaico.paste(tile_img.convert("RGB"), ((col - col_min) * tile_w, (row - row_min) * tile_h))

    return mosaico


def build_mosaic_png(local_tile_path: str, paleta_termica: bool = False) -> bytes | None:
    """`paleta_termica=True` pra camadas cujo mosaico é cinza puro (hoje
    só THEMIS) -- ver `aplicar_paleta_termica`, mesmo tratamento usado
    pelo tile server (api/tile_server.py), só que aqui pra miniatura do
    painel de camadas (`/mosaics/{layer}.png`)."""
    mosaico = build_mosaic_image(local_tile_path)
    if mosaico is None:
        return None

    if paleta_termica:
        mosaico = Image.fromarray(aplicar_paleta_termica(np.array(mosaico)), mode="RGB")

    buf = io.BytesIO()
    mosaico.save(buf, format="PNG")
    return buf.getvalue()


def build_hillshade_array(dtm_path: str, azimuth_deg: float = 315.0, altitude_deg: float = 45.0) -> np.ndarray | None:
    """Gera um hillshade real a partir de um GeoTIFF de elevação (DTM
    HiRISE 1m ou MOLA) -- fórmula clássica de Horn/ESRI, luz vindo de
    noroeste (315°) a 45° de altura (convenção padrão de cartografia,
    não é a posição real do Sol em Gale naquele sol -- isto é uma
    camada de RELEVO, não de iluminação solar real).

    Não é um algoritmo "oficial" calibrado (ex. GDAL `gdaldem
    hillshade`), mas usa dado de elevação real, mesma filosofia de
    aproximação já documentada em `_slope_degrees`. Devolve o array
    8-bit (não PNG já codificado) -- reaproveitado pelo tile server, que
    precisa recortar janelas do array, não de bytes PNG prontos."""
    with rasterio.open(dtm_path) as ds:
        elevacao = ds.read(1).astype("float64")
        nodata = ds.nodata
        if nodata is not None:
            elevacao = np.where(elevacao == nodata, np.nan, elevacao)

        pixel_size_m = abs(ds.transform.a) * MARS_METERS_PER_DEGREE

    dzdy, dzdx = np.gradient(elevacao, pixel_size_m)

    slope_rad = np.arctan(np.hypot(dzdx, dzdy))
    aspect_rad = np.arctan2(dzdy, -dzdx)

    zenith_rad = np.radians(90 - altitude_deg)
    azimuth_rad = np.radians(azimuth_deg)

    shade = np.cos(zenith_rad) * np.cos(slope_rad) + np.sin(zenith_rad) * np.sin(slope_rad) * np.cos(
        azimuth_rad - aspect_rad
    )
    shade = np.nan_to_num(shade, nan=0.5)

    # Alongamento de contraste (percentil 2-98) -- o boxwork é
    # relativamente plano, então o `shade` bruto fica todo espremido
    # numa faixa estreita de cinza (baixo contraste visual, reportado
    # pelo usuário como "camada ligada mas invisível"). Isto só
    # reescala os MESMOS valores reais de sombreamento pro intervalo
    # 0-255 inteiro, igual ao hillshade do GDAL/QGIS faz por padrão --
    # não inventa relevo novo, só usa a faixa de exibição toda em vez
    # de desperdiçar a maior parte em cinzas quase idênticos.
    p_baixo, p_alto = np.percentile(shade, [2, 98])
    if p_alto > p_baixo:
        shade = (shade - p_baixo) / (p_alto - p_baixo)
    return np.clip(shade * 255, 0, 255).astype("uint8")


#: paleta sequencial (estilo "inferno") pra traduzir o valor de brilho
#: já real do mosaico THEMIS em cor -- é só uma tradução visual do MESMO
#: pixel (não calibra temperatura real em °C, que exigiria metadado
#: radiométrico que não baixamos), por isso o nome evita "temperatura".
#: Sem isso, THEMIS sai cinza puro e fica indistinguível da imagem
#: óptica por baixo (mesmo problema do hillshade acima).
_PALETA_TERMICA_STOPS = [
    (0, (0, 0, 4)),
    (64, (87, 16, 110)),
    (128, (188, 55, 84)),
    (192, (249, 142, 8)),
    (255, (252, 255, 164)),
]


def aplicar_paleta_termica(cinza: np.ndarray) -> np.ndarray:
    """Recebe um array 2D (ou RGB com r==g==b) 0-255 e devolve RGB
    (..., 3) colorido pela paleta sequencial acima -- mesmo valor de
    pixel real, só mapeado numa cor que o olho humano consegue
    distinguir (ver docstring da paleta)."""
    if cinza.ndim == 3:
        cinza = cinza[..., 0] if cinza.shape[-1] in (3, 4) else cinza[0]

    xp = [s[0] for s in _PALETA_TERMICA_STOPS]
    r = np.interp(cinza, xp, [s[1][0] for s in _PALETA_TERMICA_STOPS])
    g = np.interp(cinza, xp, [s[1][1] for s in _PALETA_TERMICA_STOPS])
    b = np.interp(cinza, xp, [s[1][2] for s in _PALETA_TERMICA_STOPS])
    return np.stack([r, g, b], axis=-1).astype("uint8")


def build_hillshade_png(dtm_path: str, azimuth_deg: float = 315.0, altitude_deg: float = 45.0) -> bytes | None:
    shade_8bit = build_hillshade_array(dtm_path, azimuth_deg, altitude_deg)
    if shade_8bit is None:
        return None

    img = Image.fromarray(shade_8bit, mode="L").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
