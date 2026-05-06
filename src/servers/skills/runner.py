# Markdown Runner
from __future__ import annotations

import json
from typing import Any

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
    plan = _extract_json_plan(rec.instructions)
    pool = get_sibling_pool()

    steps: list[SkillStepResult] = []

    for step in plan.get("steps", []):
        name = step["name"]
        server = step["server"]
        tool = step["tool"]
        raw_args = step.get("arguments", {})
        resolved_args = _substitute_args(raw_args, arguments)

        try:
            text = await pool.call_tool(server, tool, resolved_args)
            detail = _safe_json(text)
            steps.append(SkillStepResult(name=name, ok=True, detail=detail))
        except Exception as exc:
            steps.append(
                SkillStepResult(
                    name=name,
                    ok=False,
                    detail={"error": str(exc)},
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


def _substitute_args(value: Any, runtime_args: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        return runtime_args.get(value[1:])
    if isinstance(value, dict):
        return {k: _substitute_args(v, runtime_args) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_args(v, runtime_args) for v in value]
    return value


def _safe_json(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except Exception:
        return {"text": text}