"""LLM-based plan generation for the plan-execute orchestrator.

Each plan step now includes the specific tool to call and its arguments,
so the executor needs no additional LLM calls — it calls the tool directly.
"""

from __future__ import annotations

import logging
import re
import json

from llm import LLMBackend
from llm.usage import CompletionUsage
from .models import Plan, PlanStep

_log = logging.getLogger(__name__)

_PLAN_PROMPT = """\
You are a planning assistant for industrial asset operations and maintenance.

Decompose the question below into a sequence of subtasks. For each subtask,
assign a server and select the exact tool to call. Do NOT include tool arguments —
they will be resolved at execution time from the task description and prior results.

Available servers and tools:
{servers}

Valid #ServerN values — you MUST use exactly one of these names on every step (copy the spelling): {valid_servers}
Never leave #ServerN blank. Never use "none", "null", or free text as the server name. The word "none" is ONLY valid for #ToolN when no MCP tool is needed.
Only use the ``skills`` server if it appears in the available servers list above.

Output format — one block per step, exactly:

#Task1: <task description>
#Server1: <exact server name from the list above>
#Tool1: <exact tool name, or "none" if no tool call is needed>
#Arguments1: <raw JSON object, or {{}}>
#Dependency1: None
#ExpectedOutput1: <what this step should produce>

#Task2: <task description>
#Server2: <exact server name from the list above>
#Tool2: <exact tool name>
#Arguments1: <raw JSON object, or {{}}>
#Dependency2: #S1
#ExpectedOutput2: <what this step should produce>

Rules:
- #ServerN must be one of: {valid_servers}
- #ToolN must exactly match a tool listed under that server, or be the literal none (no quotes in the server line).
- #ArgumentsN must be valid raw JSON. For no-arg tools, use {{}}.
- For skills.run_skill, use {{"skill_id":"pack/skill","arguments":{{...}}}}.
- Dependencies use #S<N> notation (e.g., #S1, #S2). Use "None" if none.
- Keep tasks specific and actionable.
{skills_rule}
Question: {question}

Plan:
"""

_SKILLS_SERVER_RULES = """\
- On server ``skills``, tool ``run_skill`` takes JSON arguments ``skill_id`` and
  ``arguments`` (object). ``skill_id`` MUST be the **full FQID** exactly as in
  the skills list: ``pack_id/skill_id`` (e.g. ``assetopsbench_demo/safety_clearance_check``).
  Never pass only the short suffix (e.g. ``safety_clearance_check`` alone).
- Pump seal / mechanical seal maintenance:
  ``skill_id`` ``assetopsbench/pump_seal_inspection``;
  ``arguments``: ``site_name``, ``asset_id``, ``asset_name`` (if only one tag like PUMP1 is known, use it for both ``asset_id`` and ``asset_name``).
- Safety clearance / readiness checks:
  ``skill_id`` ``assetopsbench_demo/safety_clearance_check``;
  ``arguments``: ``site_name``, ``asset_id``.
- Diagnostics / failure-mode sensor mapping bundle:
  ``skill_id`` ``assetopsbench_demo/asset_diagnostics_bundle``;
  ``arguments``: ``site_name``, ``asset_id``, ``asset_name``.
- If ``skills`` is not in the server list, use iot / fmsr / wo as needed instead.
"""

_TASK_RE = re.compile(r"#Task(\d+):\s*(.+)")
_SERVER_RE = re.compile(r"#Server(\d+):\s*(.+)")
_TOOL_RE = re.compile(r"#Tool(\d+):\s*(.+)")
_DEP_RE = re.compile(r"#Dependency(\d+):\s*(.+)")
_OUTPUT_RE = re.compile(r"#ExpectedOutput(\d+):\s*(.+)")
_DEP_NUM_RE = re.compile(r"#S(\d+)")
_ARGS_RE = re.compile(r"#Arguments(\d+):\s*(.+)")


