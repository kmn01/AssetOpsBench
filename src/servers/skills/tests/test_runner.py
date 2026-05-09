import json

import pytest

from servers.skills.runner import run_skill_impl
from servers.skills.sibling_mcp import set_sibling_pool_for_testing

from .fake_sibling import FakeSiblingMCPPool


@pytest.mark.anyio
async def test_pump_skill_validates_required_arguments(tmp_path, monkeypatch):
    p = tmp_path / "st.json"
    p.write_text(
        json.dumps({"installed": ["assetopsbench/pump_seal_inspection"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    set_sibling_pool_for_testing(FakeSiblingMCPPool({}))
    r = await run_skill_impl(
        "assetopsbench/pump_seal_inspection",
        {"site_name": "", "asset_id": "a", "asset_name": "b"},
    )
    assert r.model_dump().get("error")


@pytest.mark.anyio
async def test_pump_skill_defaults_asset_name_from_asset_id(tmp_path, monkeypatch):
    """Single equipment token (plan-execute often supplies only asset_id)."""
    p = tmp_path / "st.json"
    p.write_text(
        json.dumps({"installed": ["assetopsbench/pump_seal_inspection"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    mapping = {
        ("iot", "sensors"): {
            "site_name": "MAIN",
            "asset_id": "PUMP1",
            "total_sensors": 1,
            "sensors": ["Vibration"],
            "message": "ok",
        },
        ("fmsr", "get_failure_modes"): {
            "asset_name": "PUMP1",
            "failure_modes": [],
        },
        ("wo", "get_work_orders"): {
            "equipment_id": "PUMP1",
            "total": 0,
            "work_orders": [],
            "message": "ok",
        },
    }
    set_sibling_pool_for_testing(FakeSiblingMCPPool(mapping))
    r = await run_skill_impl(
        "assetopsbench/pump_seal_inspection",
        {"site_name": "MAIN", "asset_id": "PUMP1"},
    )
    d = r.model_dump()
    assert "error" not in d
    assert d["overall_ok"] is True


@pytest.mark.anyio
async def test_not_runnable_when_uninstalled(tmp_path, monkeypatch):
    p = tmp_path / "st.json"
    p.write_text(json.dumps({"installed": []}), encoding="utf-8")
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    r = await run_skill_impl(
        "assetopsbench/pump_seal_inspection",
        {
            "site_name": "MAIN",
            "asset_id": "P1",
            "asset_name": "pump",
        },
    )
    data = r.model_dump()
    assert "not installed" in data.get("error", "").lower()


@pytest.mark.anyio
async def test_diagnostics_skill_with_fake_mcp(tmp_path, monkeypatch):
    p = tmp_path / "st.json"
    p.write_text(
        json.dumps({"installed": ["assetopsbench_demo/asset_diagnostics_bundle"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    mapping = {
        ("iot", "sensors"): {
            "site_name": "MAIN",
            "asset_id": "P1",
            "total_sensors": 2,
            "sensors": ["A", "B"],
            "message": "ok",
        },
        ("fmsr", "get_failure_modes"): {
            "asset_name": "chiller",
            "failure_modes": ["Leak"],
        },
        (
            "fmsr",
            "get_failure_mode_sensor_mapping",
        ): {
            "metadata": {},
            "fm2sensor": {},
            "sensor2fm": {},
            "full_relevancy": [],
        },
    }
    set_sibling_pool_for_testing(FakeSiblingMCPPool(mapping))
    r = await run_skill_impl(
        "assetopsbench_demo/asset_diagnostics_bundle",
        {
            "site_name": "MAIN",
            "asset_id": "P1",
            "asset_name": "chiller",
        },
    )
    d = r.model_dump()
    assert d["overall_ok"] is True
    assert len(d["steps"]) == 3


@pytest.mark.anyio
async def test_mapping_skill_passes_prior_step_fields(tmp_path, monkeypatch):
    p = tmp_path / "st.json"
    p.write_text(
        json.dumps({"installed": ["assetopsbench/fmsr_sensor_failure_mapping"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    pool = FakeSiblingMCPPool(
        {
            ("iot", "sensors"): {
                "site_name": "MAIN",
                "asset_id": "Chiller 6",
                "total_sensors": 1,
                "sensors": ["Chiller 6 Supply Temperature"],
                "message": "ok",
            },
            ("fmsr", "get_failure_modes"): {
                "asset_name": "Chiller 6",
                "failure_modes": ["Compressor Overheating"],
            },
            ("fmsr", "get_failure_mode_sensor_mapping"): {
                "metadata": {},
                "fm2sensor": {
                    "Compressor Overheating": ["Chiller 6 Supply Temperature"]
                },
                "sensor2fm": {
                    "Chiller 6 Supply Temperature": ["Compressor Overheating"]
                },
                "full_relevancy": [],
            },
        }
    )
    set_sibling_pool_for_testing(pool)
    r = await run_skill_impl(
        "assetopsbench/fmsr_sensor_failure_mapping",
        {
            "site_name": "MAIN",
            "asset_id": "Chiller 6",
            "asset_name": "Chiller 6",
        },
    )
    d = r.model_dump()
    assert d["overall_ok"] is True
    assert pool.calls[2][2]["failure_modes"] == ["Compressor Overheating"]
    assert pool.calls[2][2]["sensors"] == ["Chiller 6 Supply Temperature"]


@pytest.mark.anyio
async def test_tsfm_forecast_skill_omits_missing_optional_args(tmp_path, monkeypatch):
    p = tmp_path / "st.json"
    p.write_text(
        json.dumps({"installed": ["assetopsbench/tsfm_forecast_sensor"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    pool = FakeSiblingMCPPool(
        {
            ("tsfm", "run_tsfm_forecasting"): {
                "status": "success",
                "results_file": "/tmp/forecast.json",
                "message": "ok",
            },
        }
    )
    set_sibling_pool_for_testing(pool)
    r = await run_skill_impl(
        "assetopsbench/tsfm_forecast_sensor",
        {
            "dataset_path": "chiller.csv",
            "timestamp_column": "Timestamp",
            "target_columns": ["Chiller 6 Supply Temperature"],
        },
    )
    d = r.model_dump()
    assert d["overall_ok"] is True
    assert "model_checkpoint" not in pool.calls[0][2]
    assert "forecast_horizon" not in pool.calls[0][2]


@pytest.mark.anyio
async def test_safety_clearance_fail_when_no_sensors(tmp_path, monkeypatch):
    p = tmp_path / "st.json"
    p.write_text(
        json.dumps({"installed": ["assetopsbench_demo/safety_clearance_check"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    mapping = {
        ("iot", "sensors"): {
            "error": "no sensors",
        },
        ("wo", "get_work_orders"): {
            "equipment_id": "P1",
            "total": 0,
            "work_orders": [],
            "message": "none",
        },
    }
    set_sibling_pool_for_testing(FakeSiblingMCPPool(mapping))
    r = await run_skill_impl(
        "assetopsbench_demo/safety_clearance_check",
        {"site_name": "MAIN", "asset_id": "P1"},
    )
    assert r.model_dump()["overall_ok"] is False


@pytest.mark.anyio
async def test_safety_clearance_accepts_site_and_asset_aliases(tmp_path, monkeypatch):
    """Plan-execute LLM often emits ``site`` / ``asset`` instead of canonical keys."""
    p = tmp_path / "st.json"
    p.write_text(
        json.dumps({"installed": ["assetopsbench_demo/safety_clearance_check"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILL_INSTALL_STATE_PATH", str(p))
    mapping = {
        ("iot", "sensors"): {
            "site_name": "MAIN",
            "asset_id": "P1",
            "total_sensors": 1,
            "sensors": ["A"],
            "message": "ok",
        },
        ("wo", "get_work_orders"): {
            "equipment_id": "P1",
            "total": 1,
            "work_orders": [],
            "message": "ok",
        },
    }
    set_sibling_pool_for_testing(FakeSiblingMCPPool(mapping))
    r = await run_skill_impl(
        "assetopsbench_demo/safety_clearance_check",
        {"site": "MAIN", "asset": "P1"},
    )
    d = r.model_dump()
    assert "error" not in d
    assert d["overall_ok"] is True
