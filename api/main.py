"""API da feature 01 -- ver feature-01-mapa-hiperlocal-boxwork.md,
seção 3.2.

Rodar localmente:
    cd api
    python -m uvicorn main:app --reload

Testar:
    http://127.0.0.1:8000/api/point?lat=-4.59&lon=137.44
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agente import AgenteIndisponivel, fontes_do_contexto, montar_contexto, perguntar
from alertas import BASE_LAT_LON, alertas_da_rota, alertas_do_ponto, paradas_no_bbox, tempo_e_alertas_do_sol
from conditions import get_cached_conditions
from db import get_connection
from mosaics import build_hillshade_png, build_mosaic_png
from nomenclature import get_cached_nomenclature
from previsao import apagar_medicao, previsao_do_sol, registrar_medicao, risco_inclinacao, status_previsto
from raster_sampling import sample_all_rasters
from route_planning import ForaDoGridError, SemCaminhoError, plan_route
from sugestao_rotas import sugerir
from tempo_marte import sol_msl
from tile_server import render_tile
from vector_queries import all_photos, nearby_photos, nearest_science_target, todos_alvos_cientificos
import ficha
import panorama

# Sol de referência da missão -- dado real cacheado (não é "hoje",
# é o mesmo sol usado nos testes de REMS/RAD, ver PROXIMOS-PASSOS.md).
# Quando o recorte final do boxwork sair, troca por um sol relevante
# daquela área.
REFERENCE_SOL = 4650

app = FastAPI(title="H2G2 API -- feature 01")

# F03 (panorama/fotos no ponto) e F04 (ficha científica). Arquivos do pacote
# (panoramas, fotos, Mastcam, CRISM) gerados por data-pipeline/f03/etl/build.py.
app.include_router(panorama.router)
app.include_router(ficha.router)
app.mount("/bundle", StaticFiles(directory=panorama.BUNDLE, check_dir=False), name="bundle")


@app.middleware("http")
async def front_sempre_revalidado(request: Request, call_next):
    """Front (web/) com Cache-Control: no-cache -- o navegador revalida a cada carga
    (304 barato, é local). Sem isso, depois de atualizar o sistema ele mistura módulo
    JS velho do cache com novo e a página não sobe."""
    resp = await call_next(request)
    if request.url.path == "/" or request.url.path.endswith((".js", ".mjs", ".css", ".html")):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/api/point")
def get_point(lat: float, lon: float, request: Request):
    """Combina busca vetorial (fotos próximas, alvo científico) e
    sampling de raster (elevação/slope) num único ponto -- contrato
    reaproveitado pela feature 02 (rota/A*) e feature 08 (voz)."""
    conn = get_connection()
    try:
        fotos = nearby_photos(conn, lat, lon, base_url=str(request.base_url).rstrip("/"))
        alvo = nearest_science_target(conn, lat, lon)
        rasters = sample_all_rasters(conn, lat, lon)
    finally:
        conn.close()

    return {
        "point": {"lat": lat, "lon": lon},
        "nearby_photos": fotos,
        "science_target": alvo,
        "raster_values": rasters,
        # feature 08: acréscimo ao contrato, nenhuma chave acima mudou
        "alertas": alertas_do_ponto(lat, lon, rasters),
        # feature 06: chance de o terreno real passar de 15°, pelo histórico do rover
        "previsao_inclinacao": risco_inclinacao(rasters.get("slope_deg")),
    }


@app.get("/layers")
def get_layers():
    """Metadados das camadas já confirmadas -- o frontend usa isto (e
    não uma cópia hardcoded) pra saber bbox/categoria de cada uma, uma
    única fonte de verdade (raster_registry)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT layer_name, min_lon, min_lat, max_lon, max_lat, categoria, tipo_acesso FROM raster_registry"
        ).fetchall()
    finally:
        conn.close()

    return [dict(r) for r in rows]


