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
import random
import re
import sys
from pathlib import Path
from collections.abc import Iterable
from statistics import mean
from typing import Any

try:
    from generate_dashboard import generate_dashboard as render_dashboard
except ModuleNotFoundError:
    from benchmark.skill_knowledge.generate_dashboard import generate_dashboard as render_dashboard

_log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))


def _load_scenarios(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON array")
    return data


def _load_hf_scenarios(
    *,
    dataset_name: str,
    split: str,
    dataset_config: str | None,
) -> list[dict[str, Any]]:
    try:
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "HF dataset loading requires the 'datasets' package. "
            "Install with: uv add datasets"
        ) from exc

    ds = load_dataset(dataset_name, dataset_config, split=split)
    rows = [dict(r) for r in ds]
    if not rows:
        raise ValueError(
            f"No scenarios found in dataset={dataset_name}, "
            f"config={dataset_config!r}, split={split!r}"
        )
    return rows


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_scenario_row(row: dict[str, Any], *, source: str) -> dict[str, Any]:
    text = row.get("text") or row.get("utterance") or row.get("query")
    if not text:
        raise ValueError(f"Scenario row has no text/utterance/query field: keys={sorted(row.keys())}")

    return {
        **row,
        "id": row.get("id"),
        "type": row.get("type") or row.get("scenario_type") or "",
        "category": row.get("category") or "",
        "text": str(text),
        "characteristic_form": row.get("characteristic_form"),
        "scenario_source": source,
        "synthetic": bool(row.get("synthetic", False)),
        "synthetic_parent_id": row.get("synthetic_parent_id"),
    }


def _build_synthetic_text(base_text: str, variant: int) -> str:
    variants = (
        f"Please resolve this asset-operations request:\n{base_text}",
        f"AssetOps task: {base_text}\nReturn a concise but complete answer.",
        f"For maintenance planning, answer the following question with steps:\n{base_text}",
        f"Operational question:\n{base_text}\nInclude assumptions if data is missing.",
    )
    return variants[variant % len(variants)]


def _expand_synthetic_rows(
    rows: list[dict[str, Any]],
    *,
    synthetic_copies: int,
    synthetic_seed: int,
    synthetic_only: bool,
) -> list[dict[str, Any]]:
    if synthetic_copies <= 0:
        return rows

    rng = random.Random(synthetic_seed)
    synthetic_rows: list[dict[str, Any]] = []
    next_fallback_id = 900_000_000

    for row in rows:
        parent_id = _safe_int(row.get("id"))
        if parent_id is None:
            parent_id = next_fallback_id
            next_fallback_id += 1

        for copy_idx in range(1, synthetic_copies + 1):
            variant_offset = rng.randint(0, 10_000)
            synthetic_id = parent_id * 100 + copy_idx
            synthetic_rows.append(
                {
                    **row,
                    "id": synthetic_id,
                    "text": _build_synthetic_text(
                        str(row.get("text", "")),
                        variant=variant_offset + copy_idx,
                    ),
                    "synthetic": True,
                    "synthetic_parent_id": parent_id,
                }
            )

    if synthetic_only:
        return synthetic_rows
    return [*rows, *synthetic_rows]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())


def _token_f1(prediction: str, reference: str) -> float:
    pred_tokens = _tokenize(prediction)
    ref_tokens = _tokenize(reference)
    if not pred_tokens or not ref_tokens:
        return 0.0

    pred_counts: dict[str, int] = {}
    ref_counts: dict[str, int] = {}
    for tok in pred_tokens:
        pred_counts[tok] = pred_counts.get(tok, 0) + 1
    for tok in ref_tokens:
        ref_counts[tok] = ref_counts.get(tok, 0) + 1

    overlap = 0
    for tok, count in pred_counts.items():
        overlap += min(count, ref_counts.get(tok, 0))

    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    if precision + recall == 0:
        return 0.0
    return (2 * precision * recall) / (precision + recall)


