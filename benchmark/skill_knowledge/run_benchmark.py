#!/usr/bin/env python3
"""Drive plan-execute over scenario JSON files and append HPML-style timing JSONL.

Example (from repo root, with CouchDB and API env configured):

  uv run python benchmark/skill_knowledge/run_benchmark.py \\
    --scenarios src/scenarios/local/pump_maintenance_utterance.json \\
    --output runs/pump_bench.jsonl \\
    --limit 3

See docs/Skills_Server_Benchmarking.md for metrics semantics.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))


def _load_scenarios(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON array")
    return data


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--scenarios",
        type=Path,
        default=_REPO_ROOT / "src/scenarios/local/pump_maintenance_utterance.json",
        help="Scenario JSON array (id, type, text, ...).",
    )
    p.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Append-only JSONL path for benchmark records.",
    )
    p.add_argument(
        "--model-id",
        default="watsonx/meta-llama/llama-4-maverick-17b-128e-instruct-fp8",
        help="LiteLLM model id (same as plan-execute --model-id).",
    )
    p.add_argument(
        "--ids",
        type=str,
        default="",
        help="Comma-separated scenario ids to run (default: all).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max scenarios to run after filtering (0 = no cap).",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=_REPO_ROOT,
        help="Repository root for git_sha in records.",
    )
    return p


async def _run_one(
    runner,
    text: str,
    *,
    model_id: str,
    scenario_id: int | None,
    scenario_type: str | None,
    output: Path,
    repo_root: Path,
    wandb_batch,
) -> None:
    from agent.plan_execute.metrics import PlanExecuteMetrics, append_jsonl

    try:
        result = await runner.run(text)
        if result.metrics is None:
            raise RuntimeError("runner.run returned no metrics")
        err = next((r.error for r in result.history if r.error), None)
        rec = result.metrics.to_benchmark_record(
            question=result.question,
            model_id=model_id,
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            error=err,
            repo_root=repo_root,
        )
        append_jsonl(output, rec)
        wandb_batch.log_record(rec)
    except Exception as exc:
        _log.exception(
            "Benchmark scenario failed (scenario_id=%s, type=%s)",
            scenario_id,
            scenario_type,
        )
        failed = PlanExecuteMetrics(
            discover_ms=0.0,
            plan_ms=0.0,
            execute_ms=0.0,
            summarize_ms=0.0,
            e2e_ms=0.0,
            success=False,
            plan_steps=0,
            history_steps=0,
            tool_calls_attempted=0,
            tool_calls_succeeded=0,
            failed_steps=0,
        )
        rec = failed.to_benchmark_record(
            question=text,
            model_id=model_id,
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            error=f"harness_error: {exc}",
            repo_root=repo_root,
        )
        append_jsonl(output, rec)
        wandb_batch.log_record(rec)


async def _amain() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    args = _build_parser().parse_args()
    from agent.plan_execute.runner import PlanExecuteRunner
    from llm.litellm import LiteLLMBackend

    scenarios = _load_scenarios(args.scenarios)
    id_filter: set[int] | None = None
    if args.ids.strip():
        id_filter = {int(x.strip()) for x in args.ids.split(",") if x.strip()}
        scenarios = [s for s in scenarios if int(s["id"]) in id_filter]
    if args.limit > 0:
        scenarios = scenarios[: args.limit]

    llm = LiteLLMBackend(model_id=args.model_id)
    runner = PlanExecuteRunner(llm=llm)

    from observability.benchmark_wandb import WandbBenchmarkBatch

    suite_config = {
        "suite_file": str(args.scenarios),
        "model_id": args.model_id,
        "jsonl_output": str(args.output),
    }
    with WandbBenchmarkBatch(base_config=suite_config) as wb:
        for row in scenarios:
            sid = int(row["id"])
            stype = str(row.get("type", ""))
            text = str(row["text"])
            await _run_one(
                runner,
                text,
                model_id=args.model_id,
                scenario_id=sid,
                scenario_type=stype,
                output=args.output,
                repo_root=args.repo_root,
                wandb_batch=wb,
            )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
