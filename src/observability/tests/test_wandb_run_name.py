"""Unit tests for informative W&B run names (no wandb import)."""

from datetime import datetime, timezone

from observability.benchmark_wandb import derive_informative_run_name


def test_derive_plan_execute_shape():
    name = derive_informative_run_name(
        "plan_execute_benchmark",
        {
            "model_id": "watsonx/meta-llama/llama-4-maverick-17b-128e-instruct-fp8",
            "git_sha": "abcd1234deadbeef",
        },
        when=datetime(2026, 4, 6, 10, 6, 56, tzinfo=timezone.utc),
    )
    assert name.startswith("plan-execute-benchmark__20260406_100656__")
    assert "watsonx-meta-llama-llama-4-maverick-17b-128e-inst..." in name
    assert name.endswith("__abcd123")


def test_derive_suite_includes_scenario_file_stem():
    name = derive_informative_run_name(
        "benchmark_suite",
        {
            "suite_file": "/repo/src/scenarios/local/pump_maintenance_utterance.json",
            "model_id": "m1",
        },
        when=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )
    assert name.startswith("pump_maintenance_utterance__benchmark-suite__20260102_030405__m1")


def test_derive_scenario_id_segment():
    name = derive_informative_run_name(
        "benchmark_suite",
        {"model_id": "x", "scenario_id": 401},
        when=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    assert "__sc401" in name
