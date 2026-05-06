#!/usr/bin/env python3
"""Run the full skill/knowledge benchmark suite with one command.

This wrapper calls benchmark/skill_knowledge/run_benchmark.py multiple times with
predefined configurations and output files.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_BENCHMARK = REPO_ROOT / "benchmark" / "skill_knowledge" / "run_benchmark.py"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--env-file",
        type=Path,
        default=REPO_ROOT / ".env",
        help="Path to dotenv file loaded before running benchmarks.",
    )
    p.add_argument(
        "--model-id",
        default="watsonx/ibm/granite-3-8b-instruct",
        help="Primary model id for task runs.",
    )
    p.add_argument(
        "--judge-model-id",
        default="watsonx/ibm/granite-3-8b-instruct",
        help="Model id for strict llm-judge scoring.",
    )
    p.add_argument(
        "--hf-dataset-name",
        default="ibm-research/AssetOpsBench",
        help="Hugging Face dataset id.",
    )
    p.add_argument(
        "--hf-split",
        default="train",
        help="Hugging Face split.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "runs",
        help="Directory where JSONL outputs are written.",
    )
    p.add_argument(
        "--context-window-tokens",
        type=int,
        default=128000,
        help="Context window used for utilization metrics.",
    )
    p.add_argument(
        "--accuracy-threshold",
        type=float,
        default=0.55,
        help="Heuristic threshold for pass/fail.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional per-run limit for faster smoke runs (0 disables).",
    )
    p.add_argument(
        "--with-wandb",
        action="store_true",
        help="Also run a wandb-enabled benchmark entry.",
    )
    p.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue to next benchmark if one command fails.",
    )
    return p


def _run(cmd: list[str], *, continue_on_error: bool) -> None:
    pretty = " ".join(cmd)
    print(f"\n=== Running ===\n{pretty}\n", flush=True)
    res = subprocess.run(cmd, cwd=REPO_ROOT)
    if res.returncode != 0:
        if continue_on_error:
            print(f"[WARN] command failed with exit code {res.returncode}: {pretty}")
            return
        raise SystemExit(res.returncode)


def _base_cmd() -> list[str]:
    return [sys.executable, str(RUN_BENCHMARK)]


def _with_optional_limit(cmd: list[str], *, limit: int) -> list[str]:
    if limit > 0:
        return [*cmd, "--limit", str(limit)]
    return cmd


def _load_env_file(env_file: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "python-dotenv is required to load .env for run_all_benchmarks.py"
        ) from exc

    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)
        print(f"Loaded environment from: {env_file}")
    else:
        print(f"[WARN] env file not found: {env_file} (continuing with current shell env)")


def main() -> None:
    args = _build_parser().parse_args()
    env_file = args.env_file.resolve()
    _load_env_file(env_file)

    # Print which provider credentials are present without exposing secrets.
    print(
        "Env summary: "
        f"WATSONX_APIKEY={'set' if bool(os.environ.get('WATSONX_APIKEY')) else 'missing'}, "
        f"WATSONX_PROJECT_ID={'set' if bool(os.environ.get('WATSONX_PROJECT_ID')) else 'missing'}, "
        f"LITELLM_API_KEY={'set' if bool(os.environ.get('LITELLM_API_KEY')) else 'missing'}, "
        f"LITELLM_BASE_URL={'set' if bool(os.environ.get('LITELLM_BASE_URL')) else 'missing'}, "
        f"WANDB_ENABLED={os.environ.get('WANDB_ENABLED', 'unset')}"
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    local_scenarios = REPO_ROOT / "src" / "scenarios" / "local" / "pump_maintenance_utterance.json"

    runs: list[list[str]] = []

    # 1) Local baseline (KP / plan-execute)
    runs.append(
        _with_optional_limit(
            _base_cmd()
            + [
                "--source",
                "local",
                "--scenarios",
                str(local_scenarios),
                "--runner-mode",
                "kp",
                "--output",
                str(args.output_dir / "pump_bench_local_kp.jsonl"),
                "--model-id",
                args.model_id,
            ],
            limit=args.limit,
        )
    )

    # 2) Local baseline (RAG)
    runs.append(
        _with_optional_limit(
            _base_cmd()
            + [
                "--source",
                "local",
                "--scenarios",
                str(local_scenarios),
                "--runner-mode",
                "rag",
                "--output",
                str(args.output_dir / "pump_bench_local_rag.jsonl"),
                "--model-id",
                args.model_id,
            ],
            limit=args.limit,
        )
    )

    # 3) Local selected IDs
    runs.append(
        _with_optional_limit(
            _base_cmd()
            + [
                "--source",
                "local",
                "--scenarios",
                str(local_scenarios),
                "--runner-mode",
                "kp",
                "--ids",
                "401,404,405",
                "--output",
                str(args.output_dir / "pump_bench_local_ids.jsonl"),
                "--model-id",
                args.model_id,
            ],
            limit=args.limit,
        )
    )

    # 4) HF baseline
    runs.append(
        _with_optional_limit(
            _base_cmd()
            + [
                "--source",
                "hf",
                "--hf-dataset-name",
                args.hf_dataset_name,
                "--hf-split",
                args.hf_split,
                "--output",
                str(args.output_dir / "hf_assetops_bench.jsonl"),
                "--model-id",
                args.model_id,
            ],
            limit=args.limit,
        )
    )

    # 5) HF shuffle/limit
    cmd_hf_limit = (
        _base_cmd()
        + [
            "--source",
            "hf",
            "--hf-dataset-name",
            args.hf_dataset_name,
            "--hf-split",
            args.hf_split,
            "--shuffle-seed",
            "42",
            "--output",
            str(args.output_dir / "hf_assetops_bench_shuffled.jsonl"),
            "--model-id",
            args.model_id,
        ]
    )
    if args.limit > 0:
        cmd_hf_limit += ["--limit", str(args.limit)]
    else:
        cmd_hf_limit += ["--limit", "100"]
    runs.append(cmd_hf_limit)

    # 6) HF synthetic mixed
    cmd_synth = (
        _base_cmd()
        + [
            "--source",
            "hf",
            "--hf-dataset-name",
            args.hf_dataset_name,
            "--hf-split",
            args.hf_split,
            "--synthetic-copies",
            "2",
            "--synthetic-seed",
            "17",
            "--context-window-tokens",
            str(args.context_window_tokens),
            "--output",
            str(args.output_dir / "hf_assetops_with_synth.jsonl"),
            "--model-id",
            args.model_id,
        ]
    )
    if args.limit > 0:
        cmd_synth += ["--limit", str(args.limit)]
    runs.append(cmd_synth)

    # 7) HF synthetic only
    cmd_synth_only = (
        _base_cmd()
        + [
            "--source",
            "hf",
            "--hf-dataset-name",
            args.hf_dataset_name,
            "--hf-split",
            args.hf_split,
            "--synthetic-copies",
            "3",
            "--synthetic-only",
            "--output",
            str(args.output_dir / "hf_assetops_synth_only.jsonl"),
            "--model-id",
            args.model_id,
        ]
    )
    if args.limit > 0:
        cmd_synth_only += ["--limit", str(args.limit)]
    runs.append(cmd_synth_only)

    # 8) Heuristic accuracy
    cmd_heuristic = (
        _base_cmd()
        + [
            "--source",
            "hf",
            "--hf-dataset-name",
            args.hf_dataset_name,
            "--hf-split",
            args.hf_split,
            "--accuracy-mode",
            "heuristic",
            "--accuracy-threshold",
            str(args.accuracy_threshold),
            "--output",
            str(args.output_dir / "hf_assetops_heuristic.jsonl"),
            "--model-id",
            args.model_id,
        ]
    )
    if args.limit > 0:
        cmd_heuristic += ["--limit", str(args.limit)]
    runs.append(cmd_heuristic)

    # 9) Strict llm-judge accuracy
    cmd_judge = (
        _base_cmd()
        + [
            "--source",
            "hf",
            "--hf-dataset-name",
            args.hf_dataset_name,
            "--hf-split",
            args.hf_split,
            "--accuracy-mode",
            "llm-judge",
            "--judge-model-id",
            args.judge_model_id,
            "--judge-temperature",
            "0.0",
            "--judge-max-retries",
            "2",
            "--output",
            str(args.output_dir / "hf_assetops_llm_judge.jsonl"),
            "--model-id",
            args.model_id,
        ]
    )
    if args.limit > 0:
        cmd_judge += ["--limit", str(args.limit)]
    runs.append(cmd_judge)

    # 10) Both accuracy modes
    cmd_both = (
        _base_cmd()
        + [
            "--source",
            "hf",
            "--hf-dataset-name",
            args.hf_dataset_name,
            "--hf-split",
            args.hf_split,
            "--accuracy-mode",
            "both",
            "--accuracy-threshold",
            str(args.accuracy_threshold),
            "--judge-model-id",
            args.judge_model_id,
            "--judge-temperature",
            "0.0",
            "--judge-max-retries",
            "2",
            "--context-window-tokens",
            str(args.context_window_tokens),
            "--output",
            str(args.output_dir / "hf_assetops_both_accuracy.jsonl"),
            "--model-id",
            args.model_id,
        ]
    )
    if args.limit > 0:
        cmd_both += ["--limit", str(args.limit)]
    runs.append(cmd_both)

    # 11) Optional wandb run
    if args.with_wandb:
        cmd_wandb = (
            _base_cmd()
            + [
                "--source",
                "hf",
                "--hf-dataset-name",
                args.hf_dataset_name,
                "--hf-split",
                args.hf_split,
                "--accuracy-mode",
                "llm-judge",
                "--judge-model-id",
                args.judge_model_id,
                "--output",
                str(args.output_dir / "hf_assetops_wandb.jsonl"),
                "--model-id",
                args.model_id,
            ]
        )
        if args.limit > 0:
            cmd_wandb += ["--limit", str(args.limit)]
        runs.append(cmd_wandb)

    print(f"Planned benchmark runs: {len(runs)}")
    for cmd in runs:
        _run(cmd, continue_on_error=args.continue_on_error)

    print("\nAll benchmark commands completed.")


if __name__ == "__main__":
    main()