def _keyword_coverage(prediction: str, reference: str) -> float:
    stop = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "for",
        "in",
        "on",
        "with",
        "is",
        "are",
        "be",
        "from",
        "at",
        "by",
    }
    ref_keywords = {
        tok
        for tok in _tokenize(reference)
        if len(tok) >= 4 and tok not in stop
    }
    if not ref_keywords:
        return 0.0
    pred_set = set(_tokenize(prediction))
    hits = len(ref_keywords & pred_set)
    return hits / len(ref_keywords)


def _accuracy_eval(
    *,
    prediction: str,
    characteristic_form: str | None,
    threshold: float,
) -> dict[str, Any]:
    ref = (characteristic_form or "").strip()
    if not ref:
        return {
            "accuracy_has_reference": False,
            "accuracy_score": None,
            "accuracy_pass": None,
            "accuracy_token_f1": None,
            "accuracy_keyword_coverage": None,
            "accuracy_threshold": threshold,
        }

    f1 = _token_f1(prediction, ref)
    kw_cov = _keyword_coverage(prediction, ref)
    score = round(0.5 * f1 + 0.5 * kw_cov, 6)
    return {
        "accuracy_has_reference": True,
        "accuracy_score": score,
        "accuracy_pass": bool(score >= threshold),
        "accuracy_token_f1": round(f1, 6),
        "accuracy_keyword_coverage": round(kw_cov, 6),
        "accuracy_threshold": threshold,
    }