@app.get("/mosaics/{layer_name}.png")
def get_mosaic(layer_name: str):
    """Imagem única pra exibir uma camada no mapa -- stitch de tiles
    (`tiles_wmts`) ou hillshade gerado na hora a partir de um DTM
    (`hillshade_derivado`). Ver mosaics.py pra entender por que isto
    substitui uma fonte `tiles` XYZ padrão do MapLibre (nossa grade de
    tiles do Mars Trek não é Web Mercator)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT local_tile_path, tipo_acesso FROM raster_registry WHERE layer_name = ?",
            (layer_name,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Camada não encontrada")

    if row["tipo_acesso"] == "hillshade_derivado":
        png_bytes = build_hillshade_png(row["local_tile_path"])
    elif row["tipo_acesso"] == "tiles_wmts":
        png_bytes = build_mosaic_png(row["local_tile_path"], paleta_termica=(layer_name == "themis_termica"))
    else:
        raise HTTPException(status_code=404, detail=f"tipo_acesso {row['tipo_acesso']!r} não vira mosaico")

    if png_bytes is None:
        raise HTTPException(status_code=404, detail="Dado local não encontrado para esta camada")

    return Response(content=png_bytes, media_type="image/png")


@app.get("/api/conditions")
def get_conditions(sol: int = REFERENCE_SOL):
    """Clima (REMS) + radiação (RAD) resumidos de um sol -- não é por
    coordenada (ver feature-01-mapa-hiperlocal-boxwork.md, seção 2.3:
    "não é uma camada de mapa", é valor amarrado ao sol). Lê só do
    cache local (data/local/conditions/), sem chamada de rede."""
    dados = get_cached_conditions(sol)
    if dados is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sol {sol} não cacheado ainda -- rodar data-pipeline/scripts/cache_conditions.py {sol}",
        )
    tempo, alertas = tempo_e_alertas_do_sol(sol)
    return {**dados, "tempo": tempo, "alertas": alertas}


@app.get("/api/nomenclature")
def get_nomenclature():
    """Feições com nome oficial IAU/USGS na região de Gale (item 12 da
    feature 01) -- cacheado por
    data-pipeline/scripts/fetch_nomenclature.py, sem chamada de rede
    aqui."""
    dados = get_cached_nomenclature()
    if dados is None:
        raise HTTPException(
            status_code=404,
            detail="Nomenclatura não cacheada -- rodar data-pipeline/scripts/fetch_nomenclature.py",
        )
    return dados


@app.get("/api/photos")
def get_photos(request: Request):
    """Todas as ~200 fotos reais do Curiosity com posição -- camada
    "rastro do rover" no mapa (pins nas posições reais, não escondidas
    atrás de um raio de busca). Ver vector_queries.all_photos."""
    conn = get_connection()
    try:
        fotos = all_photos(conn, base_url=str(request.base_url).rstrip("/"))
    finally:
        conn.close()
    return fotos


@app.get("/api/rover-track")
def get_rover_track():
    """Paradas do Curiosity dentro do bbox das camadas, com a inclinação
    medida pelo rover já classificada (feature 08, memória do terreno).
    O bbox vem do raster_registry, mesma fonte única do /layers.

    Bug real corrigido: era MIN(min)/MAX(max) -- a UNIÃO dos bbox de
    todas as camadas, dominada pela THEMIS (cobre uma área bem maior
    que o CTX/HiRISE/DTM baixados de verdade). Isso deixava passar
    paradas reais do rover fora de qualquer imagem de base, então a
    trilha aparecia sobre fundo preto ao afastar o zoom. O certo é a
    INTERSECÇÃO (MAX(min)/MIN(max)): só a área onde toda camada tem
    dado de verdade."""
    conn = get_connection()
    try:
        bbox = conn.execute(
            "SELECT MAX(min_lon), MAX(min_lat), MIN(max_lon), MIN(max_lat) FROM raster_registry"
        ).fetchone()
    finally:
        conn.close()

    paradas = paradas_no_bbox(*bbox) if bbox[0] is not None else None
    if paradas is None:
        raise HTTPException(
            status_code=404,
            detail="Trilha não disponível -- rodar data-pipeline/scripts/fetch_rover_waypoints.py e populate_raster_registry.py",
        )
    return paradas


@app.get("/tiles/{layer_name}/{z}/{x}/{y}.png")
def get_tile(layer_name: str, z: int, x: int, y: int):
    """Tile XYZ padrão de verdade -- substitui o ImageSource de imagem
    única (ver /mosaics/{layer}.png e mosaics.py) pra zoom/pan contínuo
    de mapa real. Ver tile_server.py pra entender por que isso não
    precisa de reprojeção cartográfica de verdade."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT local_tile_path, tipo_acesso, min_lon, min_lat, max_lon, max_lat FROM raster_registry WHERE layer_name = ?",
            (layer_name,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Camada não encontrada")

    bbox = (row["min_lon"], row["min_lat"], row["max_lon"], row["max_lat"])
    png_bytes = render_tile(layer_name, z, x, y, row["local_tile_path"], row["tipo_acesso"], bbox)
    if png_bytes is None:
        raise HTTPException(status_code=404, detail="Tile fora da cobertura real desta camada")

    return Response(content=png_bytes, media_type="image/png")


@app.get("/api/alvos-cientificos")
def get_alvos_cientificos():
    """Ferramenta de consulta pra camada de IA (F08/Hugo) decidir destino
    científico em linguagem natural -- ver docs/feature-02-arquitetura-
    ferramentas-ia-rota.md, seção 3.1. Devolve os alvos reais crus, sem
    filtro nem pontuação: quem decide qual combina com o objetivo falado
    é a IA, não este endpoint (hoje só 3 alvos cadastrados, não compensa
    busca/ranking aqui). Reaproveita a mesma query que route_planning.py
    já usa na variante "mais_ciencia" -- nenhuma lógica nova."""
    conn = get_connection()
    try:
        alvos = todos_alvos_cientificos(conn)
    except sqlite3.OperationalError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Tabela de alvos científicos não populada ({e}) -- rodar a ETL do F03/F04 "
            "(data-pipeline/f03/etl/build.py, ver CLAUDE.md) antes de usar este endpoint",
        )
    finally:
        conn.close()
    return alvos


