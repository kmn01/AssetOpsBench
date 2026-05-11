"""Stdio MCP child process parameters and environment forwarding.

Used by :mod:`agent.plan_execute.executor` and :mod:`servers.skills` sibling
clients so both spawn MCP servers with identical ``uv run``, ``cwd``, and env
rules.
"""

from __future__ import annotations

import os
from pathlib import Path

# Env vars forwarded to MCP stdio children (exact keys).
MCP_ENV_EXACT: frozenset[str] = frozenset(
    {
        "IOT_DBNAME",
        "WO_DBNAME",
        "WO_DATA_DIR",
        "VIBRATION_DBNAME",
        "ASSET_DATA_FILE",
        "LOG_LEVEL",
        "FMSR_MODEL_ID",
        "LLM_HTTP_TIMEOUT_SEC",
        "ENABLED_SKILLS",
        "PATH_TO_MODELS_DIR",
        "PATH_TO_DATASETS_DIR",
        "PATH_TO_OUTPUTS_DIR",
        "SKILL_INSTALL_STATE_PATH",
        "SKILL_PACK_DIRS",
        "SKILL_SIBLING_COMMANDS",
        "SKILL_MCP_CALL_TIMEOUT_SEC",
        "SKILL_BOOTSTRAP_INSTALL",
    }
)

MCP_ENV_PREFIXES: tuple[str, ...] = (
    "WATSONX_",
    "LITELLM_",
    "COUCHDB_",
    "OPENAI_",
    "ANTHROPIC_",
)


def forwarded_parent_env() -> dict[str, str]:
    """Subset of ``os.environ`` needed by MCP server processes."""
    out: dict[str, str] = {}
    for key, val in os.environ.items():
        if key in MCP_ENV_EXACT or key.startswith(MCP_ENV_PREFIXES):
            out[key] = val
    return out


def mcp_child_env(repo_root: Path) -> dict[str, str]:
    """Env for MCP stdio children: defaults + forwarded vars + ``PYTHONPATH``."""
    from mcp.client.stdio import get_default_environment

    env = {**get_default_environment(), **forwarded_parent_env()}
    src = str(repo_root / "src")
    prev = env.get("PYTHONPATH") or os.environ.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src if not prev else f"{src}{os.pathsep}{prev}"
    return env


def make_stdio_params(
    server: Path | str,
    *,
    repo_root: Path,
):
    """Build ``StdioServerParameters`` for a server spec (same rules as executor).

    - str  → entry-point name; invoked as ``uv run <name>`` from ``repo_root``.
    - Path → ``python -m`` module under ``repo_root``, or raw script path.
    """
    from mcp import StdioServerParameters

    env = mcp_child_env(repo_root)
    if isinstance(server, str):
        return StdioServerParameters(
            command="uv",
            args=["run", server],
            cwd=str(repo_root),
            env=env,
        )
    try:
        rel = server.relative_to(repo_root)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        return StdioServerParameters(
            command="python",
            args=["-m", module],
            cwd=str(repo_root),
            env=env,
        )
    except ValueError:
        return StdioServerParameters(
            command="python",
            args=[str(server)],
            env=env,
        )
