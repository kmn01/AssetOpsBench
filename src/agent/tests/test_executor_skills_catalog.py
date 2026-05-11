"""Tests for planner skills catalog fetch in Executor."""

from __future__ import annotations

import json

import pytest

from agent.plan_execute.executor import Executor
from llm import LLMBackend


class _NoopLLM(LLMBackend):
    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        return ""


_INSTRUCTIONS = """\
---
inputs:
  site_name:
    type: string
    required: true
  asset_id:
    type: string
    required: true
---
```json
{"steps": []}
```
"""


@pytest.mark.anyio
async def test_fetch_planner_skills_catalog_builds_minimal_rows(monkeypatch):
    async def fake_call_tool(
        server_path, tool_name: str, args: dict
    ) -> str:
        if tool_name == "list_skills":
            return json.dumps(
                {
                    "skills": [
                        {
                            "fqid": "demo/skill_one",
                            "description": "Test skill",
                            "runnable": True,
                            "asset_types": ["pump"],
                        },
                        {
                            "fqid": "demo/skill_skip",
                            "description": "Not runnable",
                            "runnable": False,
                        },
                    ]
                }
            )
        if tool_name == "get_skill_manifest":
            return json.dumps(
                {
                    "fqid": args.get("skill_id"),
                    "instructions": _INSTRUCTIONS,
                }
            )
        return "{}"

    monkeypatch.setattr(
        "agent.plan_execute.executor._call_tool",
        fake_call_tool,
    )
    ex = Executor(_NoopLLM(), server_paths={"skills": "skills-mcp-server"})
    rows = await ex.fetch_planner_skills_catalog()
    assert len(rows) == 1
    assert rows[0]["fqid"] == "demo/skill_one"
    assert rows[0]["description"] == "Test skill"
    assert set(rows[0]["required_args"]) == {"asset_id", "site_name"}
    assert rows[0]["asset_types"] == ["pump"]


@pytest.mark.anyio
async def test_fetch_planner_skills_catalog_empty_without_skills_server():
    ex = Executor(_NoopLLM(), server_paths={"iot": "iot-mcp-server"})
    rows = await ex.fetch_planner_skills_catalog()
    assert rows == []