@app.get("/api/route")
def get_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    stop_lat: list[float] = Query(default=[]),
    stop_lon: list[float] = Query(default=[]),
    o2_disponivel_l: float | None = None,
):
    """Feature 02 -- A* real sobre o DTM, duas variantes (mais_segura/
    mais_rapida). Ver route_planning.py pro desvio consciente do AI4Mars
    (não cobre o boxwork -- custo usa só inclinação real, areia vira
    aviso textual). Dose de radiação real (RAD, mesmo REFERENCE_SOL de
    /api/conditions) entra como estimativa acumulada pela duração da
    caminhada -- None se o sol não estiver cacheado, nunca 0 fingido.

    stop_lat/stop_lon (mesmo tamanho, mesma ordem): paradas intermediárias
    entre origem e destino -- gap "paradas intermediárias".

    o2_disponivel_l (Fase 3, opcional): litros de O2 disponíveis no
    início da caminhada -- em litros, não porcentagem, pra não duplicar
    a capacidade do traje aqui (ver docstring de
    route_planning._perfil_margem_de_volta). Sem ele, margem_minima sai
    null em cada rota; o resto do perfil de volta (ponto_nao_retorno,
    pior_trecho_emergencia, volta_minutos_max) não depende disso."""
    if len(stop_lat) != len(stop_lon):
        raise HTTPException(status_code=422, detail="stop_lat e stop_lon precisam ter o mesmo tamanho")
    paradas = list(zip(stop_lat, stop_lon))

    dados_rad = get_cached_conditions(REFERENCE_SOL)
    dose_rad_ugy_por_hora = dados_rad["rad"]["dose_media_ugy_por_hora"] if dados_rad else None

    conn = get_connection()
    try:
        resultado = plan_route(
            conn, origin_lat, origin_lon, dest_lat, dest_lon, dose_rad_ugy_por_hora, paradas, o2_disponivel_l
        )
    except ForaDoGridError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SemCaminhoError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        conn.close()
    # feature 06: cada trecho ganha a chance prevista e o status que a considera
    for rota in resultado["rotas"]:
        for t in rota["trechos_risco"]:
            risco = risco_inclinacao(t["slope_deg"])
            t["chance_pct"] = risco["chance_pct"] if risco else None
            t["status_previsto"] = status_previsto(t["slope_status"], risco)
        rota["trechos_risco_previsto"] = sum(t["status_previsto"] != t["slope_status"] for t in rota["trechos_risco"])

    # feature 08: acréscimo ao contrato, nenhuma chave acima muda --
    # cruza o histórico do rover e o limite de volta à base (mesmas
    # regras do /api/point) com os pontos de cada variante calculada.
    # distancia_m (acima do início, não do destino) vem do mesmo
    # perfil_elevacao do gráfico -- é o "em que trecho" que faltava:
    # sem isso, o alerta valia pra rota inteira, não pra um ponto dela.
    for rota in resultado["rotas"]:
        alertas = alertas_da_rota([tuple(p) for p in rota["pontos"]])
        perfil = rota["perfil_elevacao"]
        for alerta in alertas:
            alerta["distancia_m"] = perfil[alerta.pop("indice_ponto")]["distancia_acumulada_m"]
        alertas.sort(key=lambda a: a["distancia_m"])
        rota["alertas"] = alertas

    # Fase 4 (F02+F08): rótulo ✅/⚠️/⛔ e prós/contras por rota, mais a
    # ordem sugerida -- roda por último porque usa alertas/margem_minima
    # calculados acima. Nenhuma rota é removida/escondida daqui: sugerir()
    # só acrescenta rotulo/pros_contras em cada item de resultado["rotas"].
    resultado["sugestao"] = sugerir(resultado["rotas"])

    return resultado


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=1, max_length=500)
    # sem ponto escolhido, o assistente responde sobre a base (mesma de api/alertas.py)
    lat: float = Field(BASE_LAT_LON[0], ge=-90, le=90)
    lon: float = Field(BASE_LAT_LON[1], ge=-180, le=360)
    sol: int = REFERENCE_SOL


