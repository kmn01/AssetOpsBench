"""Lazy-reused stdio MCP clients for sibling servers (iot, fmsr, wo, ...)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from servers.common.mcp_stdio import make_stdio_params

from .registry import repo_root

_log = logging.getLogger(__name__)

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
    """One long-lived stdio MCP session per logical server name."""

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
        self._stdio_acm: dict[str, Any] = {}
        self._session_acm: dict[str, Any] = {}
        self._sessions: dict[str, Any] = {}
        self._closed = False

    @classmethod
    def from_env(cls) -> SiblingMCPPool:
        return cls(
            project_root=repo_root(),
            command_map=default_sibling_command_map(),
            timeout_sec=float(os.environ.get("SKILL_MCP_CALL_TIMEOUT_SEC", "120")),
        )

    async def _ensure_session(self, server_name: str):
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        if self._closed:
            raise RuntimeError("SiblingMCPPool is closed")
        if server_name in self._sessions:
            return self._sessions[server_name]
        spec = self._command_map.get(server_name)
        if spec is None:
            raise ValueError(
                f"unknown sibling server {server_name!r}; extend SKILL_SIBLING_COMMANDS"
            )
        params = make_stdio_params(spec, repo_root=self._project_root)
        stdio_cm = stdio_client(params)
        read_write = await stdio_cm.__aenter__()
        try:
            read, write = read_write
            sess_cm = ClientSession(read, write)
            session = await sess_cm.__aenter__()
            try:
                await session.initialize()
            except BaseException:
                await sess_cm.__aexit__(*sys.exc_info())
                raise
        except BaseException:
            await stdio_cm.__aexit__(*sys.exc_info())
            raise
        self._stdio_acm[server_name] = stdio_cm
        self._session_acm[server_name] = sess_cm
        self._sessions[server_name] = session
        _log.info("Sibling MCP session ready for %s", server_name)
        return session

    async def aclose(self) -> None:
        """Exit all stored stdio and session context managers (inner session first)."""
        if self._closed:
            return
        self._closed = True
        names = list(self._sessions.keys())
        for name in names:
            lock = self._locks.setdefault(name, asyncio.Lock())
            async with lock:
                sess_cm = self._session_acm.pop(name, None)
                stdio_cm = self._stdio_acm.pop(name, None)
                self._sessions.pop(name, None)
                errors: list[BaseException] = []
                if sess_cm is not None:
                    try:
                        await sess_cm.__aexit__(None, None, None)
                    except BaseException as e:
                        errors.append(e)
                if stdio_cm is not None:
                    try:
                        await stdio_cm.__aexit__(None, None, None)
                    except BaseException as e:
                        errors.append(e)
                if errors:
                    if len(errors) == 1:
                        raise errors[0]
                    raise ExceptionGroup("SiblingMCPPool.aclose", errors)

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
        lock = self._locks.setdefault(server_name, asyncio.Lock())
        async with lock:
            session = await self._ensure_session(server_name)
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=self._timeout_sec,
            )
            return _extract_content(getattr(result, "content", None))


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