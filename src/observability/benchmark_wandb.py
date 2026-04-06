"""Flatten benchmark records and send them to WandB when configured.

This module is optional at runtime: if the ``wandb`` package is not installed,
calls no-op with a warning when ``WANDB_ENABLED`` is set.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .wandb_derived_metrics import SuiteRollingViz, derived_benchmark_viz_metrics
from .wandb_settings import WandbSettings, load_wandb_settings, wandb_requirements_satisfied

_log = logging.getLogger(__name__)


def flatten_benchmark_record_for_wandb(record: dict[str, Any]) -> dict[str, Any]:
    """Turn a :meth:`PlanExecuteMetrics.to_benchmark_record` dict into WandB-friendly scalars.

    Appends ``viz/*`` derived metrics (latency, context, cost, quality, reliability); see
    :mod:`observability.wandb_derived_metrics`. Uses slash-separated keys so the WandB UI groups
    metrics. Omits raw
    ``question`` text by default (length only) to avoid leaking prompts into
    shared projects; set ``WANDB_LOG_QUESTION=1`` to include a ``bench/question``
    string (use only in private projects).
    """
    out: dict[str, Any] = {}
    scalars = (
        "discover_ms",
        "plan_ms",
        "execute_ms",
        "summarize_ms",
        "e2e_ms",
        "success",
        "plan_steps",
        "history_steps",
        "tool_calls_attempted",
        "tool_calls_succeeded",
        "failed_steps",
    )
    for k in scalars:
        if k in record and record[k] is not None:
            v = record[k]
            if k == "success":
                out[f"bench/{k}"] = bool(v)
            else:
                out[f"bench/{k}"] = v

    pm = record.get("phase_ms") or {}
    if isinstance(pm, dict):
        for key, val in pm.items():
            if val is not None:
                out[f"bench/phase/{key}_ms"] = val

    tu = record.get("token_usage") or {}
    if isinstance(tu, dict):
        for section in (
            "plan",
            "summarize",
            "execute_arg_resolution",
            "llm_totals",
        ):
            block = tu.get(section)
            if not isinstance(block, dict):
                continue
            for tk, tv in block.items():
                if tv is not None:
                    out[f"bench/token/{section}/{tk}"] = tv
        for flag_key in (
            "llm_prompt_tokens_reported",
            "llm_completion_tokens_reported",
        ):
            if flag_key in tu and tu[flag_key] is not None:
                out[f"bench/token/{flag_key}"] = 1.0 if tu[flag_key] else 0.0

    meta = (
        "scenario_id",
        "scenario_type",
        "model_id",
        "git_sha",
        "error",
    )
    for k in meta:
        if k in record and record[k] is not None:
            out[f"bench/{k}"] = record[k]

    q = record.get("question")
    if isinstance(q, str):
        out["bench/question_char_len"] = len(q)
        if _truthy_env("WANDB_LOG_QUESTION"):
            out["bench/question"] = q

    steps = record.get("step_timings_ms")
    if isinstance(steps, list):
        out["bench/step_timings_count"] = len(steps)
        try:
            out["bench/step_timings_json"] = json.dumps(steps, default=str)[:50_000]
        except (TypeError, ValueError):
            pass

    out.update(derived_benchmark_viz_metrics(record))
    return out


def _truthy_env(name: str) -> bool:
    v = os.environ.get(name)
    return bool(v and v.strip().lower() in ("1", "true", "yes", "on"))


def _slug_segment(s: str, max_len: int) -> str:
    """Make a W&B-safe single path segment (letters, digits, ._-)."""
    t = re.sub(r"[^a-zA-Z0-9._-]+", "_", s.strip())
    t = t.strip("._-") or "na"
    if len(t) > max_len:
        t = t[: max_len - 3] + "..."
    return t


def derive_informative_run_name(
    job_type: str,
    config: dict[str, Any],
    *,
    when: datetime | None = None,
    max_total_len: int = 127,
) -> str:
    """Build a default run name when ``WANDB_RUN_NAME`` is unset.

    Format (segments joined with ``__``):

    - Optional **suite** stem when ``config`` contains ``suite_file`` (batch benchmarks).
    - **job_type** slug (e.g. ``plan_execute_benchmark``).
    - **UTC timestamp** ``YYYYMMDD_HHMMSS``.
    - **model_id** with ``/`` replaced by ``-`` (truncated).
    - Optional **scenario_id** as ``sc<N>`` when present.
    - Optional first **7** chars of ``git_sha`` when present.

    Total length is capped at ``max_total_len`` for W&B display-name limits.
    """
    dt = when or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts = dt.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")
    parts: list[str] = []

    suite = config.get("suite_file")
    if isinstance(suite, str) and suite.strip():
        parts.append(_slug_segment(Path(suite).stem, 40))

    jt = job_type.strip() or "benchmark"
    parts.append(_slug_segment(jt.replace("_", "-"), 32))
    parts.append(ts)

    mid = config.get("model_id")
    if isinstance(mid, str) and mid.strip():
        parts.append(_slug_segment(mid.replace("/", "-"), 52))

    sid = config.get("scenario_id")
    if sid is not None and str(sid).strip():
        parts.append(_slug_segment(f"sc{sid}", 16))

    sha = config.get("git_sha")
    if isinstance(sha, str) and sha.strip():
        parts.append(_slug_segment(sha.strip()[:7], 8))

    name = "__".join(parts)
    if len(name) > max_total_len:
        name = name[: max_total_len - 3] + "..."
    return name


def _build_wandb_init_kwargs(
    settings: WandbSettings,
    *,
    config: dict[str, Any],
    job_type: str,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "project": settings.project,
        "config": config,
        "job_type": job_type,
    }
    if settings.entity:
        kwargs["entity"] = settings.entity
    if settings.group:
        kwargs["group"] = settings.group
    if settings.tags:
        kwargs["tags"] = list(settings.tags)
    if settings.mode:
        kwargs["mode"] = settings.mode
    if settings.run_name:
        kwargs["name"] = settings.run_name
    else:
        kwargs["name"] = derive_informative_run_name(job_type, config)
    return kwargs


def _import_wandb():
    import importlib.util

    if importlib.util.find_spec("wandb") is None:
        return None
    import wandb

    return wandb


def _configure_wandb_benchmark_step_axis(run: Any) -> None:
    """Tie logged scalars to ``benchmark/suite_step`` so line charts advance per ``log`` call.

    Without :meth:`wandb.Run.define_metric`, the UI may plot ``viz/...`` and ``bench/...``
    on an axis that does not match scenario index, often collapsing series to a single visible
    point (W&B custom x-axes in their track/log docs).
    """
    run.define_metric("benchmark/suite_step")
    # W&B only allows a single trailing ``*`` per metric name (no ``a/*/b`` patterns).
    for pattern in (
        "bench/*",
        "bench/phase/*",
        "bench/token/*",
        "bench/token/plan/*",
        "bench/token/summarize/*",
        "bench/token/execute_arg_resolution/*",
        "bench/token/llm_totals/*",
        "viz/latency/*",
        "viz/context/*",
        "viz/cost/*",
        "viz/quality/*",
        "viz/reliability/*",
        "benchmark/suite_roll/*",
    ):
        run.define_metric(pattern, step_metric="benchmark/suite_step")


