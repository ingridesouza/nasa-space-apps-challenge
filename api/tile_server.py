"""Serve tiles XYZ padrão (`/tiles/{layer}/{z}/{x}/{y}.png`) pras
camadas raster reais -- substitui o `ImageSource` de imagem única
(mosaics.py + frontend/src/map/style.ts) por um mapa de tiles de
verdade: zoom/pan carregando por partes, não uma foto esticada.

Por que isso funciona sem reprojeção cartográfica de verdade: o
endereçamento z/x/y -> bbox lon/lat do slippy map padrão (OSM/Google/
qualquer XYZ) é só uma convenção de graus normalizados -- o raio do
corpo celeste só entra na conta de ESCALA/resolução física, não no
endereçamento (mesma ressalva já documentada sobre
OGC_METERS_PER_DEGREE em data-pipeline/adapters/mars_trek_wmts.py).
Nossas coordenadas de Marte já são lon/lat de verdade em todo o
sistema, então um recorte de janela por lon/lat (mesma operação de
`route_planning._latlon_to_rc`) é suficiente -- sem inventar nenhuma
precisão que não existe.

Suporta só os dois `tipo_acesso` que o frontend realmente usa como
camada de tiles (`tiles_wmts` e `hillshade_derivado`) -- `raster_unico`
(DTM/MOLA) não é exibido como tile diretamente hoje, só amostrado
ponto a ponto (ver raster_sampling.py)."""

import functools
import io
import math
import os

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling, reproject

from geo import MARS_RADIUS_M
from mosaics import build_hillshade_array, build_mosaic_image

TILE_SIZE = 256

# PROJ4 ad hoc pra esfera de Marte -- não existe EPSG de Marte, e marcar
# como EPSG:4326 (WGS84 de verdade) seria enganoso. Só usado como
# metadado do GeoTIFF cacheado; todo o recorte de tile é feito por
# aritmética direta do transform, nunca por reprojeção PROJ de verdade.
MARS_GEOGRAPHIC_CRS = f"+proj=longlat +a={MARS_RADIUS_M} +b={MARS_RADIUS_M} +no_defs"


