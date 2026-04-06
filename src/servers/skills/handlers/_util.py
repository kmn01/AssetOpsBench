"""Helpers for sibling MCP JSON and step records."""

from __future__ import annotations

import json
from typing import Any

from ..results import SkillStepResult


def parse_mcp_json(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return {"_scalar": data}
    except json.JSONDecodeError:
        return {
            "error": "invalid_json_from_sibling",
            "raw_excerpt": text[:400],
        }


def detail_ok(d: dict[str, Any]) -> bool:
    err = d.get("error")
    if err is None:
        return True
    if isinstance(err, str) and err.strip() == "":
        return True
    return False


async def mcp_step(
    pool,
    *,
    name: str,
    server: str,
    tool: str,
    arguments: dict[str, Any],
) -> SkillStepResult:
    try:
        text = await pool.call_tool(server, tool, arguments)
    except TimeoutError:
        return SkillStepResult(
            name=name, ok=False, detail={"error": "mcp_call_timeout"}
        )
    except Exception as exc:  # noqa: BLE001 — boundary from MCP client
        return SkillStepResult(name=name, ok=False, detail={"error": str(exc)})
    detail = parse_mcp_json(text)
    return SkillStepResult(name=name, ok=detail_ok(detail), detail=detail)