def log_plan_execute_benchmark_if_configured(
    record: dict[str, Any],
    *,
    settings: WandbSettings | None = None,
    job_type: str | None = None,
    extra_config: dict[str, Any] | None = None,
) -> None:
    """Single-shot run: ``init`` → ``log`` → ``finish`` (e.g. ``plan-execute`` CLI)."""
    s = settings or load_wandb_settings()
    if not s.enabled:
        return
    if not wandb_requirements_satisfied(s):
        _log.warning(
            "WANDB_ENABLED is set but WANDB_PROJECT is empty; skipping WandB logging."
        )
        return
    wandb = _import_wandb()
    if wandb is None:
        _log.warning(
            "WANDB_ENABLED is set but the wandb package is not installed; "
            "install with: uv sync --group wandb"
        )
        return

    config: dict[str, Any] = {}
    for k in ("model_id", "git_sha", "scenario_id", "scenario_type"):
        if record.get(k) is not None:
            config[k] = record[k]
    if extra_config:
        config.update(extra_config)

    run = wandb.init(
        **_build_wandb_init_kwargs(
            s,
            config=config,
            job_type=job_type or s.job_type_default or "plan_execute_benchmark",
        )
    )
    try:
        _configure_wandb_benchmark_step_axis(run)
        row = flatten_benchmark_record_for_wandb(record)
        row["benchmark/suite_step"] = 0
        run.log(row, step=0)
    finally:
        run.finish()


class WandbBenchmarkBatch:
    """One WandB run over multiple benchmark rows (e.g. scenario suite loop)."""

    def __init__(
        self,
        *,
        settings: WandbSettings | None = None,
        job_type: str | None = None,
        base_config: dict[str, Any] | None = None,
    ) -> None:
        self._settings = settings or load_wandb_settings()
        self._job_type = job_type or self._settings.job_type_default
        self._base_config = dict(base_config or {})
        self._run: Any = None
        self._step = 0
        self._suite_roll = SuiteRollingViz()

    def __enter__(self) -> WandbBenchmarkBatch:
        if not self._settings.enabled:
            return self
        if not wandb_requirements_satisfied(self._settings):
            _log.warning(
                "WANDB_ENABLED is set but WANDB_PROJECT is empty; "
                "skipping WandB batch session."
            )
            return self
        wandb = _import_wandb()
        if wandb is None:
            _log.warning(
                "WANDB_ENABLED is set but the wandb package is not installed; "
                "install with: uv sync --group wandb"
            )
            return self
        self._run = wandb.init(
            **_build_wandb_init_kwargs(
                self._settings,
                config=self._base_config,
                job_type=self._job_type or "benchmark_suite",
            )
        )
        _configure_wandb_benchmark_step_axis(self._run)
        return self

    def log_record(self, record: dict[str, Any]) -> None:
        if not self._run:
            return
        row = flatten_benchmark_record_for_wandb(record)
        row["benchmark/suite_step"] = self._step
        row.update(self._suite_roll.observe(record))
        self._run.log(row, step=self._step)
        self._step += 1

    def __exit__(self, *exc: object) -> None:
        if self._run is not None:
            self._run.finish()
            self._run = None


def should_emit_plan_execute_wandb(
    *, wrote_benchmark_jsonl: bool, settings: WandbSettings | None = None
) -> bool:
    """Whether a single ``plan-execute`` invocation should log to WandB."""
    s = settings or load_wandb_settings()
    if not s.enabled:
        return False
    return wrote_benchmark_jsonl or s.log_each_plan_execute
