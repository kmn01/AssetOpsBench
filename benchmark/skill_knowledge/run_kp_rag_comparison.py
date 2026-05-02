#!/usr/bin/env python3
"""Run full KP vs RAG comparison and build dashboard in one command."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_BENCHMARK = REPO_ROOT / "benchmark" / "skill_knowledge" / "run_benchmark.py"
BUILD_DASHBOARD = REPO_ROOT / "benchmark" / "skill_knowledge" / "build_dashboard.py"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--scenarios",
        type=Path,
        default=REPO_ROOT / "src" / "scenarios" / "local" / "vibration_utterance.json",
        help="Scenario JSON file used for both KP and RAG runs.",
    )
    p.add_argument(
        "--model-id",
        default="watsonx/ibm/granite-3-8b-instruct",
        help="Model id used for benchmark runs.",
    )
    p.add_argument(
        "--judge-model-id",
        default="watsonx/ibm/granite-3-8b-instruct",
        help="Judge model id for strict llm-judge scoring.",
    )
    p.add_argument(
        "--ids",
        default="",
        help="Optional comma-separated scenario ids.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional cap of selected scenarios (0 disables).",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "runs",
        help="Directory for generated JSONL files.",
    )
    p.add_argument(
        "--prefix",
        default="pump_kp_vs_rag",
        help="Prefix for generated output files.",
    )
    p.add_argument(
        "--dashboard-template",
        type=Path,
        default=REPO_ROOT / "eval_dashboard_llm_judge_4_23_26_pump_baseline.html",
        help="Dashboard HTML template to update.",
    )
    p.add_argument(
        "--dashboard-output",
        type=Path,
        default=REPO_ROOT / "eval_dashboard_llm_judge_4_23_26_pump_baseline.html",
        help="Output dashboard HTML path.",
    )
    p.add_argument(
        "--include-jsonl",
        type=Path,
        nargs="*",
        default=[],
        help="Optional additional JSONL files to include in dashboard merge.",
    )
    p.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue to dashboard build even if one benchmark fails.",
    )
    return p


def _run(cmd: list[str], *, continue_on_error: bool) -> bool:
    pretty = " ".join(cmd)
    print(f"\n=== Running ===\n{pretty}\n", flush=True)
    res = subprocess.run(cmd, cwd=REPO_ROOT)
    if res.returncode == 0:
        return True
    print(f"[ERROR] exit code {res.returncode}: {pretty}")
    if continue_on_error:
        return False
    raise SystemExit(res.returncode)


def _base_benchmark_cmd(args: argparse.Namespace) -> list[str]:
    cmd = [
        sys.executable,
        str(RUN_BENCHMARK),
        "--source",
        "local",
        "--scenarios",
        str(args.scenarios),
        "--accuracy-mode",
        "llm-judge",
        "--judge-model-id",
        args.judge_model_id,
        "--model-id",
        args.model_id,
    ]
    if args.ids.strip():
        cmd += ["--ids", args.ids]
    if args.limit > 0:
        cmd += ["--limit", str(args.limit)]
    return cmd


def main() -> None:
    args = _build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    kp_out = args.output_dir / f"{args.prefix}_kp_full.jsonl"
    rag_out = args.output_dir / f"{args.prefix}_rag_full.jsonl"

    base = _base_benchmark_cmd(args)
    ok_kp = _run(
        [*base, "--runner-mode", "kp", "--output", str(kp_out)],
        continue_on_error=args.continue_on_error,
    )
    ok_rag = _run(
        [*base, "--runner-mode", "rag", "--output", str(rag_out)],
        continue_on_error=args.continue_on_error,
    )

    include_files = [*args.include_jsonl, kp_out, rag_out]
    build_cmd = [
        sys.executable,
        str(BUILD_DASHBOARD),
        "--template",
        str(args.dashboard_template),
        "--output",
        str(args.dashboard_output),
        "--inputs",
        *[str(p) for p in include_files if Path(p).is_file()],
    ]
    _run(build_cmd, continue_on_error=False)

    print("\nKP/RAG comparison pipeline completed.")
    print(f"KP run: {'ok' if ok_kp else 'failed'} -> {kp_out}")
    print(f"RAG run: {'ok' if ok_rag else 'failed'} -> {rag_out}")
    print(f"Dashboard: {args.dashboard_output}")


if __name__ == "__main__":
    main()