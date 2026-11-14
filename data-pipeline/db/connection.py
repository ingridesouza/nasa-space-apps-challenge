"""Conexão com o banco local SQLite da feature 01."""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "h2g2.sqlite")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = get_connection(db_path)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    return conn
