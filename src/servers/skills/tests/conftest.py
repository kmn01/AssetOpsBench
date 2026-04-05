import json

import pytest


async def call_tool(mcp_instance, tool_name: str, args: dict) -> dict:
    """Call an MCP tool and return parsed JSON response."""
    contents, _ = await mcp_instance.call_tool(tool_name, args)
    return json.loads(contents[0].text)
