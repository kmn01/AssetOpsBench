"""Minimal planner-facing skill metadata derived from SKILL.md instructions."""

from __future__ import annotations

import json
import re
from typing import Any

import yaml

_VAR_RE = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)")


def _split_yaml_frontmatter(markdown: str) -> tuple[dict[str, Any] | None, str]:
    if not markdown.startswith("---"):
        return None, markdown
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return None, markdown
    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None, markdown
    return (fm if isinstance(fm, dict) else None), parts[2]


def _required_args_from_inputs_block(inputs: dict[str, Any]) -> list[str] | None:
    """Return sorted required arg names, or None if block absent / unusable."""
    if not isinstance(inputs, dict) or not inputs:
        return None
    required: list[str] = []
    for name, spec in inputs.items():
        if not isinstance(spec, dict):
            continue
        if spec.get("required") is True:
            required.append(str(name))
    return sorted(required)


def _required_args_from_json_plan(markdown: str) -> list[str]:
    start = markdown.find("```json")
    if start == -1:
        return []
    start = markdown.find("\n", start) + 1
    end = markdown.find("```", start)
    if end == -1:
        return []
    try:
        plan = json.loads(markdown[start:end].strip())
    except json.JSONDecodeError:
        return []
    steps = plan.get("steps") or []
    if not isinstance(steps, list):
        return []
    step_names: set[str] = set()
    for s in steps:
        if isinstance(s, dict) and s.get("name"):
            step_names.add(str(s["name"]))
    blob = json.dumps(plan)
    vars_found = set(_VAR_RE.findall(blob))
    runtime = sorted(v for v in vars_found if v not in step_names)
    return runtime


def extract_required_args_from_skill_instructions(instructions: str) -> list[str]:
    """Prefer YAML ``inputs`` with ``required: true``; else JSON plan ``$var`` refs."""
    fm, _ = _split_yaml_frontmatter(instructions)
    if fm:
        inputs = fm.get("inputs")
        if isinstance(inputs, dict) and inputs:
            req = _required_args_from_inputs_block(inputs)
            if req is not None:
                return req
    return _required_args_from_json_plan(instructions)


def build_planner_skill_entry(
    *,
    fqid: str,
    description: str,
    instructions: str | None,
    asset_types: list[str] | None,
) -> dict[str, Any]:
    """One minimal row for the planner / run_skill arg-resolution prompts."""
    entry: dict[str, Any] = {
        "fqid": fqid,
        "description": (description or "").strip(),
        "required_args": extract_required_args_from_skill_instructions(
            instructions or ""
        ),
    }
    if asset_types:
        entry["asset_types"] = list(asset_types)
    return entry
