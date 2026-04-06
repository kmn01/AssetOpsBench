"""Derived scalars for Weights & Biases dashboards (latency, context, cost, quality, reliability).

These keys are **WandB-only**: they are merged in ``flatten_benchmark_record_for_wandb`` and are
not added to JSONL benchmark records. Prefix ``viz/`` keeps them grouped in the W&B UI next to
``bench/*`` raw fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _f(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _i(x: Any) -> int | None:
    if x is None:
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _safe_div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


_PHASE_TOP_KEYS: dict[str, str] = {
    "discover": "discover_ms",
    "plan": "plan_ms",
    "execute": "execute_ms",
    "summarize": "summarize_ms",
}


def _phase_ms_value(record: dict[str, Any], phase: str) -> float | None:
    """Wall ms for a phase: prefer top-level ``discover_ms``-style keys, else ``phase_ms`` dict."""
    top = _f(record.get(_PHASE_TOP_KEYS[phase]))
    if top is not None:
        return top
    pm = record.get("phase_ms")
    if isinstance(pm, dict):
        return _f(pm.get(phase))
    return None


def derived_benchmark_viz_metrics(record: dict[str, Any]) -> dict[str, Any]:
    """Compute dashboard-friendly scalars from a benchmark JSONL-style record.

    Buckets (W&B metric groups):

    - ``viz/latency/*`` — phase fractions, overhead, time per step/tool.
    - ``viz/context/*`` — token totals, bucket mix, tokens per wall-clock second.
    - ``viz/cost/*`` — same counts as ``viz/context/token_*`` under a cost-oriented prefix for panels.
    - ``viz/quality/*`` — success as float, step-level success rate.
    - ``viz/reliability/*`` — tool outcomes, harness errors.

    Omits keys when inputs are missing or division is undefined.
    """
    out: dict[str, Any] = {}

    discover = _phase_ms_value(record, "discover")
    plan = _phase_ms_value(record, "plan")
    execute = _phase_ms_value(record, "execute")
    summarize = _phase_ms_value(record, "summarize")
    e2e = _f(record.get("e2e_ms"))

    parts = [discover, plan, execute, summarize]
    known = [p for p in parts if p is not None]
    if known:
        phase_sum = float(sum(known))
        out["viz/latency/phase_sum_ms"] = phase_sum
        if e2e is not None:
            out["viz/latency/e2e_minus_phase_sum_ms"] = float(e2e) - phase_sum

    if e2e is not None and e2e > 0:
        for name, val in (
            ("discover", discover),
            ("plan", plan),
            ("execute", execute),
            ("summarize", summarize),
        ):
            if val is None:
                continue
            out[f"viz/latency/phase_frac_{name}"] = float(val) / float(e2e)

    hs = _i(record.get("history_steps"))
    ta = _i(record.get("tool_calls_attempted"))
    ts = _i(record.get("tool_calls_succeeded"))
    fs = _i(record.get("failed_steps"))

    if execute is not None and ta is not None and ta > 0:
        out["viz/latency/execute_ms_per_tool_attempt"] = execute / ta
    if e2e is not None and hs is not None and hs > 0:
        out["viz/latency/e2e_ms_per_history_step"] = e2e / hs

    tu = record.get("token_usage")
    if not isinstance(tu, dict):
        tu = {}

    plan_u = tu.get("plan")
    summ_u = tu.get("summarize")
    exec_u = tu.get("execute_arg_resolution")
    totals = tu.get("llm_totals")

    def _tokblk(b: Any, k: str) -> int | None:
        if not isinstance(b, dict):
            return None
        return _i(b.get(k))

    pt_plan = _tokblk(plan_u, "prompt_tokens")
    pt_sum = _tokblk(summ_u, "prompt_tokens")
    pt_ex = _tokblk(exec_u, "prompt_tokens")
    pt_tot = _tokblk(totals, "prompt_tokens")
    ct_tot = _tokblk(totals, "completion_tokens")
    tot_tok = _tokblk(totals, "total_tokens")

    if pt_tot is not None:
        out["viz/context/prompt_tokens_total"] = pt_tot
        out["viz/cost/prompt_tokens"] = float(pt_tot)
    if ct_tot is not None:
        out["viz/context/completion_tokens_total"] = ct_tot
        out["viz/cost/completion_tokens"] = float(ct_tot)
    if tot_tok is not None:
        out["viz/context/total_llm_tokens"] = tot_tok
        out["viz/cost/total_llm_tokens"] = float(tot_tok)
        if e2e is not None and e2e > 0:
            out["viz/context/tokens_per_e2e_second"] = float(tot_tok) / (e2e / 1000.0)
        if ts is not None and ts > 0:
            out["viz/context/tokens_per_successful_tool"] = float(tot_tok) / float(ts)
        if hs is not None and hs > 0:
            out["viz/context/tokens_per_history_step"] = float(tot_tok) / float(hs)

    pr = tu.get("llm_prompt_tokens_reported")
    if pr is not None:
        out["viz/context/usage_prompt_reported"] = 1.0 if pr else 0.0
    cr = tu.get("llm_completion_tokens_reported")
    if cr is not None:
        out["viz/context/usage_completion_reported"] = 1.0 if cr else 0.0

    mix_parts: list[tuple[str, int | None]] = [
        ("plan", pt_plan),
        ("summarize", pt_sum),
        ("execute_arg", pt_ex),
    ]
    if pt_tot is not None and pt_tot > 0:
        for label, pt in mix_parts:
            if pt is not None:
                out[f"viz/context/prompt_frac_{label}"] = float(pt) / float(pt_tot)

    succ = record.get("success")
    if isinstance(succ, bool):
        out["viz/quality/success_float"] = 1.0 if succ else 0.0

    if hs is not None and hs >= 0 and fs is not None:
        ok_steps = max(hs - fs, 0)
        if hs > 0:
            out["viz/quality/history_step_success_rate"] = float(ok_steps) / float(hs)

    if ta is not None and ta > 0 and ts is not None:
        out["viz/reliability/tool_call_success_rate"] = float(ts) / float(ta)

    if fs is not None:
        out["viz/reliability/had_step_failures"] = 1.0 if fs > 0 else 0.0

    err = record.get("error")
    if err is not None and str(err).strip():
        out["viz/reliability/had_error"] = 1.0
    elif "error" in record:
        out["viz/reliability/had_error"] = 0.0

    if ta is not None and ts is not None:
        out["viz/reliability/tool_calls_failed"] = float(max(ta - ts, 0))

    return out


@dataclass
class SuiteRollingViz:
    """Incremental suite-level metrics for multi-step W&B runs (``run_benchmark.py``).

    Attach emitted keys next to each ``benchmark/suite_step`` row so line charts show cumulative
    quality/latency/context trends across scenarios without post-processing.
    """

    _n: int = 0
    _successes: int = 0
    _e2e_sum: float = 0.0
    _e2e_n: int = 0
    _prompt_sum: float = 0.0
    _prompt_n: int = 0
    _tool_ok: int = 0
    _tool_att: int = 0
    _tok_total_sum: float = 0.0
    _tok_n: int = 0

    def observe(self, record: dict[str, Any]) -> dict[str, Any]:
        """Return ``benchmark/suite_roll/*`` fields after incorporating ``record``."""
        self._n += 1
        if record.get("success") is True:
            self._successes += 1

        e2e = _f(record.get("e2e_ms"))
        if e2e is not None:
            self._e2e_sum += e2e
            self._e2e_n += 1

        tu = record.get("token_usage")
        if isinstance(tu, dict):
            totals = tu.get("llm_totals")
            if isinstance(totals, dict):
                pt = _i(totals.get("prompt_tokens"))
                if pt is not None:
                    self._prompt_sum += float(pt)
                    self._prompt_n += 1
                tt = _i(totals.get("total_tokens"))
                if tt is not None:
                    self._tok_total_sum += float(tt)
                    self._tok_n += 1

        ta = _i(record.get("tool_calls_attempted"))
        ts = _i(record.get("tool_calls_succeeded"))
        if ta is not None and ta > 0:
            self._tool_att += ta
            self._tool_ok += int(ts or 0)

        out: dict[str, Any] = {
            "benchmark/suite_roll/n_logged": float(self._n),
            "benchmark/suite_roll/mean_success_rate": float(self._successes) / float(self._n),
        }
        if self._e2e_n > 0:
            out["benchmark/suite_roll/mean_e2e_ms_so_far"] = self._e2e_sum / float(
                self._e2e_n
            )
        if self._prompt_n > 0:
            out["benchmark/suite_roll/mean_prompt_tokens_so_far"] = (
                self._prompt_sum / float(self._prompt_n)
            )
        if self._tok_n > 0:
            out["benchmark/suite_roll/mean_total_llm_tokens_so_far"] = (
                self._tok_total_sum / float(self._tok_n)
            )
        if self._tool_att > 0:
            out["benchmark/suite_roll/aggregate_tool_success_rate"] = float(
                self._tool_ok
            ) / float(self._tool_att)
        return out