def _parse_dependency_numbers(raw_dep: str) -> list[int]:
    """Parse dependency references from planner output.

    Accepts canonical ``#S1`` and tolerant fallbacks like ``#T1`` or ``1``.
    """
    # Canonical notation expected by prompt.
    deps = [int(x) for x in re.findall(r"#S(\d+)", raw_dep, flags=re.IGNORECASE)]
    if deps:
        return deps

    # Some models emit #T1 for task references; treat as equivalent.
    deps = [int(x) for x in re.findall(r"#T(\d+)", raw_dep, flags=re.IGNORECASE)]
    if deps:
        return deps

    # Final fallback: bare numbers (e.g. "1,2").
    if re.fullmatch(r"[\d\s,;]+", raw_dep):
        nums = [s for s in re.split(r"[\s,;]+", raw_dep) if s.strip()]
        return [int(s) for s in nums]

    return []


def parse_plan(raw: str) -> Plan:
    """Parse an LLM-generated plan string into a Plan object."""
    tasks = {int(m.group(1)): m.group(2).strip() for m in _TASK_RE.finditer(raw)}
    servers = {int(m.group(1)): m.group(2).strip() for m in _SERVER_RE.finditer(raw)}
    # Strip any trailing signature the LLM may copy from the server description
    # format "tool_name(param: type)" — only the bare name is needed.
    tools = {
        int(m.group(1)): m.group(2).strip().split("(")[0].strip()
        for m in _TOOL_RE.finditer(raw)
    }
    args_raw = {
        int(m.group(1)): m.group(2).strip()
        for m in _ARGS_RE.finditer(raw)
    }
    deps_raw = {int(m.group(1)): m.group(2).strip() for m in _DEP_RE.finditer(raw)}
    outputs = {int(m.group(1)): m.group(2).strip() for m in _OUTPUT_RE.finditer(raw)}

    steps = []
    for n in sorted(tasks):
        raw_dep = deps_raw.get(n, "None").strip()

        if raw_dep.lower() == "none":
            dependencies = []
        else:
            dependencies = _parse_dependency_numbers(raw_dep)

            # Make sure dependency references only point to earlier valid steps.
            if not dependencies:
                raise ValueError(f"Invalid dependency format for step {n}: {raw_dep}")

            for dep in dependencies:
                if dep < 1 or dep >= n:
                    raise ValueError(
                        f"Invalid dependency reference for step {n}: #S{dep}"
                    )
        try:
            tool_args = json.loads(args_raw.get(n, "{}"))
            if not isinstance(tool_args, dict):
                tool_args = {}
        except json.JSONDecodeError:
            tool_args = {}

        steps.append(
            PlanStep(
                step_number=n,
                task=tasks[n],
                server=servers.get(n, ""),
                tool=tools.get(n, ""),
                tool_args=tool_args,
                dependencies=dependencies,
                expected_output=outputs.get(n, ""),
            )
        )

    return Plan(steps=steps, raw=raw)


class Planner:
    """Decomposes a question into a structured execution plan using an LLM."""

    def __init__(self, llm: LLMBackend) -> None:
        self._llm = llm

    def generate_plan(
        self,
        question: str,
        server_descriptions: dict[str, str],
    ) -> tuple[Plan, CompletionUsage]:
        """Generate a plan for a question given available servers and their tools.

        Args:
            question: The user question to answer.
            server_descriptions: Mapping of server_name -> formatted tool signatures.

        Returns:
            The parsed :class:`~.models.Plan` and token usage for the planning LLM
            call (may be all-``None`` if the backend does not report usage).
        """
        servers_text = "\n\n".join(
            f"{name}:\n{desc}" for name, desc in server_descriptions.items()
        )
        valid_servers = ", ".join(sorted(server_descriptions.keys()))
        skills_rule = (
            _SKILLS_SERVER_RULES if "skills" in server_descriptions else ""
        )
        prompt = _PLAN_PROMPT.format(
            servers=servers_text,
            question=question,
            valid_servers=valid_servers,
            skills_rule=skills_rule,
        )
        raw, usage = self._llm.generate_with_usage(prompt)
        return parse_plan(raw), usage