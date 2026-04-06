"""In-memory sibling MCP pool for tests."""

from __future__ import annotations

import json
from typing import Any


class FakeSiblingMCPPool:
    def __init__(self, responses: dict[tuple[str, str], dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> str:
        self.calls.append((server_name, tool_name, arguments))
        key = (server_name, tool_name)
        body = self.responses.get(key)
        if body is None:
            return json.dumps({"error": f"unmocked tool {key}"})
        return json.dumps(body)

    async def aclose(self) -> None:
        """Mirror :meth:`SiblingMCPPool.aclose`; fake pool has no stdio to release."""
        return None