_JUDGE_RUBRIC_PROMPT = """\
You are a strict industrial AI benchmark grader.

Evaluate the CANDIDATE_ANSWER against the EXPECTED_REFERENCE for the QUESTION.

Return ONLY valid JSON with the following schema:
{{
  "task_completion": true|false,
  "data_retrieval_accuracy": true|false,
  "generalized_result_verification": true|false,
  "agent_sequence_correct": true|false,
  "clarity_and_justification": true|false,
  "hallucinations": true|false,
  "rationale": "short explanation"
}}

Rules:
- Use strict standards. Do not infer unstated facts.
- hallucinations=true if the answer contains materially unsupported claims.
- Output only JSON. No markdown.

QUESTION:
{question}

EXPECTED_REFERENCE:
{reference}

CANDIDATE_ANSWER:
{answer}
"""


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(raw)):
        ch = raw[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                frag = raw[start : i + 1]
                try:
                    parsed = json.loads(frag)
                except json.JSONDecodeError:
                    return None
                if isinstance(parsed, dict):
                    return parsed
                return None
    return None


def _judge_bool(d: dict[str, Any], key: str) -> bool | None:
    v = d.get(key)
    if isinstance(v, bool):
        return v
    return None


async def _llm_judge_eval(
    *,
    question: str,
    prediction: str,
    characteristic_form: str | None,
    judge_llm,
    judge_model_id: str,
    judge_temperature: float,
    judge_max_retries: int,
) -> dict[str, Any]:
    ref = (characteristic_form or "").strip()
    if not ref:
        return {
            "accuracy_judge_has_reference": False,
            "accuracy_judge_valid": None,
            "accuracy_judge_task_completion": None,
            "accuracy_judge_data_retrieval_accuracy": None,
            "accuracy_judge_generalized_result_verification": None,
            "accuracy_judge_agent_sequence_correct": None,
            "accuracy_judge_clarity_and_justification": None,
            "accuracy_judge_hallucinations": None,
            "accuracy_judge_strict_pass": None,
            "accuracy_judge_score": None,
            "accuracy_judge_rationale": None,
            "accuracy_judge_model_id": judge_model_id,
            "accuracy_judge_ms": None,
            "accuracy_judge_prompt_tokens": None,
            "accuracy_judge_completion_tokens": None,
            "accuracy_judge_total_tokens": None,
            "accuracy_judge_error": None,
            "accuracy_judge_raw_output": None,
        }

    prompt = _JUDGE_RUBRIC_PROMPT.format(
        question=question,
        reference=ref,
        answer=prediction,
    )
    last_error: str | None = None
    last_raw: str | None = None

    for _ in range(max(1, judge_max_retries)):
        t0 = asyncio.get_running_loop().time()
        try:
            raw, usage = await asyncio.to_thread(
                judge_llm.generate_with_usage,
                prompt,
                judge_temperature,
            )
            last_raw = raw
            elapsed_ms = round((asyncio.get_running_loop().time() - t0) * 1000.0, 3)
            parsed = _extract_json_object(raw)
            if parsed is None:
                last_error = "judge_invalid_json"
                continue

            tc = _judge_bool(parsed, "task_completion")
            dra = _judge_bool(parsed, "data_retrieval_accuracy")
            grv = _judge_bool(parsed, "generalized_result_verification")
            asc = _judge_bool(parsed, "agent_sequence_correct")
            caj = _judge_bool(parsed, "clarity_and_justification")
            hal = _judge_bool(parsed, "hallucinations")
            required = [tc, dra, grv, asc, caj, hal]
            if any(v is None for v in required):
                last_error = "judge_schema_missing_boolean"
                continue

            assert tc is not None
            assert dra is not None
            assert grv is not None
            assert asc is not None
            assert caj is not None
            assert hal is not None

            strict_pass = tc and dra and grv and asc and caj and (not hal)
            score = (int(tc) + int(dra) + int(grv) + int(asc) + int(caj) + int(not hal)) / 6.0

            return {
                "accuracy_judge_has_reference": True,
                "accuracy_judge_valid": True,
                "accuracy_judge_task_completion": tc,
                "accuracy_judge_data_retrieval_accuracy": dra,
                "accuracy_judge_generalized_result_verification": grv,
                "accuracy_judge_agent_sequence_correct": asc,
                "accuracy_judge_clarity_and_justification": caj,
                "accuracy_judge_hallucinations": hal,
                "accuracy_judge_strict_pass": strict_pass,
                "accuracy_judge_score": round(score, 6),
                "accuracy_judge_rationale": str(parsed.get("rationale", "")).strip() or None,
                "accuracy_judge_model_id": judge_model_id,
                "accuracy_judge_ms": elapsed_ms,
                "accuracy_judge_prompt_tokens": usage.prompt_tokens,
                "accuracy_judge_completion_tokens": usage.completion_tokens,
                "accuracy_judge_total_tokens": usage.total_tokens,
                "accuracy_judge_error": None,
                "accuracy_judge_raw_output": raw,
            }
        except Exception as exc:  # pragma: no cover - provider/network runtime variability
            last_error = f"judge_exception: {exc}"

    return {
        "accuracy_judge_has_reference": True,
        "accuracy_judge_valid": False,
        "accuracy_judge_task_completion": None,
        "accuracy_judge_data_retrieval_accuracy": None,
        "accuracy_judge_generalized_result_verification": None,
        "accuracy_judge_agent_sequence_correct": None,
        "accuracy_judge_clarity_and_justification": None,
        "accuracy_judge_hallucinations": None,
        "accuracy_judge_strict_pass": None,
        "accuracy_judge_score": None,
        "accuracy_judge_rationale": None,
        "accuracy_judge_model_id": judge_model_id,
        "accuracy_judge_ms": None,
        "accuracy_judge_prompt_tokens": None,
        "accuracy_judge_completion_tokens": None,
        "accuracy_judge_total_tokens": None,
        "accuracy_judge_error": last_error,
        "accuracy_judge_raw_output": last_raw,
    }


async def _evaluate_accuracy(
    *,
    question: str,
    prediction: str,
    characteristic_form: str | None,
    threshold: float,
    mode: str,
    judge_llm,
    judge_model_id: str,
    judge_temperature: float,
    judge_max_retries: int,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "accuracy_mode": mode,
    }

    heuristic = _accuracy_eval(
        prediction=prediction,
        characteristic_form=characteristic_form,
        threshold=threshold,
    )

    if mode in ("heuristic", "both"):
        out.update(heuristic)

    if mode in ("llm-judge", "both"):
        judge = await _llm_judge_eval(
            question=question,
            prediction=prediction,
            characteristic_form=characteristic_form,
            judge_llm=judge_llm,
            judge_model_id=judge_model_id,
            judge_temperature=judge_temperature,
            judge_max_retries=judge_max_retries,
        )
        out.update(judge)

        # Canonical top-level accuracy fields represent strict judge when enabled.
        out["accuracy_has_reference"] = judge.get("accuracy_judge_has_reference")
        out["accuracy_score"] = judge.get("accuracy_judge_score")
        out["accuracy_pass"] = judge.get("accuracy_judge_strict_pass")
        out["accuracy_threshold"] = None

        # Preserve heuristic details for analysis when running both modes.
        if mode == "both":
            out["accuracy_heuristic_score"] = heuristic.get("accuracy_score")
            out["accuracy_heuristic_pass"] = heuristic.get("accuracy_pass")
            out["accuracy_heuristic_token_f1"] = heuristic.get("accuracy_token_f1")
            out["accuracy_heuristic_keyword_coverage"] = heuristic.get(
                "accuracy_keyword_coverage"
            )
            out["accuracy_heuristic_threshold"] = heuristic.get("accuracy_threshold")

    return out


def _context_metrics_from_record(
    rec: dict[str, Any],
    *,
    context_window_tokens: int,
) -> dict[str, Any]:
    usage = rec.get("token_usage") or {}
    plan = usage.get("plan") or {}
    summarize = usage.get("summarize") or {}
    exec_args = usage.get("execute_arg_resolution") or {}
    totals = usage.get("llm_totals") or {}

    prompt_candidates = [
        plan.get("prompt_tokens"),
        summarize.get("prompt_tokens"),
        exec_args.get("prompt_tokens"),
    ]
    prompt_values = [int(v) for v in prompt_candidates if isinstance(v, int)]
    peak_context = max(prompt_values) if prompt_values else None

    util_pct: float | None = None
    if peak_context is not None and context_window_tokens > 0:
        util_pct = round((peak_context / context_window_tokens) * 100.0, 3)

    approx_context_kib: float | None = None
    if peak_context is not None:
        approx_context_kib = round((peak_context * 4) / 1024.0, 3)

    return {
        "context_peak_prompt_tokens": peak_context,
        "context_window_tokens": context_window_tokens if context_window_tokens > 0 else None,
        "context_window_utilization_pct": util_pct,
        "context_estimated_kib": approx_context_kib,
        "token_total_tokens": totals.get("total_tokens"),
        "token_prompt_tokens": totals.get("prompt_tokens"),
        "token_completion_tokens": totals.get("completion_tokens"),
    }


def _mean_or_none(values: Iterable[float | None]) -> float | None:
    real = [float(v) for v in values if v is not None]
    if not real:
        return None
    return round(mean(real), 6)


def _summarize_run(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(records),
        "success_rate": _mean_or_none(1.0 if r.get("success") else 0.0 for r in records),
        "mean_e2e_ms": _mean_or_none(r.get("e2e_ms") for r in records),
        "mean_accuracy_score": _mean_or_none(r.get("accuracy_score") for r in records),
        "accuracy_pass_rate": _mean_or_none(
            1.0 if r.get("accuracy_pass") is True else 0.0 if r.get("accuracy_pass") is False else None
            for r in records
        ),
        "mean_context_util_pct": _mean_or_none(r.get("context_window_utilization_pct") for r in records),
    }


def _detect_skills_runtime_metadata() -> dict[str, Any]:
    """Inspect active skills server runtime so benchmark rows record implementation flavor."""
    out: dict[str, Any] = {
        "skills_runner_module": None,
        "skills_runner_file": None,
        "skills_markdown_runner_detected": False,
        "skills_markdown_json_plan_detected": False,
        "skills_catalog_md_count": None,
        "skills_runtime_detection_error": None,
    }

    try:
        from servers.skills import runner as skills_runner

        runner_file = Path(getattr(skills_runner, "__file__", "")).resolve()
        out.update(
            {
                "skills_runner_module": "servers.skills.runner",
                "skills_runner_file": str(runner_file),
                "skills_markdown_runner_detected": hasattr(skills_runner, "run_markdown_skill"),
                "skills_markdown_json_plan_detected": hasattr(skills_runner, "_extract_json_plan"),
            }
        )
    except Exception as exc:
        out["skills_runtime_detection_error"] = f"import_runner_failed: {exc}"

    try:
        skills_root = _REPO_ROOT / "src" / "servers" / "skills" / "packs"
        if skills_root.is_dir():
            out["skills_catalog_md_count"] = sum(1 for _ in skills_root.rglob("SKILL.md"))
    except Exception as exc:
        if out["skills_runtime_detection_error"]:
            out["skills_runtime_detection_error"] = (
                f"{out['skills_runtime_detection_error']}; md_scan_failed: {exc}"
            )
        else:
            out["skills_runtime_detection_error"] = f"md_scan_failed: {exc}"

    return out


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--runner-mode",
        choices=("kp", "rag"),
        default="kp",
        help=(
            "Execution strategy to benchmark: kp=Knowledge Plugin mode "
            "(plan-execute orchestration), rag=traditional retrieval+LLM generation."
        ),
    )
    p.add_argument(
        "--scenarios",
        type=Path,
        default=_REPO_ROOT / "src/scenarios/local/vibration_utterance.json",
        help="Scenario JSON array (id, type, text, ...).",
    )
    p.add_argument(
        "--source",
        choices=("local", "hf"),
        default="local",
        help="Scenario source: local JSON file or Hugging Face dataset.",
    )
    p.add_argument(
        "--hf-dataset-name",
        default="ibm-research/AssetOpsBench",
        help="Hugging Face dataset id (used when --source hf).",
    )
    p.add_argument(
        "--hf-config",
        default="",
        help="Optional HF dataset config/subset name.",
    )
    p.add_argument(
        "--no-skills-mcp",
        action="store_true",
        help="Remove the skills MCP server from the agent's available tools.",
    )
    p.add_argument(
        "--hf-split",
        default="train",
        help="HF split to use (train/test/validation/etc.).",
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
        "--synthetic-copies",
        type=int,
        default=0,
        help="Number of synthetic variants to create per scenario (0 = disabled).",
    )
    p.add_argument(
        "--synthetic-seed",
        type=int,
        default=17,
        help="Seed for deterministic synthetic scenario generation.",
    )
    p.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Run only synthetic variants (exclude original scenarios).",
    )
    p.add_argument(
        "--context-window-tokens",
        type=int,
        default=0,
        help=(
            "Model context-window size for utilization percentage. "
            "0 disables utilization calculation."
        ),
    )
    p.add_argument(
        "--accuracy-threshold",
        type=float,
        default=0.55,
        help="Pass threshold for heuristic accuracy score [0, 1].",
    )
    p.add_argument(
        "--accuracy-mode",
        choices=("heuristic", "llm-judge", "both"),
        default="llm-judge",
        help=(
            "Accuracy path: heuristic lexical score, strict llm rubric judge, "
            "or both."
        ),
    )
    p.add_argument(
        "--judge-model-id",
        default="watsonx/ibm/granite-3-8b-instruct",
        help="Model id used by strict llm-judge accuracy path.",
    )
    p.add_argument(
        "--judge-temperature",
        type=float,
        default=0.0,
        help="Temperature for llm-judge scoring calls.",
    )
    p.add_argument(
        "--judge-max-retries",
        type=int,
        default=2,
        help="Max retries for invalid/non-JSON llm-judge output.",
    )
    p.add_argument(
        "--shuffle-seed",
        type=int,
        default=0,
        help="If >0, shuffle scenarios with this seed before applying --limit.",
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
    scenario_row: dict[str, Any],
    model_id: str,
    scenario_id: int | None,
    scenario_type: str | None,
    output: Path,
    repo_root: Path,
    context_window_tokens: int,
    accuracy_threshold: float,
    accuracy_mode: str,
    judge_llm,
    judge_model_id: str,
    judge_temperature: float,
    judge_max_retries: int,
    wandb_batch,
    runner_mode: str,
    skills_runtime_meta: dict[str, Any],
) -> dict[str, Any]:
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
        rec.update(
            {
                "scenario_category": scenario_row.get("category"),
                "scenario_source": scenario_row.get("scenario_source"),
                "synthetic": bool(scenario_row.get("synthetic", False)),
                "synthetic_parent_id": scenario_row.get("synthetic_parent_id"),
                "characteristic_form": scenario_row.get("characteristic_form"),
                "candidate_answer": result.answer,
                "runner_mode": runner_mode,
            }
        )
        rec.update(skills_runtime_meta)
        rec.update(
            await _evaluate_accuracy(
                question=result.question,
                prediction=result.answer,
                characteristic_form=scenario_row.get("characteristic_form"),
                threshold=accuracy_threshold,
                mode=accuracy_mode,
                judge_llm=judge_llm,
                judge_model_id=judge_model_id,
                judge_temperature=judge_temperature,
                judge_max_retries=judge_max_retries,
            )
        )
        rec.update(
            _context_metrics_from_record(
                rec,
                context_window_tokens=context_window_tokens,
            )
        )
        append_jsonl(output, rec)
        wandb_batch.log_record(rec)
        return rec
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
        rec.update(
            {
                "scenario_category": scenario_row.get("category"),
                "scenario_source": scenario_row.get("scenario_source"),
                "synthetic": bool(scenario_row.get("synthetic", False)),
                "synthetic_parent_id": scenario_row.get("synthetic_parent_id"),
                "characteristic_form": scenario_row.get("characteristic_form"),
                "candidate_answer": None,
                "runner_mode": runner_mode,
            }
        )
        rec.update(skills_runtime_meta)
        rec.update(
            await _evaluate_accuracy(
                question=text,
                prediction="",
                characteristic_form=scenario_row.get("characteristic_form"),
                threshold=accuracy_threshold,
                mode=accuracy_mode,
                judge_llm=judge_llm,
                judge_model_id=judge_model_id,
                judge_temperature=judge_temperature,
                judge_max_retries=judge_max_retries,
            )
        )
        rec.update(
            _context_metrics_from_record(
                rec,
                context_window_tokens=context_window_tokens,
            )
        )
        append_jsonl(output, rec)
        wandb_batch.log_record(rec)
        return rec


