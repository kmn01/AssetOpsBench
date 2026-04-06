"""MCP-based step executor for the plan-execute orchestrator.

The planner produces steps with no pre-filled arguments. For every step that
calls a tool the executor makes one LLM call to generate the concrete argument
dict from the task description, original question, and prior step results.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import anyio

from llm import LLMBackend
from servers.common.mcp_stdio import make_stdio_params

from .models import Plan, PlanStep, StepResult

_log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent.parent

# Composed skills (e.g. FMSR FM×sensor mapping) can run many sequential LLM calls.
_MCP_CLIENT_TIMEOUT_SEC = float(os.environ.get("MCP_CLIENT_TIMEOUT_SEC", "600"))

# Arg-resolution uses sync llm.generate(); run it in a thread and bound wall time
# so a hung provider does not freeze the asyncio loop indefinitely.
_ARG_RESOLUTION_LLM_TIMEOUT_SEC = float(
    os.environ.get("PLAN_EXECUTE_ARG_LLM_TIMEOUT_SEC", "180")
)

# Maps agent names to either a uv entry-point name (str) or a script Path.
# Entry-point names are invoked as ``uv run <name>``; Paths fall back to
# ``python -m module.path`` (supports relative imports).
DEFAULT_SERVER_PATHS: dict[str, Path | str] = {
    "iot": "iot-mcp-server",
    "utilities": "utilities-mcp-server",
    "fmsr": "fmsr-mcp-server",
    "tsfm": "tsfm-mcp-server",
    "wo": "wo-mcp-server",
    "vibration": "vibration-mcp-server",
    "skills": "skills-mcp-server",
}

_PLACEHOLDER_RE = re.compile(r"\{step_(\d+)\}")

_ARG_RESOLUTION_PROMPT = """\
Generate the JSON arguments for the tool call below.

Question: {question}
Tool: {tool}
Tool parameters: {tool_schema}
Task: {task}

Prior step results:
{context}

YOUR RESPONSE MUST BE A SINGLE RAW JSON OBJECT AND NOTHING ELSE.
Do not write any explanation, reasoning, or prose — output only the JSON object.
Use EXACTLY the parameter names listed in "Tool parameters" above.
Use the task description and prior step results to determine the correct argument values.
If a value comes from a list, use the first relevant element.

JSON:"""

# MCP lists ``arguments`` as an opaque object; spell out nested keys for the LLM.
_RUN_SKILL_ARGS_HINT = """

Extra rules for tool ``run_skill`` (skills server):
- Output MUST be a JSON object with exactly two top-level keys: ``skill_id`` (string) and ``arguments`` (object). Do not flatten skill fields to the top level.
- Nested keys belong inside ``arguments`` only.

