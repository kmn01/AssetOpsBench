"""CLI entry point for the plan-execute runner.

Usage:
    plan-execute "What assets are available at site MAIN?"
    plan-execute --model-id watsonx/ibm/granite-3-3-8b-instruct --show-plan "List sensors"
    plan-execute --model-id litellm_proxy/GCP/claude-4-sonnet "What are the failure modes?"
    plan-execute --json "What is the current time?"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

_DEFAULT_MODEL = "watsonx/meta-llama/llama-4-maverick-17b-128e-instruct-fp8"

_LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
_LOG_DATE_FORMAT = "%H:%M:%S"

_log = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plan-execute",
        description="Run a question through the MCP plan-execute workflow.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
model-id format:
  The provider is encoded in the model-id prefix:
    watsonx/<model>          IBM WatsonX  (e.g. watsonx/meta-llama/llama-3-3-70b-instruct)
    litellm_proxy/<model>    LiteLLM proxy (e.g. litellm_proxy/GCP/claude-4-sonnet)

environment variables:
  WATSONX_APIKEY        IBM WatsonX API key      (required for watsonx/* models)
  WATSONX_PROJECT_ID    IBM WatsonX project ID   (required for watsonx/* models)
  WATSONX_URL           IBM WatsonX endpoint     (optional, defaults to us-south)

  LITELLM_API_KEY       LiteLLM API key          (required for non-watsonx models)
  LITELLM_BASE_URL      LiteLLM base URL         (required for non-watsonx models)

  LOG_LEVEL             Log level for MCP servers (default: WARNING)

  MCP_CLIENT_TIMEOUT_SEC  Max seconds for each MCP connect / list_tools / call_tool
                          in plan-execute (default in code: 600). Raises TimeoutError if exceeded.

examples:
  plan-execute "What assets are at site MAIN?"
  plan-execute --model-id watsonx/ibm/granite-3-3-8b-instruct --show-plan "List sensors"
  plan-execute --model-id litellm_proxy/GCP/claude-4-sonnet "What are the failure modes?"
  plan-execute --quiet --show-history --json "How many IoT observations exist for CH-1?"
  plan-execute --verbose --show-history --json "How many IoT observations exist for CH-1?"
""",
    )
    parser.add_argument("question", help="The question to answer.")
    parser.add_argument(
        "--model-id",
        default=_DEFAULT_MODEL,
        metavar="MODEL_ID",
        help=f"litellm model string with provider prefix (default: {_DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--server",
        action="append",
        metavar="NAME=PATH",
        dest="servers",
        default=[],
        help=(
            "Register an MCP server as NAME=PATH. "
            "Overrides the default servers. "
            "Repeatable."
        ),
    )
    parser.add_argument(
        "--show-plan",
        action="store_true",
        help="Print the generated plan before execution.",
    )
    parser.add_argument(
        "--show-history",
        action="store_true",
        help="Print each step result after execution.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output the full result (answer, plan, history) as JSON.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show DEBUG-level logs on stderr (noisy; includes libraries).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress logs (WARNING and above only on stderr).",
    )
    parser.add_argument(
        "--rag-mode",
        action="store_true",
        help=(
            "Use traditional RAG (Retrieval-Augmented Generation) instead of plan-execute. "
            "Retrieves chunks then calls LLM for generation. Use to benchmark vs Knowledge Plugin. "
            "Example: plan-execute 'What are pump procedures?' --rag-mode --show-history"
        ),
    )
    return parser


def _setup_logging(*, verbose: bool, quiet: bool) -> None:
    """Configure logging: by default show agent progress on stderr; optional quiet/debug."""
    fmt = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)
    stderr_h = logging.StreamHandler(sys.stderr)
    stderr_h.setFormatter(fmt)
    logging.root.handlers.clear()
    logging.root.addHandler(stderr_h)

    if verbose:
        logging.root.setLevel(logging.DEBUG)
        return

    if quiet:
        logging.root.setLevel(logging.WARNING)
        return

    logging.root.setLevel(logging.WARNING)
    agent_log = logging.getLogger("agent")
    agent_log.setLevel(logging.INFO)
    agent_h = logging.StreamHandler(sys.stderr)
    agent_h.setFormatter(fmt)
    agent_log.addHandler(agent_h)
    agent_log.propagate = False


