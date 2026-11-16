"""Tests for GET /api/science-targets and vector_queries.all_science_targets
-- see docs/feature-02-arquitetura-ferramentas-ia-rota.md, section 3.1.

Run: cd api && python test_science_targets.py

The `targets` table only exists after the F03/F04 ETL
(data-pipeline/f03/etl/build.py, see CLAUDE.md). Without it run locally,
the tests against the real database tolerate the declared 503 instead of
failing -- what they guarantee is the response FORMAT when the data
exists, not that the data exists in this environment."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vector_queries import all_science_targets

EXPECTED_FIELDS = {"name", "lat", "lon", "curiosity_measurement", "source_url"}


def _db_with_targets():
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
        "INSERT INTO targets VALUES ('t1','Altadena','rock',4564,-4.805,137.380,'https://blog.example/altadena')"
    )
    conn.execute("INSERT INTO targets VALUES ('t2','NoMeasurement','rock',4600,-4.810,137.390,NULL)")
    conn.execute("INSERT INTO measurements VALUES ('m1','t1','APXS','high Fe content','https://pds.example/apxs')")
    conn.commit()
    return conn


def test_format_matches_the_tool_3_1_contract():
    conn = _db_with_targets()
    targets = all_science_targets(conn)
    assert len(targets) == 2
    for t in targets:
        assert set(t.keys()) == EXPECTED_FIELDS


def test_no_measurement_returns_null_not_an_empty_string():
    conn = _db_with_targets()
    targets = {t["name"]: t for t in all_science_targets(conn)}
    assert targets["NoMeasurement"]["curiosity_measurement"] is None
    assert targets["NoMeasurement"]["source_url"] is None


def test_with_measurement_joins_instrument_and_uses_the_measurement_source():
    conn = _db_with_targets()
    targets = {t["name"]: t for t in all_science_targets(conn)}
    assert "APXS" in targets["Altadena"]["curiosity_measurement"]
    assert targets["Altadena"]["source_url"] == "https://pds.example/apxs"


def test_endpoint_does_not_filter_or_score_returns_everything_raw():
    # Explicit contract of section 3.1: the tool returns everything raw,
    # the AI decides what matches -- never a ranking/filter in the backend.
    conn = _db_with_targets()
    targets = all_science_targets(conn)
    assert {t["name"] for t in targets} == {"Altadena", "NoMeasurement"}


def test_http_endpoint_format_or_declared_error():
    from fastapi.testclient import TestClient

    from main import app

    c = TestClient(app)
    r = c.get("/api/science-targets")
    if r.status_code == 200:
        body = r.json()
        assert isinstance(body, list)
        for t in body:
            assert set(t.keys()) == EXPECTED_FIELDS
    else:
        # `targets` table not populated in this environment -- a declared
        # error (503), never a raw 500 nor a made-up list.
        assert r.status_code == 503
        assert "ETL" in r.json()["detail"]


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} tests passed")
