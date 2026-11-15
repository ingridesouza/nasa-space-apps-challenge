"""Testes de GET /api/alvos-cientificos e vector_queries.todos_alvos_cientificos
-- ver docs/feature-02-arquitetura-ferramentas-ia-rota.md, seção 3.1.

Rodar: cd api && python test_alvos_cientificos.py

A tabela `targets` só existe depois da ETL do F03/F04
(data-pipeline/f03/etl/build.py, ver CLAUDE.md). Sem ela rodada
localmente, os testes contra o banco real toleram o 503 declarado em
vez de falhar -- o que eles garantem é o FORMATO da resposta quando o
dado existe, não que o dado exista neste ambiente."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vector_queries import todos_alvos_cientificos

CAMPOS_ESPERADOS = {"nome", "lat", "lon", "medicao_curiosity", "fonte_url"}


def _db_com_alvos():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE targets(id TEXT PRIMARY KEY, name TEXT, kind TEXT, sol INT,
          lat REAL, lon REAL, blog_url TEXT);
        CREATE TABLE measurements(id TEXT PRIMARY KEY, target_id TEXT, instrument TEXT,
          summary TEXT, source_url TEXT);
        """
    )
    conn.execute(
        "INSERT INTO targets VALUES ('t1','Altadena','rocha',4564,-4.805,137.380,'https://blog.example/altadena')"
    )
    conn.execute("INSERT INTO targets VALUES ('t2','SemMedicao','rocha',4600,-4.810,137.390,NULL)")
    conn.execute("INSERT INTO measurements VALUES ('m1','t1','APXS','alto teor de Fe','https://pds.example/apxs')")
    conn.commit()
    return conn


def test_formato_bate_com_o_contrato_da_ferramenta_3_1():
    conn = _db_com_alvos()
    alvos = todos_alvos_cientificos(conn)
    assert len(alvos) == 2
    for alvo in alvos:
        assert set(alvo.keys()) == CAMPOS_ESPERADOS


def test_sem_medicao_devolve_null_nao_string_vazia():
    conn = _db_com_alvos()
    alvos = {a["nome"]: a for a in todos_alvos_cientificos(conn)}
    assert alvos["SemMedicao"]["medicao_curiosity"] is None
    assert alvos["SemMedicao"]["fonte_url"] is None


def test_com_medicao_junta_instrumento_e_usa_fonte_da_medicao():
    conn = _db_com_alvos()
    alvos = {a["nome"]: a for a in todos_alvos_cientificos(conn)}
    assert "APXS" in alvos["Altadena"]["medicao_curiosity"]
    assert alvos["Altadena"]["fonte_url"] == "https://pds.example/apxs"


def test_endpoint_nao_filtra_nem_pontua_devolve_todos_crus():
    # Contrato explícito da seção 3.1: a ferramenta devolve tudo cru, a
    # IA decide o que combina -- nunca um ranking/filtro no backend.
    conn = _db_com_alvos()
    alvos = todos_alvos_cientificos(conn)
    assert {a["nome"] for a in alvos} == {"Altadena", "SemMedicao"}


def test_endpoint_http_formato_ou_erro_declarado():
    from fastapi.testclient import TestClient

    from main import app

    c = TestClient(app)
    r = c.get("/api/alvos-cientificos")
    if r.status_code == 200:
        corpo = r.json()
        assert isinstance(corpo, list)
        for alvo in corpo:
            assert set(alvo.keys()) == CAMPOS_ESPERADOS
    else:
        # tabela `targets` não populada neste ambiente -- erro
        # declarado (503), nunca um 500 cru nem uma lista inventada.
        assert r.status_code == 503
        assert "ETL" in r.json()["detail"]


if __name__ == "__main__":
    testes = [f for nome, f in sorted(globals().items()) if nome.startswith("test_")]
    for t in testes:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(testes)} testes passaram")
