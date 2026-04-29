#!/usr/bin/env python3
"""Build static evaluation dashboard HTML from arbitrary JSONL inputs.

This utility keeps the existing dashboard layout/JS and only replaces the
embedded ``jsonlData`` block, so users can regenerate dashboards from new runs
without manual copy-paste edits.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE = REPO_ROOT / "eval_dashboard_llm_judge_4_23_26_pump_baseline.html"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--inputs",
        type=Path,
        nargs="+",
        required=True,
        help="Input JSONL files to merge into dashboard data.",
    )
    p.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help="Template dashboard HTML that contains const jsonlData = `...`.",
    )
    p.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output dashboard HTML path.",
    )
    p.add_argument(
        "--dedupe",
        choices=("none", "scenario-runner-question"),
        default="scenario-runner-question",
        help="Dedupe key strategy for merged rows.",
    )
    return p


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{idx}: invalid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{path}:{idx}: expected JSON object per line")
        rows.append(parsed)
    return rows


def _dedupe_rows(rows: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode == "none":
        return rows

    if mode != "scenario-runner-question":
        raise ValueError(f"Unsupported dedupe mode: {mode}")

    keyed: dict[tuple[str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str]] = []

    for row in rows:
        scenario = str(row.get("scenario_id", ""))
        runner = str(row.get("runner_mode") or "kp").lower()
        question = str(row.get("question") or "")
        key = (scenario, runner, question)
        if key not in keyed:
            order.append(key)
        keyed[key] = row

    return [keyed[k] for k in order]


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _key(row: dict[str, Any]) -> tuple[int, str, str]:
        try:
            sid = int(row.get("scenario_id"))
        except Exception:
            sid = 10**9
        runner = str(row.get("runner_mode") or "kp").lower()
        q = str(row.get("question") or "")
        return sid, runner, q

    return sorted(rows, key=_key)


def _replace_jsonl_block(template_html: str, jsonl_blob: str) -> str:
    pattern = re.compile(r"const jsonlData = `.*?`;", flags=re.DOTALL)
    replacement = f"const jsonlData = {json.dumps(jsonl_blob)};"
    updated, count = pattern.subn(lambda _: replacement, template_html, count=1)
    if count != 1:
        raise ValueError("Template missing expected `const jsonlData = `...`;` block")
    return updated


def _replace_data_source_label(html: str, inputs: list[Path]) -> str:
    source_names = ", ".join(p.name for p in inputs)
    replacement = (
        '<div class="source">\n'
        f"            Data source: generated from {len(inputs)} JSONL file(s) ({source_names})\n"
        "        </div>"
    )
    pattern = re.compile(r"<div class=\"source\">.*?</div>", flags=re.DOTALL)
    updated, count = pattern.subn(replacement, html, count=1)
    if count != 1:
        return html
    return updated


def main() -> None:
    args = _build_parser().parse_args()

    template_path = args.template.resolve()
    output_path = args.output.resolve()
    input_paths = [p.resolve() for p in args.inputs]

    all_rows: list[dict[str, Any]] = []
    for path in input_paths:
        if not path.is_file():
            raise FileNotFoundError(f"Input JSONL does not exist: {path}")
        all_rows.extend(_load_jsonl(path))

    rows = _dedupe_rows(all_rows, args.dedupe)
    rows = _sort_rows(rows)
    jsonl_blob = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)

    template_html = template_path.read_text(encoding="utf-8")
    html = _replace_jsonl_block(template_html, jsonl_blob)
    html = _replace_data_source_label(html, input_paths)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"Wrote dashboard: {output_path}")
    print(f"Merged rows: {len(all_rows)} | Output rows: {len(rows)}")


if __name__ == "__main__":
    main()