"""Wall-clock metrics for plan-execute benchmark harnesses.

All durations use :func:`time.monotonic` in milliseconds. LLM time is included
inside the phase that issued the call (plan, execute-step arg resolution,
summarize); MCP/network time is included in ``mcp_call_ms`` per step.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llm.usage import CompletionUsage, sum_usage_optional

from .models import StepResult


def git_sha_short(repo_root: Path | None = None) -> str | None:
    """Best-effort ``git rev-parse --short HEAD`` for reproducibility in logs."""
    try:
        cwd = repo_root
        if cwd is None:
            cwd = Path(__file__).resolve().parents[3]
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _is_real_tool(step: StepResult) -> bool:
    t = (step.tool or "").strip().lower()
    return bool(t) and t not in ("none", "null")


@dataclass
class PlanExecuteMetrics:
    """Phase timings and counters for one ``runner.run`` invocation."""

    discover_ms: float
    plan_ms: float
    execute_ms: float
    summarize_ms: float
    e2e_ms: float
    success: bool
    plan_steps: int
    history_steps: int
    tool_calls_attempted: int
    tool_calls_succeeded: int
    failed_steps: int
    step_timings_ms: list[dict[str, Any]] = field(default_factory=list)
    plan_usage: CompletionUsage | None = None
    summarize_usage: CompletionUsage | None = None
    execute_arg_usage: CompletionUsage | None = None

    def to_json_dict(self) -> dict[str, Any]:
        """Serializable metrics payload (no question/model — add at record boundary)."""
        llm_totals = self._llm_totals()
        return {
            "discover_ms": round(self.discover_ms, 3),
            "plan_ms": round(self.plan_ms, 3),
            "execute_ms": round(self.execute_ms, 3),
            "summarize_ms": round(self.summarize_ms, 3),
            "e2e_ms": round(self.e2e_ms, 3),
            "phase_ms": {
                "discover": round(self.discover_ms, 3),
                "plan": round(self.plan_ms, 3),
                "execute": round(self.execute_ms, 3),
                "summarize": round(self.summarize_ms, 3),
            },
            "success": self.success,
            "plan_steps": self.plan_steps,
            "history_steps": self.history_steps,
            "tool_calls_attempted": self.tool_calls_attempted,
            "tool_calls_succeeded": self.tool_calls_succeeded,
            "failed_steps": self.failed_steps,
            "step_timings_ms": self.step_timings_ms,
            "token_usage": {
                "plan": (self.plan_usage or CompletionUsage()).to_json_fields(),
                "summarize": (
                    self.summarize_usage or CompletionUsage()
                ).to_json_fields(),
                "execute_arg_resolution": (
                    self.execute_arg_usage or CompletionUsage()
                ).to_json_fields(),
                "llm_totals": llm_totals.to_json_fields(),
                "llm_prompt_tokens_reported": llm_totals.prompt_tokens is not None,
                "llm_completion_tokens_reported": llm_totals.completion_tokens
                is not None,
            },
        }

    def _llm_totals(self) -> CompletionUsage:
        parts: list[CompletionUsage] = []
        if self.plan_usage:
            parts.append(self.plan_usage)
        if self.execute_arg_usage:
            parts.append(self.execute_arg_usage)
        if self.summarize_usage:
            parts.append(self.summarize_usage)
        return sum_usage_optional(parts)

    def to_benchmark_record(
        self,
        *,
        question: str,
        model_id: str | None = None,
        scenario_id: int | None = None,
        scenario_type: str | None = None,
        error: str | None = None,
        repo_root: Path | None = None,
    ) -> dict[str, Any]:
        """Single JSON object suitable for one JSONL line (benchmark / WandB ingest)."""
        rec: dict[str, Any] = {
            **self.to_json_dict(),
            "question": question,
            "model_id": model_id,
            "scenario_id": scenario_id,
            "scenario_type": scenario_type,
            "git_sha": git_sha_short(repo_root),
            "error": error,
        }
        return rec

    @staticmethod
    def from_phases_and_history(
        *,
        discover_ms: float,
        plan_ms: float,
        execute_ms: float,
        summarize_ms: float,
        e2e_ms: float,
        history: list[StepResult],
        plan_step_count: int,
        plan_usage: CompletionUsage | None = None,
        summarize_usage: CompletionUsage | None = None,
    ) -> PlanExecuteMetrics:
        step_rows: list[dict[str, Any]] = []
        tool_attempted = 0
        tool_ok = 0
        failed = 0
        exec_arg_slices: list[CompletionUsage] = []
        for r in history:
            if not r.success:
                failed += 1
            is_tool = _is_real_tool(r)
            if is_tool:
                tool_attempted += 1
                if r.success:
                    tool_ok += 1
                if (
                    r.arg_prompt_tokens is not None
                    or r.arg_completion_tokens is not None
                ):
                    exec_arg_slices.append(
                        CompletionUsage(
                            prompt_tokens=r.arg_prompt_tokens,
                            completion_tokens=r.arg_completion_tokens,
                        )
                    )
            row: dict[str, Any] = {
                "step_number": r.step_number,
                "server": r.server,
                "tool": r.tool,
                "success": r.success,
                "error": r.error,
            }
            if r.arg_resolution_ms is not None:
                row["arg_resolution_ms"] = round(r.arg_resolution_ms, 3)
            if r.mcp_call_ms is not None:
                row["mcp_call_ms"] = round(r.mcp_call_ms, 3)
            if r.arg_resolution_ms is not None and r.mcp_call_ms is not None:
                row["step_execute_ms"] = round(
                    r.arg_resolution_ms + r.mcp_call_ms, 3
                )
            if r.arg_prompt_tokens is not None:
                row["arg_prompt_tokens"] = r.arg_prompt_tokens
            if r.arg_completion_tokens is not None:
                row["arg_completion_tokens"] = r.arg_completion_tokens
            step_rows.append(row)

        execute_arg_usage: CompletionUsage | None = None
        if exec_arg_slices:
            execute_arg_usage = sum_usage_optional(exec_arg_slices)

        success = failed == 0 and bool(history)
        return PlanExecuteMetrics(
            discover_ms=discover_ms,
            plan_ms=plan_ms,
            execute_ms=execute_ms,
            summarize_ms=summarize_ms,
            e2e_ms=e2e_ms,
            success=success,
            plan_steps=plan_step_count,
            history_steps=len(history),
            tool_calls_attempted=tool_attempted,
            tool_calls_succeeded=tool_ok,
            failed_steps=failed,
            step_timings_ms=step_rows,
            plan_usage=plan_usage,
            summarize_usage=summarize_usage,
            execute_arg_usage=execute_arg_usage,
        )


def append_jsonl(path: Path | str, record: dict[str, Any]) -> None:
    """Append one UTF-8 JSON line (newline-terminated)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
