"""Unit tests for W&B flatten helper (no network / no wandb import required)."""

from observability.benchmark_wandb import flatten_benchmark_record_for_wandb


def test_flatten_includes_phases_and_tokens():
    rec = {
        "e2e_ms": 100.0,
        "success": True,
        "tool_calls_attempted": 2,
        "phase_ms": {"discover": 1.0, "plan": 2.0},
        "token_usage": {
            "llm_totals": {"prompt_tokens": 500, "completion_tokens": 100},
            "llm_prompt_tokens_reported": True,
        },
        "scenario_id": 401,
        "model_id": "test/model",
        "question": "hello",
        "step_timings_ms": [{"step_number": 1}],
    }
    flat = flatten_benchmark_record_for_wandb(rec)
    assert flat["bench/e2e_ms"] == 100.0
    assert flat["bench/success"] is True
    assert flat["bench/phase/discover_ms"] == 1.0
    assert flat["bench/token/llm_totals/prompt_tokens"] == 500
    assert flat["bench/scenario_id"] == 401
    assert flat["bench/question_char_len"] == 5
    assert "bench/question" not in flat
    assert flat["viz/quality/success_float"] == 1.0
    assert "viz/latency/phase_frac_plan" in flat


def test_flatten_omits_question_text_by_default():
    rec = {"question": "secret", "e2e_ms": 1.0, "phase_ms": {}}
    flat = flatten_benchmark_record_for_wandb(rec)
    assert flat["bench/question_char_len"] == 6
    assert "bench/question" not in flat