async def _amain() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    args = _build_parser().parse_args()
    from agent.plan_execute.rag_runner import RAGRunner
    from agent.plan_execute.runner import PlanExecuteRunner
    from agent.plan_execute.executor import DEFAULT_SERVER_PATHS
    from llm.litellm import LiteLLMBackend

    if args.source == "hf":
        scenarios = _load_hf_scenarios(
            dataset_name=args.hf_dataset_name,
            split=args.hf_split,
            dataset_config=args.hf_config or None,
        )
        scenario_source_label = "hf"
    else:
        scenarios = _load_scenarios(args.scenarios)
        scenario_source_label = "local"

    scenarios = [
        _normalize_scenario_row(row, source=scenario_source_label)
        for row in scenarios
    ]

    id_filter: set[int] | None = None
    if args.ids.strip():
        id_filter = {int(x.strip()) for x in args.ids.split(",") if x.strip()}
        scenarios = [
            s
            for s in scenarios
            if _safe_int(s.get("id")) is not None
            and int(s["id"]) in id_filter
        ]

    scenarios = _expand_synthetic_rows(
        scenarios,
        synthetic_copies=args.synthetic_copies,
        synthetic_seed=args.synthetic_seed,
        synthetic_only=args.synthetic_only,
    )

    if args.shuffle_seed > 0:
        random.Random(args.shuffle_seed).shuffle(scenarios)

    if args.limit > 0:
        scenarios = scenarios[: args.limit]

    if not scenarios:
        raise ValueError("No scenarios selected after filtering/limits.")

    llm = LiteLLMBackend(model_id=args.model_id)
    judge_llm = llm
    if args.accuracy_mode in ("llm-judge", "both"):
        judge_llm = LiteLLMBackend(model_id=args.judge_model_id)

    server_paths = None
    if args.no_skills_mcp:
        server_paths = {
            name: path
            for name, path in DEFAULT_SERVER_PATHS.items()
            if name != "skills"
        }

    if args.runner_mode == "rag":
        runner = RAGRunner(llm=llm)
    else:
        runner = PlanExecuteRunner(llm=llm, server_paths=server_paths)

    skills_runtime_meta = _detect_skills_runtime_metadata()
    skills_runtime_meta["skills_mcp_enabled_for_run"] = not args.no_skills_mcp

    from observability.benchmark_wandb import WandbBenchmarkBatch

    suite_config = {
        "suite_file": str(args.scenarios),
        "source": args.source,
        "hf_dataset_name": args.hf_dataset_name if args.source == "hf" else None,
        "hf_config": args.hf_config if args.source == "hf" else None,
        "hf_split": args.hf_split if args.source == "hf" else None,
        "synthetic_copies": args.synthetic_copies,
        "synthetic_only": args.synthetic_only,
        "context_window_tokens": args.context_window_tokens,
        "accuracy_threshold": args.accuracy_threshold,
        "accuracy_mode": args.accuracy_mode,
        "runner_mode": args.runner_mode,
        "judge_model_id": args.judge_model_id,
        "judge_temperature": args.judge_temperature,
        "judge_max_retries": args.judge_max_retries,
        "model_id": args.model_id,
        "jsonl_output": str(args.output),
    }
    records: list[dict[str, Any]] = []
    with WandbBenchmarkBatch(base_config=suite_config) as wb:
        for row in scenarios:
            sid = _safe_int(row.get("id"))
            stype = str(row.get("type", ""))
            text = str(row["text"])
            rec = await _run_one(
                runner,
                text,
                scenario_row=row,
                model_id=args.model_id,
                scenario_id=sid,
                scenario_type=stype,
                output=args.output,
                repo_root=args.repo_root,
                context_window_tokens=args.context_window_tokens,
                accuracy_threshold=args.accuracy_threshold,
                accuracy_mode=args.accuracy_mode,
                judge_llm=judge_llm,
                judge_model_id=args.judge_model_id,
                judge_temperature=args.judge_temperature,
                judge_max_retries=args.judge_max_retries,
                wandb_batch=wb,
                runner_mode=args.runner_mode,
                skills_runtime_meta=skills_runtime_meta,
            )
            records.append(rec)

    summary = _summarize_run(records)
    _log.info("Benchmark summary: %s", json.dumps(summary, sort_keys=True))
    try:
        # Map the JSONL output filename to an HTML filename under repo_root/dashboards
        out_name = args.output.name
        if out_name.lower().endswith('.jsonl'):
            out_name = out_name[: -len('.jsonl')] + '.html'
        else:
            out_name = out_name + '.html'
        dashboard_path = args.repo_root / "dashboards" / out_name
        jsonl_text = args.output.read_text(encoding="utf-8")
        render_dashboard(
            jsonl_text,
            dashboard_path,
            title=f"Benchmark: {args.output.name}",
            data_href=f"runs/{args.output.name}",
            data_name=args.output.name,
        )
        _log.info("Wrote static dashboard: %s", str(dashboard_path))
    except Exception:
        _log.exception("Failed to generate dashboard")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
