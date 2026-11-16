"""Tests for the simulated Earth-Mars sync (feature 09 extension) -- see
docs/feature-09-earth-mars-sync.md. No network call anywhere in this
module or in earth_sync.py itself -- these tests only exercise the local
file reveal, with a temp directory standing in for data/local/.

Run: cd api && python -m pytest -q test_earth_sync.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import earth_sync


def _write_pending(path: Path, sol: int = 4800, peak_dose_ugy_per_hour: float = 7.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "sol": sol,
        "rems": {"temp_min_c": -70.0, "temp_max_c": -5.0, "pressure_pa": 750.0,
                 "uv_peak": 5.0, "humidity_pct": 4.0, "n_readings": 500},
        "rad": {"mean_dose_ugy_per_hour": peak_dose_ugy_per_hour * 0.9,
                "estimated_dose_ugy_per_day": peak_dose_ugy_per_hour * 0.9 * 24,
                "peak_dose_ugy_per_hour": peak_dose_ugy_per_hour, "n_readings": 20},
    }), encoding="utf-8")


def test_status_reports_no_package_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(earth_sync, "PENDING_PATH", str(tmp_path / "pending.json"))
    status = earth_sync.earth_sync_status()
    assert status["pending"] is False
    assert status["sol"] is None


def test_status_reports_a_waiting_package_without_revealing_its_content(tmp_path, monkeypatch):
    pending = tmp_path / "pending.json"
    _write_pending(pending, sol=4800)
    monkeypatch.setattr(earth_sync, "PENDING_PATH", str(pending))
    status = earth_sync.earth_sync_status()
    assert status["pending"] is True
    assert status["sol"] == 4800
    assert "rems" not in status and "rad" not in status  # the apply endpoint is for that


def test_real_delay_range_is_the_documented_one():
    assert earth_sync.REAL_DELAY_RANGE_MIN == (4, 24)


def test_apply_with_no_pending_package_is_a_clear_404(tmp_path, monkeypatch):
    monkeypatch.setattr(earth_sync, "PENDING_PATH", str(tmp_path / "pending.json"))
    try:
        earth_sync.earth_sync_apply()
        assert False, "expected HTTPException"
    except Exception as e:  # fastapi.HTTPException
        assert getattr(e, "status_code", None) == 404


def test_apply_reveals_the_real_sol_and_writes_it_to_the_active_cache(tmp_path, monkeypatch):
    pending = tmp_path / "earth_sync" / "pending.json"
    conditions_dir = tmp_path / "conditions"
    _write_pending(pending, sol=4800, peak_dose_ugy_per_hour=20.0)  # well above background: triggers a solar alert
    monkeypatch.setattr(earth_sync, "PENDING_PATH", str(pending))
    monkeypatch.setattr(earth_sync, "CONDITIONS_DIR", str(conditions_dir))

    result = earth_sync.earth_sync_apply()

    assert result["sol"] == 4800
    assert result["rad"]["peak_dose_ugy_per_hour"] == 20.0
    assert any(a["type"] == "solar_event" for a in result["alerts"])  # real ratio-based rule, not faked
    assert (conditions_dir / "sol_4800.json").is_file()  # same folder/format api/conditions.py reads
    assert not pending.exists()  # one-shot reveal: consumed, not left to re-apply silently


def test_apply_is_idempotent_safe_if_the_sol_was_already_cached(tmp_path, monkeypatch):
    pending = tmp_path / "earth_sync" / "pending.json"
    conditions_dir = tmp_path / "conditions"
    conditions_dir.mkdir(parents=True)
    (conditions_dir / "sol_4800.json").write_text('{"sol": 4800, "rems": {}, "rad": {}}', encoding="utf-8")
    _write_pending(pending, sol=4800)
    monkeypatch.setattr(earth_sync, "PENDING_PATH", str(pending))
    monkeypatch.setattr(earth_sync, "CONDITIONS_DIR", str(conditions_dir))

    result = earth_sync.earth_sync_apply()  # must not crash or overwrite silently-conflicting data

    assert result["sol"] == 4800


if __name__ == "__main__":
    import pytest as _pytest
    raise SystemExit(_pytest.main([__file__, "-q"]))
