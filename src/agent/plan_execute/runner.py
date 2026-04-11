"""Plan-and-execute agent runner using MCP servers as tool providers.

Replaces AgentHive's combination of PlanningWorkflow + SequentialWorkflow with
an MCP-native implementation:

  AgentHive                       plan_execute
  ────────────────────────────    ─────────────────────────────
  PlanningWorkflow.generate_steps → Planner.generate_plan
  SequentialWorkflow.run          → Executor.execute_plan
  ReactAgent.execute_task         → _list_tools + _call_tool (MCP stdio)
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from llm import LLMBackend

from .executor import Executor
from .metrics import PlanExecuteMetrics
from .planner import Planner
from ..models import OrchestratorResult
from ..runner import AgentRunner

_log = logging.getLogger(__name__)

_SUMMARIZE_PROMPT = """\
You are summarizing the results of a multi-step task execution for an \
industrial asset operations system.

Original question: {question}

Step-by-step execution results:
{results}

Your task: Create a comprehensive, detailed answer to the original question. 

IMPORTANT FORMATTING:
1. Write a FULL, DETAILED explanation answering the user's question
2. Include all relevant information, procedures, steps, and details
3. Do NOT just list results - synthesize them into a coherent narrative
4. At the END of your answer, add a "Sources & Citations" section that lists:
   - Document name and page number for each source used
   - Confidence/match percentage if available
5. Format citations as:
   ────────────────────
   Sources & Citations:
   ────────────────────
   • Source: [PDF Name] - Page X (YY% match)
   • Source: [PDF Name] - Pages X-Y (ZZ% match)

Example answer structure:
   "The pump maintenance procedures include:
   1. Daily checks: ...
   2. Weekly checks: ...
   [detailed explanation]
   
   Sources & Citations:
   ────────────────────
   • Centrifugal Pump Seal Inspection Manual - Page 2 (87% match)
   • pump_maintenance_handbook.pdf - Pages 5-7 (92% match)"

Provide a complete answer based on the results above, with full details and citations at the end.
"""


class PlanExecuteRunner(AgentRunner):
    """Entry-point for plan-and-execute workflows using MCP servers as tool providers.

    Usage::

        from agent import PlanExecuteRunner
        from llm import LiteLLMBackend

        runner = PlanExecuteRunner(llm=LiteLLMBackend("watsonx/meta-llama/llama-3-3-70b-instruct"))
        result = await runner.run("What are the assets at site MAIN?")
        print(result.answer)

    Args:
        llm: LLM backend used for planning, tool selection, and summarisation.
        server_paths: Override MCP server specs.  Keys must match the server
                      names the planner will assign steps to.  Values are
                      either a uv entry-point name (str) or a Path to a
                      script file.  Defaults to all five registered servers.
    """

    def __init__(
        self,
        llm: LLMBackend,
        server_paths: dict[str, Path | str] | None = None,
    ) -> None:
        super().__init__(llm, server_paths)
        self._planner = Planner(llm)
        self._executor = Executor(llm, server_paths)

    async def run(self, question: str) -> OrchestratorResult:
        """Run the full plan-execute loop for a question.

        Steps:
          1. Discover available servers from registered MCP servers.
          2. Use the LLM to decompose the question into an execution plan.
          3. Execute each plan step by routing tool calls to MCP servers.
          4. Summarise the step results into a final answer.

        Args:
            question: The user question to answer.

        Returns:
            OrchestratorResult with the final answer, the generated plan, and
            the per-step execution history.
        """
        t_run0 = time.monotonic()

        # 1. Discover
        _log.info("Discovering server capabilities...")
        t0 = time.monotonic()
        server_descriptions = await self._executor.get_server_descriptions()
        discover_ms = (time.monotonic() - t0) * 1000.0

        # 2. Plan (thread: sync LLM must not block the asyncio event loop)
        _log.info("Planning...")
        t0 = time.monotonic()
        plan, plan_usage = await asyncio.to_thread(
            self._planner.generate_plan, question, server_descriptions
        )
        plan_ms = (time.monotonic() - t0) * 1000.0
        _log.info("Plan has %d step(s).", len(plan.steps))

        # 3. Execute
        t0 = time.monotonic()
        history = await self._executor.execute_plan(plan, question)
        execute_ms = (time.monotonic() - t0) * 1000.0

        # 4. Summarise
        _log.info("Summarising...")
        results_text = "\n\n".join(
            f"Step {r.step_number} — {r.task} (server: {r.server}):\n"
            + (r.response if r.success else f"ERROR: {r.error}")
            for r in history
        )
        summarize_prompt = _SUMMARIZE_PROMPT.format(
            question=question, results=results_text
        )
        t0 = time.monotonic()
        answer, summarize_usage = await asyncio.to_thread(
            self._llm.generate_with_usage, summarize_prompt
        )
        summarize_ms = (time.monotonic() - t0) * 1000.0
        e2e_ms = (time.monotonic() - t_run0) * 1000.0

        metrics = PlanExecuteMetrics.from_phases_and_history(
            discover_ms=discover_ms,
            plan_ms=plan_ms,
            execute_ms=execute_ms,
            summarize_ms=summarize_ms,
            e2e_ms=e2e_ms,
            history=history,
            plan_step_count=len(plan.steps),
            plan_usage=plan_usage,
            summarize_usage=summarize_usage,
        )

        return OrchestratorResult(
            question=question,
            answer=answer,
            plan=plan,
            history=history,
            metrics=metrics,
        )