def tile_bounds_lonlat(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) do tile z/x/y -- fórmula
    padrão de slippy map, independente do corpo celeste (ver docstring
    do módulo)."""
    n = 2**z

    def lat_do_y(y_tile: float) -> float:
        t = math.pi * (1 - 2 * y_tile / n)
        return math.degrees(math.atan(math.sinh(t)))

    min_lon = x / n * 360.0 - 180.0
    max_lon = (x + 1) / n * 360.0 - 180.0
    max_lat = lat_do_y(y)
    min_lat = lat_do_y(y + 1)
    return min_lon, min_lat, max_lon, max_lat


def _build_georef_tif(local_tile_path: str, bbox: tuple[float, float, float, float], out_path: str) -> None:
    """Constrói (uma vez, cacheado em disco) um GeoTIFF real a partir do
    mosaico já stitched (mosaics.build_mosaic_image) + bbox real já
    corrigido (ver PROXIMOS-PASSOS.md sobre a correção de
    georreferenciamento de 2026-11-14) -- mesma técnica de
    `rasterio.transform.from_bounds` já usada em route_planning.py."""
    mosaico = build_mosaic_image(local_tile_path)
    if mosaico is None:
        raise RuntimeError(f"Sem tiles em {local_tile_path}")

    min_lon, min_lat, max_lon, max_lat = bbox
    array = np.array(mosaico)  # (rows, cols, 3) RGB
    height, width = array.shape[0], array.shape[1]
    transform = rasterio.transform.from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)

    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=3,
        dtype=array.dtype,
        crs=MARS_GEOGRAPHIC_CRS,
        transform=transform,
    ) as dst:
        for banda in range(3):
            dst.write(array[:, :, banda], banda + 1)


@functools.lru_cache(maxsize=8)
def _load_array_and_transform(layer_name: str, local_tile_path: str, tipo_acesso: str, bbox: tuple[float, float, float, float]):
    """(array, transform) cacheado em memória -- mesmo padrão de
    route_planning._load_dtm, evita reabrir/reconstruir a cada tile
    pedido."""
    if tipo_acesso == "hillshade_derivado":
        shade = build_hillshade_array(local_tile_path)
        if shade is None:
            raise RuntimeError(f"Sem DTM em {local_tile_path} pra gerar hillshade")
        with rasterio.open(local_tile_path) as ds:
            transform, crs = ds.transform, ds.crs
        return shade, transform, (crs or MARS_GEOGRAPHIC_CRS)

    if tipo_acesso == "tiles_wmts":
        georef_path = os.path.join(local_tile_path, "_mosaico_georef.tif")
        if not os.path.exists(georef_path):
            _build_georef_tif(local_tile_path, bbox, georef_path)
        with rasterio.open(georef_path) as ds:
            array = ds.read()  # (3, rows, cols)
            return array, ds.transform, (ds.crs or MARS_GEOGRAPHIC_CRS)

    raise ValueError(f"tipo_acesso {tipo_acesso!r} não é servido como tile -- ver docstring do módulo")


#: cacheia o PNG final (não só o array decodificado) por layer/z/x/y --
#: sem isso, voltar pra um nível de zoom já visitado nessa sessão
#: refaz o reproject do zero toda vez. ~50KB por tile, 2048 tiles
#: cabem em ~100MB -- não arrisca repetir os cortes de memória que já
#: aconteceram nesta sessão (não usei múltiplos workers do uvicorn por
#: esse mesmo motivo: cada worker duplicaria os arrays já cacheados em
#: memória).
@functools.lru_cache(maxsize=2048)
def render_tile(
    layer_name: str, z: int, x: int, y: int, local_tile_path: str, tipo_acesso: str, bbox: tuple[float, float, float, float]
) -> bytes | None:
    """PNG 256x256 do tile pedido, ou None se o tile não intersecta a
    cobertura real da camada (vira 404 em api/main.py, mesmo padrão já
    usado por /mosaics/{layer}.png).

    Reamostragem via `rasterio.warp.reproject` (GDAL) em vez de recorte
    de janela por índice inteiro + resize do PIL -- a versão anterior
    arredondava a janela de cada tile de forma independente, e como
    tile vizinho é outra requisição/arredondamento separado, a borda
    entre dois tiles não batia pixel a pixel (ficava a "costura"/
    distorção visível reportada pelo usuário ao dar zoom). `reproject`
    amostra cada pixel de destino pela coordenada contínua real (sem
    arredondar janela primeiro), então dois tiles vizinhos sempre batem
    exatamente na borda -- e por ser C/GDAL, é bem mais rápido que o
    crop+resize em Python puro de antes."""
    min_lon, min_lat, max_lon, max_lat = bbox
    t_min_lon, t_min_lat, t_max_lon, t_max_lat = tile_bounds_lonlat(z, x, y)

    if t_max_lon < min_lon or t_min_lon > max_lon or t_max_lat < min_lat or t_min_lat > max_lat:
        return None

    array, transform, crs = _load_array_and_transform(layer_name, local_tile_path, tipo_acesso, bbox)
    dst_transform = rasterio.transform.from_bounds(t_min_lon, t_min_lat, t_max_lon, t_max_lat, TILE_SIZE, TILE_SIZE)

    if array.ndim == 2:
        destino = np.zeros((TILE_SIZE, TILE_SIZE), dtype=array.dtype)
    else:
        destino = np.zeros((array.shape[0], TILE_SIZE, TILE_SIZE), dtype=array.dtype)

    # dst_crs = src_crs (mesmo sistema de graus dos dois lados) -- não é
    # uma reprojeção cartográfica de verdade, só reamostragem contínua
    # entre duas grades de pixel diferentes (ver docstring do módulo
    # sobre o endereçamento z/x/y não depender do raio do corpo).
    #
    # Resampling.cubic em vez de bilinear -- interpolação mais nítida
    # dos MESMOS pixels reais ao dar zoom in além da resolução nativa
    # (já confirmado: z16 é o maior nível que o Mars Trek oferece pra
    # HiRISE nessa região, não existe mais detalhe real pra baixar).
    # Isto não inventa nenhum pixel novo, só troca o jeito de
    # interpolar os que já temos por um kernel mais nítido que a média
    # simples do bilinear.
    reproject(
        source=array,
        destination=destino,
        src_transform=transform,
        src_crs=crs,
        dst_transform=dst_transform,
        dst_crs=crs,
        resampling=Resampling.cubic,
    )

    if array.ndim == 2:
        img = Image.fromarray(destino).convert("L").convert("RGB")
    else:
        img = Image.fromarray(np.moveaxis(destino, 0, -1)).convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
