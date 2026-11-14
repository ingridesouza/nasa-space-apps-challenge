"""Acesso ao banco local compartilhado com data-pipeline/db."""

import os
import sys

_DATA_PIPELINE_DB = os.path.join(os.path.dirname(__file__), "..", "data-pipeline", "db")
sys.path.insert(0, _DATA_PIPELINE_DB)

from connection import get_connection  # noqa: E402

__all__ = ["get_connection"]