Required ``arguments`` by ``skill_id``:
- ``assetopsbench/pump_seal_inspection``: ``site_name``, ``asset_id``, ``asset_name``. If the user names one pump token (e.g. PUMP1), use that value for both ``asset_id`` and ``asset_name`` unless prior steps give distinct values.
- ``assetopsbench_demo/safety_clearance_check``: ``site_name``, ``asset_id``
- ``assetopsbench_demo/asset_diagnostics_bundle``: ``site_name``, ``asset_id``, ``asset_name`` (same single-token rule as pump when applicable).
"""


class Executor:
    """Executes plan steps by routing tool calls to MCP servers."""

    def __init__(
        self,
        llm: LLMBackend,
        server_paths: dict[str, Path | str] | None = None,
    ) -> None:
        self._llm = llm
        self._server_paths = (
            DEFAULT_SERVER_PATHS if server_paths is None else server_paths
        )

    async def get_server_descriptions(self) -> dict[str, str]:
        """Query each registered MCP server and return formatted tool signatures."""
        descriptions: dict[str, str] = {}
        for name, path in self._server_paths.items():
            _log.info("Listing tools from server %r ...", name)
            try:
                tools = await _list_tools(path)
                lines = []
                for t in tools:
                    params = ", ".join(
                        f"{p['name']}: {p['type']}{'?' if not p['required'] else ''}"
                        for p in t.get("parameters", [])
                    )
                    lines.append(f"  - {t['name']}({params}): {t['description']}")
                descriptions[name] = "\n".join(lines)
            except Exception as exc:  # noqa: BLE001
                descriptions[name] = f"  (unavailable: {exc})"
        return descriptions

    async def execute_plan(self, plan: Plan, question: str) -> list[StepResult]:
        """Execute all plan steps in dependency order."""
        ordered = plan.resolved_order()
        total = len(ordered)

        # Pre-fetch tool schemas for all servers referenced in the plan so that
        # _resolve_args_with_llm can include exact parameter names in its prompt.
        server_names = {step.server for step in ordered}
        tool_schemas: dict[str, dict[str, str]] = {}  # server -> {tool_name -> sig}
        for name in server_names:
            path = self._server_paths.get(name)
            if path is None:
                continue
            try:
                tools = await _list_tools(path)
                tool_schemas[name] = {
                    t["name"]: ", ".join(
                        f"{p['name']}: {p['type']}{'?' if not p['required'] else ''}"
                        for p in t.get("parameters", [])
                    )
                    for t in tools
                }
            except Exception:  # noqa: BLE001
                tool_schemas[name] = {}

        context: dict[int, StepResult] = {}
        results: list[StepResult] = []
        for step in ordered:
            _log.info(
                "Step %d/%d [%s]: %s",
                step.step_number,
                total,
                step.server,
                step.task,
            )
            schema = tool_schemas.get(step.server, {}).get(step.tool, "")
            result = await self.execute_step(
                step, context, question, tool_schema=schema
            )
            if result.success:
                _log.info("Step %d OK.", step.step_number)
            else:
                _log.warning("Step %d FAILED: %s", step.step_number, result.error)
            context[step.step_number] = result
            results.append(result)
        return results

    async def execute_step(
        self,
        step: PlanStep,
        context: dict[int, StepResult],
        question: str,
        tool_schema: str = "",
    ) -> StepResult:
        """Execute a single plan step.

        1. Resolve the MCP server assigned to this step.
        2. If no tool is specified, return expected_output directly.
        3. Call the LLM to generate tool arguments from the task and prior results.
        4. Call the tool and return its result.
        """
        tool_name = (step.tool or "").strip()
        if not tool_name or tool_name.lower() in ("none", "null"):
            return StepResult(
                step_number=step.step_number,
                task=step.task,
                server=step.server,
                response=step.expected_output,
                tool=tool_name,
                tool_args=step.tool_args,
            )

        server_path = self._server_paths.get(step.server)
        if server_path is None:
            return StepResult(
                step_number=step.step_number,
                task=step.task,
                server=step.server,
                response="",
                error=(
                    f"Unknown server '{step.server}'. "
                    f"Registered servers: {list(self._server_paths)}"
                ),
            )

        try:
            _log.info("Step %d: calling LLM to resolve args.", step.step_number)
            resolved_args = await _resolve_args_with_llm(
                question, step.task, tool_name, tool_schema, context, self._llm
            )
            _log.info(
                "Step %d: calling MCP tool %r on server %r.",
                step.step_number,
                tool_name,
                step.server,
            )

            response = await _call_tool(server_path, tool_name, resolved_args)
            return StepResult(
                step_number=step.step_number,
                task=step.task,
                server=step.server,
                response=response,
                tool=tool_name,
                tool_args=resolved_args,
            )
        except Exception as exc:  # noqa: BLE001
            return StepResult(
                step_number=step.step_number,
                task=step.task,
                server=step.server,
                response="",
                error=str(exc),
                tool=tool_name,
                tool_args=step.tool_args,
            )


# ── arg resolution ────────────────────────────────────────────────────────────


async def _resolve_args_with_llm(
    question: str,
    task: str,
    tool: str,
    tool_schema: str,
    context: dict[int, StepResult],
    llm: LLMBackend,
) -> dict:
    """Generate tool arguments from the task description and prior step results."""
    context_text = "\n".join(
        f"Step {n}: {r.response}" for n, r in sorted(context.items())
    )
    prompt = (
        _ARG_RESOLUTION_PROMPT.replace("{question}", question)
        .replace("{task}", task)
        .replace("{tool}", tool)
        .replace("{tool_schema}", tool_schema or "(unknown)")
        .replace("{context}", context_text or "(none)")
    )
    if tool.strip().lower() == "run_skill":
        prompt = prompt.rstrip() + _RUN_SKILL_ARGS_HINT
    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(llm.generate, prompt),
            timeout=_ARG_RESOLUTION_LLM_TIMEOUT_SEC,
        )
    except TimeoutError as exc:
        raise TimeoutError(
            f"LLM arg resolution exceeded {_ARG_RESOLUTION_LLM_TIMEOUT_SEC}s "
            "(set PLAN_EXECUTE_ARG_LLM_TIMEOUT_SEC or fix connectivity / provider)"
        ) from exc
    resolved = _parse_json(raw)
    if resolved is None:
        _log.warning(
            "Tool '%s': arg resolution returned no parseable JSON (response: %r…)",
            tool,
            raw[:120],
        )
        return {}
    return resolved


def _parse_json(raw: str) -> dict | None:
    """Extract a JSON object from an LLM response, with markdown fence handling.

    Returns the parsed dict, or None if no JSON object could be extracted.
    An empty dict ``{}`` is a valid successful parse (e.g. for no-arg tools).
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).lstrip("json").strip()
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            result = json.loads(text[start:end])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    _log.debug("_parse_json: could not extract a JSON object from: %r…", raw[:120])
    return None


