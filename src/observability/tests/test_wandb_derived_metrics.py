"""Tests for W&B dashboard derived metrics (no wandb import)."""

from observability.wandb_derived_metrics import SuiteRollingViz, derived_benchmark_viz_metrics


def test_derived_latency_fractions_and_overhead():
    rec = {
        "discover_ms": 10.0,
        "plan_ms": 20.0,
        "execute_ms": 60.0,
        "summarize_ms": 10.0,
        "e2e_ms": 101.0,
    }
    d = derived_benchmark_viz_metrics(rec)
    assert abs(d["viz/latency/phase_frac_plan"] - 20.0 / 101.0) < 1e-6
    assert d["viz/latency/phase_sum_ms"] == 100.0
    assert d["viz/latency/e2e_minus_phase_sum_ms"] == 1.0


def test_derived_context_and_cost_totals():
    rec = {
        "e2e_ms": 2000.0,
        "history_steps": 2,
        "tool_calls_succeeded": 1,
        "token_usage": {
            "plan": {"prompt_tokens": 100},
            "summarize": {"prompt_tokens": 400},
            "execute_arg_resolution": {"prompt_tokens": 500},
            "llm_totals": {
                "prompt_tokens": 1000,
                "completion_tokens": 200,
                "total_tokens": 1200,
            },
            "llm_prompt_tokens_reported": True,
            "llm_completion_tokens_reported": True,
        },
    }
    d = derived_benchmark_viz_metrics(rec)
    assert d["viz/context/prompt_tokens_total"] == 1000
    assert d["viz/cost/total_llm_tokens"] == 1200.0
    assert abs(d["viz/context/tokens_per_e2e_second"] - 600.0) < 1e-6
    assert d["viz/context/prompt_frac_summarize"] == 0.4
    assert d["viz/context/tokens_per_history_step"] == 600.0


def test_derived_quality_and_reliability():
    rec = {
        "success": True,
        "history_steps": 4,
        "failed_steps": 1,
        "tool_calls_attempted": 3,
        "tool_calls_succeeded": 2,
        "error": None,
    }
    d = derived_benchmark_viz_metrics(rec)
    assert d["viz/quality/success_float"] == 1.0
    assert abs(d["viz/quality/history_step_success_rate"] - 0.75) < 1e-6
    assert abs(d["viz/reliability/tool_call_success_rate"] - 2.0 / 3.0) < 1e-6
    assert d["viz/reliability/had_error"] == 0.0
    assert d["viz/reliability/tool_calls_failed"] == 1.0


def test_suite_rolling_cumulative():
    roll = SuiteRollingViz()
    r1 = {"success": True, "e2e_ms": 100.0, "token_usage": {"llm_totals": {"prompt_tokens": 50, "total_tokens": 80}}, "tool_calls_attempted": 2, "tool_calls_succeeded": 2}
    r2 = {"success": False, "e2e_ms": 200.0, "token_usage": {"llm_totals": {"prompt_tokens": 150, "total_tokens": 200}}, "tool_calls_attempted": 1, "tool_calls_succeeded": 0}
    a1 = roll.observe(r1)
    assert a1["benchmark/suite_roll/mean_success_rate"] == 1.0
    assert a1["benchmark/suite_roll/mean_e2e_ms_so_far"] == 100.0
    a2 = roll.observe(r2)
    assert abs(a2["benchmark/suite_roll/mean_success_rate"] - 0.5) < 1e-6
    assert abs(a2["benchmark/suite_roll/mean_e2e_ms_so_far"] - 150.0) < 1e-6
    assert abs(a2["benchmark/suite_roll/aggregate_tool_success_rate"] - 2.0 / 3.0) < 1e-6