def _build_llm(model_id: str):
    """Instantiate the LiteLLMBackend for the given model_id."""
    try:
        from llm.litellm import LiteLLMBackend
    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        return LiteLLMBackend(model_id=model_id)
    except KeyError as exc:
        print(f"error: missing environment variable {exc}", file=sys.stderr)
        sys.exit(1)


def _parse_servers(entries: list[str]) -> dict[str, Path] | None:
    """Parse NAME=PATH pairs into a server_paths dict, or None if empty."""
    if not entries:
        return None
    result: dict[str, Path] = {}
    for entry in entries:
        if "=" not in entry:
            print(
                f"error: --server requires NAME=PATH format, got: {entry!r}",
                file=sys.stderr,
            )
            sys.exit(1)
        name, _, path = entry.partition("=")
        result[name.strip()] = Path(path.strip())
    return result


def _print_section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


async def _run(args: argparse.Namespace) -> None:
    from agent.plan_execute.runner import PlanExecuteRunner
    from agent.plan_execute.rag_runner import RAGRunner

    llm = _build_llm(args.model_id)
    server_paths = _parse_servers(args.servers)

    # Choose runner based on mode
    if args.rag_mode:
        _log.info("Using traditional RAG mode (retrieval + LLM generation)")
        runner = RAGRunner(llm=llm, server_paths=server_paths)
    else:
        _log.info("Using Knowledge Plugin mode (retrieval only, no LLM generation)")
        runner = PlanExecuteRunner(llm=llm, server_paths=server_paths)

    result = await runner.run(args.question)

    if args.output_json:
        output = {
            "question": result.question,
            "answer": result.answer,
            "metrics": (
                result.metrics.to_json_dict() if result.metrics is not None else None
            ),
            "plan": [
                {
                    "step": s.step_number,
                    "task": s.task,
                    "server": s.server,
                    "tool": s.tool,
                    "tool_args": s.tool_args,
                    "dependencies": s.dependencies,
                    "expected_output": s.expected_output,
                }
                for s in result.plan.steps
            ],
            "history": [
                {
                    "step": r.step_number,
                    "task": r.task,
                    "server": r.server,
                    "tool": r.tool,
                    "tool_args": r.tool_args,
                    "response": r.response,
                    "error": r.error,
                    "success": r.success,
                }
                for r in result.history
            ],
        }
        print(json.dumps(output, indent=2))
        return

    if args.show_plan:
        _print_section("Plan")
        for step in result.plan.steps:
            deps = ", ".join(f"#{d}" for d in step.dependencies) or "none"
            print(f"  [{step.step_number}] {step.server}: {step.task}")
            print(f"       tool: {step.tool}  args: {step.tool_args}")
            print(f"       deps={deps} | expected: {step.expected_output}")

    if args.show_history:
        _print_section("Execution History")
        for r in result.history:
            status = "OK " if r.success else "ERR"
            print(f"  [{status}] Step {r.step_number} ({r.server}): {r.task}")
            if r.tool and r.tool.lower() not in ("none", "null", ""):
                print(f"       tool: {r.tool}  args: {r.tool_args}")
            detail = r.response if r.success else f"Error: {r.error}"
            snippet = detail[:200] + ("..." if len(detail) > 200 else "")
            print(f"        {snippet}")

    _print_section("Answer")
    print(result.answer)
    print()


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    args = _build_parser().parse_args()
    if args.verbose and args.quiet:
        print("error: use only one of --verbose and --quiet", file=sys.stderr)
        sys.exit(2)
    _setup_logging(verbose=args.verbose, quiet=args.quiet)
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