@app.post("/api/ask")
def ask(p: Pergunta, request: Request):
    """Feature 08, fase 2: pergunta em linguagem natural sobre o ponto,
    respondida pelo modelo local só com o contexto do /api/point."""
    ponto = get_point(p.lat, p.lon, request)
    condicoes = get_cached_conditions(p.sol)
    if condicoes:
        condicoes["tempo"], condicoes["alertas"] = tempo_e_alertas_do_sol(p.sol)
        condicoes["previsao_hoje"] = previsao_do_sol(condicoes["tempo"]["sol_agora"])
    ctx = montar_contexto(ponto, condicoes)
    try:
        resposta = perguntar(p.pergunta, ctx)
    except AgenteIndisponivel as e:
        # 503 com os alertas: as regras de segurança não dependem do modelo
        raise HTTPException(status_code=503, detail={"mensagem": str(e), "alertas": ponto["alertas"]})
    # Perigo é dito por regra, antes da resposta: o modelo de 3B às vezes o omite.
    perigos = " ".join(a["mensagem"] for a in ponto["alertas"] if a["nivel"] == "perigo")
    if perigos:
        resposta = f"Perigo: {perigos} {resposta}"
    return {"resposta": resposta, "fontes": fontes_do_contexto(ctx), "alertas": ponto["alertas"]}


@app.get("/api/previsao")
def get_previsao(sol: int | None = None, duracao_min: float | None = Query(None, gt=0, le=24 * 60)):
    """Feature 06: clima previsto para um sol (padrão: o de hoje), offline.
    Estimativa com faixa e erro medido por backtest -- nunca vira "medido".
    Com duracao_min (tempo da rota), sugere a melhor janela do dia para a EVA."""
    prev = previsao_do_sol(sol if sol is not None else sol_msl(datetime.now(timezone.utc)), duracao_min)
    if prev is None:
        raise HTTPException(status_code=404, detail="Sem climatologia: rodar data-pipeline/scripts/cache_climatologia.py")
    return prev


class Medicao(BaseModel):
    """Leitura do sensor do habitat/traje (feature 06): faixas físicas de Gale com folga."""
    sol: int = Field(ge=1, le=20000)
    temp_min_c: float = Field(ge=-150, le=40)
    temp_max_c: float = Field(ge=-150, le=60)
    pressao_pa: float = Field(ge=100, le=1500)
    solo_meio_dia_c: float | None = Field(None, ge=-150, le=80)
    dose_ugy_dia: float | None = Field(None, ge=0, le=100000)


@app.post("/api/medicao")
def post_medicao(m: Medicao):
    if m.temp_min_c > m.temp_max_c:
        raise HTTPException(status_code=422, detail="temp_min_c maior que temp_max_c")
    return registrar_medicao(m.model_dump())


@app.delete("/api/medicao/{sol}")
def delete_medicao(sol: int):
    if not apagar_medicao(sol):
        raise HTTPException(status_code=404, detail=f"Nenhuma medição local no sol {sol}")
    return {"apagada": sol}


@app.get("/api/posicao")
def get_posicao():
    # Sem rastreador real: a posição do astronauta é simulada na base
    # provisória (api/alertas.py), a mesma do limite de 2 km e do assistente.
    lat, lon = BASE_LAT_LON
    return {"lat": lat, "lon": lon, "fonte": "simulado",
            "rotulo": "rastreador simulado: base provisória na parada do Curiosity do sol 4650"}


@app.get("/health")
def health():
    return {"status": "ok"}


# Front HTML/JS puro (web/) servido pela própria API -- mesma origem, offline.
# Fica por último: o mount em "/" engoliria /api, /tiles e /layers se viesse antes.
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