# ── MCP protocol helpers ──────────────────────────────────────────────────────


async def _list_tools(server_path: Path | str) -> list[dict]:
    """Connect to an MCP server via stdio and list its tools with parameter info."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    params = make_stdio_params(server_path, repo_root=_REPO_ROOT)

    async def _run() -> list[dict]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                tools = []
                for t in result.tools:
                    schema = t.inputSchema or {}
                    props = schema.get("properties", {})
                    required = set(schema.get("required", []))
                    parameters = [
                        {
                            "name": k,
                            "type": v.get("type", "any"),
                            "required": k in required,
                        }
                        for k, v in props.items()
                    ]
                    tools.append(
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "parameters": parameters,
                        }
                    )
                return tools

    # Use anyio.fail_after (not asyncio.wait_for): MCP stdio_client relies on
    # anyio cancel scopes; asyncio cancelling the nested task breaks teardown
    # with "Attempted to exit cancel scope in a different task".
    try:
        with anyio.fail_after(_MCP_CLIENT_TIMEOUT_SEC):
            return await _run()
    except TimeoutError as exc:
        raise TimeoutError(
            f"MCP list_tools exceeded {_MCP_CLIENT_TIMEOUT_SEC}s "
            f"(server {server_path!r}); increase MCP_CLIENT_TIMEOUT_SEC or fix the server"
        ) from exc


async def _call_tool(server_path: Path | str, tool_name: str, args: dict) -> str:
    """Connect to an MCP server via stdio and call a tool."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    params = make_stdio_params(server_path, repo_root=_REPO_ROOT)

    async def _run() -> str:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                return _extract_content(result.content)

    try:
        with anyio.fail_after(_MCP_CLIENT_TIMEOUT_SEC):
            return await _run()
    except TimeoutError as exc:
        raise TimeoutError(
            f"MCP call_tool({tool_name!r}) exceeded {_MCP_CLIENT_TIMEOUT_SEC}s "
            f"(server {server_path!r}); increase MCP_CLIENT_TIMEOUT_SEC or fix the server"
        ) from exc


def _extract_content(content: list[Any]) -> str:
    """Extract text from MCP tool call result content."""
    return "\n".join(getattr(item, "text", str(item)) for item in content)


def _resolve_args(args: dict, context: dict[int, StepResult]) -> dict:
    """Simple string substitution of {{step_N}} placeholders (kept for tests)."""
    resolved = {}
    for key, val in args.items():
        if isinstance(val, str):

            def _sub(m: re.Match) -> str:
                n = int(m.group(1))
                return context[n].response if n in context else m.group(0)

            resolved[key] = _PLACEHOLDER_RE.sub(_sub, val)
        else:
            resolved[key] = val
    return resolved


def _parse_tool_call(raw: str) -> dict:
    """Parse LLM output into a {tool, args} dict (utility, not used in main path)."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner)
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return {"tool": None, "answer": text}
