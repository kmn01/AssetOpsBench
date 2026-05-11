"""Stdio MCP clients to sibling servers (iot, fmsr, wo, ...).

Each :meth:`SiblingMCPPool.call_tool` opens a short-lived stdio transport and closes
it in the **same** asyncio task. Reusing sessions across tasks was unsafe: parallel
``asyncio.gather`` entered ``stdio_client`` in worker tasks while ``aclose`` exited
from the parent task, triggering AnyIO "cancel scope in a different task" errors.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import anyio

from servers.common.mcp_stdio import make_stdio_params

from .registry import repo_root

_TEST_POOL: Any | None = None


def set_sibling_pool_for_testing(pool: Any | None) -> None:
    """Replace the process-global pool (used by unit tests)."""
    global _TEST_POOL
    _TEST_POOL = pool


def default_sibling_command_map() -> dict[str, str]:
    raw = os.environ.get("SKILL_SIBLING_COMMANDS", "").strip()
    if not raw:
        return {
            "iot": "iot-mcp-server",
            "fmsr": "fmsr-mcp-server",
            "wo": "wo-mcp-server",
            "utilities": "utilities-mcp-server",
            "vibration": "vibration-mcp-server",
        }
    out: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        key, val = k.strip(), v.strip()
        if key:
            out[key] = val
    if not out:
        raise ValueError("SKILL_SIBLING_COMMANDS is set but parsed empty")
    return out


def _extract_content(content: Any) -> str:
    if content is None:
        return ""
    if not isinstance(content, list):
        return ""
    return "\n".join(getattr(item, "text", str(item)) for item in content)


class SiblingMCPPool:
    """Serialize calls per server and run each RPC in a one-shot stdio client."""

    def __init__(
        self,
        *,
        project_root: Path,
        command_map: dict[str, str],
        timeout_sec: float,
    ) -> None:
        self._project_root = project_root
        self._command_map = command_map
        self._timeout_sec = timeout_sec
        self._locks: dict[str, asyncio.Lock] = {}
        self._closed = False

    @classmethod
    def from_env(cls) -> SiblingMCPPool:
        return cls(
            project_root=repo_root(),
            command_map=default_sibling_command_map(),
            timeout_sec=float(os.environ.get("SKILL_MCP_CALL_TIMEOUT_SEC", "120")),
        )

    async def aclose(self) -> None:
        """Mark the pool closed (no persistent stdio sessions to drain)."""
        self._closed = True

    async def __aenter__(self) -> SiblingMCPPool:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        if self._closed:
            raise RuntimeError("SiblingMCPPool is closed")
        spec = self._command_map.get(server_name)
        if spec is None:
            raise ValueError(
                f"unknown sibling server {server_name!r}; extend SKILL_SIBLING_COMMANDS"
            )
        params = make_stdio_params(spec, repo_root=self._project_root)
        lock = self._locks.setdefault(server_name, asyncio.Lock())
        async with lock:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client

            async def _run() -> str:
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments)
                        return _extract_content(getattr(result, "content", None))

            with anyio.fail_after(self._timeout_sec):
                return await _run()


def get_sibling_pool() -> SiblingMCPPool:
    if _TEST_POOL is not None:
        return _TEST_POOL
    return _DEFAULT_POOL.get()


async def close_sibling_pool() -> None:
    """Close the process-default pool and drop the singleton reference.

    No-op when :func:`set_sibling_pool_for_testing` replaced the pool.
    """
    if _TEST_POOL is not None:
        return
    await _DEFAULT_POOL.aclose()


class _Singleton:
    __slots__ = ("_pool",)

    def __init__(self) -> None:
        self._pool: SiblingMCPPool | None = None

    def get(self) -> SiblingMCPPool:
        if self._pool is None:
            self._pool = SiblingMCPPool.from_env()
        return self._pool

    async def aclose(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None


_DEFAULT_POOL = _Singleton()
