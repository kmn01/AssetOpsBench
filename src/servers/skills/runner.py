# Markdown Runner
from __future__ import annotations

import json
from typing import Any

import yaml

from .registry import coerce_skill_fqid, load_skill_catalog, read_installed_fqids, parse_enabled_skills_allowlist
from .registry import _runnable
from .results import SkillInvocationError, SkillRunResult, SkillStepResult
from .sibling_mcp import get_sibling_pool


def _find_skill(fqid: str):
    catalog = load_skill_catalog()
    target = coerce_skill_fqid(fqid, catalog)
    for rec in catalog:
        if rec.fqid == target:
            return rec
    return None


async def run_skill_impl(skill_id: str, arguments: dict[str, Any]) -> SkillRunResult | SkillInvocationError:
    rec = _find_skill(skill_id)
    if rec is None:
        return SkillInvocationError(error=f"unknown skill: {skill_id!r}")

    installed = rec.fqid in read_installed_fqids()
    env_allow = parse_enabled_skills_allowlist()

    if not installed:
        return SkillInvocationError(error=f"skill is not installed: {rec.fqid}")

    if not _runnable(
        rec.fqid,
        default_enabled=rec.default_enabled,
        installed=installed,
        env_allow=env_allow,
    ):
        return SkillInvocationError(error=f"skill is not runnable: {rec.fqid}")

    if not rec.instructions:
        return SkillInvocationError(
            error=f"skill {rec.fqid} has no SKILL.md instructions"
        )

    return await run_markdown_skill(rec, arguments)


async def run_markdown_skill(rec, arguments: dict[str, Any]) -> SkillRunResult:
    """
    Minimal Markdown-driven implementation.

    The SKILL.md file declares a simple JSON plan under a fenced block:

    ```json
    {
      "steps": [
        {
          "name": "iot_sensors",
          "server": "iot",
          "tool": "sensors",
          "arguments": {
            "site_name": "$site_name",
            "asset_id": "$asset_id"
          }
        }
      ]
    }
    ```
    """
    validation_error = _validate_required_inputs(rec.instructions, arguments)
    if validation_error:
        return SkillInvocationError(error=validation_error)

    plan = _extract_json_plan(rec.instructions)
    pool = get_sibling_pool()

    steps: list[SkillStepResult] = []
    step_outputs: dict[str, dict[str, Any]] = {}

    for step in plan.get("steps", []):
        name = step["name"]
        server = step["server"]
        tool = step["tool"]
        raw_args = step.get("arguments", {})
        resolved_args = _substitute_args(raw_args, arguments, step_outputs)

        try:
            text = await pool.call_tool(server, tool, resolved_args)
            detail = _safe_json(text)
            step_outputs[name] = detail
            steps.append(
                SkillStepResult(name=name, ok=not _has_error(detail), detail=detail)
            )
        except Exception as exc:
            detail = {"error": str(exc)}
            step_outputs[name] = detail
            steps.append(
                SkillStepResult(
                    name=name,
                    ok=False,
                    detail=detail,
                )
            )

    return SkillRunResult(
        skill_id=rec.fqid,
        overall_ok=all(s.ok for s in steps),
        steps=steps,
    )


def _extract_json_plan(markdown: str) -> dict[str, Any]:
    start = markdown.find("```json")
    if start == -1:
        raise ValueError("SKILL.md must contain a fenced ```json skill plan")

    start = markdown.find("\n", start) + 1
    end = markdown.find("```", start)

    if end == -1:
        raise ValueError("SKILL.md json block is not closed")

    return json.loads(markdown[start:end].strip())


def _validate_required_inputs(
    markdown: str,
    runtime_args: dict[str, Any],
) -> str | None:
    inputs = _frontmatter_inputs(markdown)
    if not inputs:
        return None
    missing = []
    for name, spec in inputs.items():
        if not isinstance(spec, dict) or spec.get("required") is not True:
            continue
        value = _lookup_runtime_arg(str(name), runtime_args)
        if value in (None, ""):
            missing.append(str(name))
    if missing:
        return f"missing required skill arguments: {', '.join(sorted(missing))}"
    return None


def _frontmatter_inputs(markdown: str) -> dict[str, Any]:
    if not markdown.startswith("---"):
        return {}
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        frontmatter = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
    if not isinstance(frontmatter, dict):
        return {}
    inputs = frontmatter.get("inputs")
    return inputs if isinstance(inputs, dict) else {}


def _substitute_args(
    value: Any,
    runtime_args: dict[str, Any],
    step_outputs: dict[str, dict[str, Any]] | None = None,
) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        return _resolve_placeholder(value[1:], runtime_args, step_outputs or {})
    if isinstance(value, dict):
        resolved = {}
        for k, v in value.items():
            item = _substitute_args(v, runtime_args, step_outputs)
            if item is not None:
                resolved[k] = item
        return resolved
    if isinstance(value, list):
        return [_substitute_args(v, runtime_args, step_outputs) for v in value]
    return value


def _resolve_placeholder(
    ref: str,
    runtime_args: dict[str, Any],
    step_outputs: dict[str, dict[str, Any]],
) -> Any:
    runtime_value = _lookup_runtime_arg(ref, runtime_args)
    if runtime_value is not None:
        return runtime_value

    head, *path = ref.split(".")
    current: Any = step_outputs.get(head)
    for part in path:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _lookup_runtime_arg(ref: str, runtime_args: dict[str, Any]) -> Any:
    if ref in runtime_args:
        return runtime_args.get(ref)
    aliases = {
        "site_name": ("site",),
        "asset_id": ("asset", "equipment_id"),
        "asset_name": ("asset_id", "asset", "equipment_id"),
        "equipment_id": ("asset_id", "asset"),
    }
    for alias in aliases.get(ref, ()):
        value = runtime_args.get(alias)
        if value is not None:
            return value
    return None


def _has_error(detail: dict[str, Any]) -> bool:
    return bool(detail.get("error"))


def _safe_json(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except Exception:
        return {"text": text}