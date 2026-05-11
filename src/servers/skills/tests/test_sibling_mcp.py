"""Tests for :mod:`servers.skills.sibling_mcp` pool lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from servers.skills.sibling_mcp import SiblingMCPPool


@pytest.mark.anyio
async def test_aclose_exits_session_then_stdio(tmp_path) -> None:
    order: list[str] = []

    stdio_cm = MagicMock()
    stdio_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))

    async def exit_stdio(*_args: object) -> None:
        order.append("stdio")

    stdio_cm.__aexit__ = AsyncMock(side_effect=exit_stdio)

    sess_cm = MagicMock()
    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=MagicMock(content=[]))

    async def exit_session(*_args: object) -> None:
        order.append("session")

    sess_cm.__aenter__ = AsyncMock(return_value=mock_session)
    sess_cm.__aexit__ = AsyncMock(side_effect=exit_session)

    pool = SiblingMCPPool(
        project_root=tmp_path,
        command_map={"iot": "iot-mcp-server"},
        timeout_sec=1.0,
    )

    with (
        patch("mcp.client.stdio.stdio_client", return_value=stdio_cm),
        patch("mcp.ClientSession", return_value=sess_cm),
    ):
        await pool.call_tool("iot", "any_tool", {})
        await pool.aclose()

    # Teardown happens inside call_tool (same task as __aenter__); aclose is a no-op.
    assert order == ["session", "stdio"]
    sess_cm.__aexit__.assert_awaited_once()
    stdio_cm.__aexit__.assert_awaited_once()


@pytest.mark.anyio
async def test_aclose_idempotent(tmp_path) -> None:
    stdio_cm = MagicMock()
    stdio_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    stdio_cm.__aexit__ = AsyncMock(return_value=None)
    sess_cm = MagicMock()
    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=MagicMock(content=[]))
    sess_cm.__aenter__ = AsyncMock(return_value=mock_session)
    sess_cm.__aexit__ = AsyncMock(return_value=None)

    pool = SiblingMCPPool(
        project_root=tmp_path,
        command_map={"iot": "iot-mcp-server"},
        timeout_sec=1.0,
    )

    with (
        patch("mcp.client.stdio.stdio_client", return_value=stdio_cm),
        patch("mcp.ClientSession", return_value=sess_cm),
    ):
        await pool.call_tool("iot", "t", {})
        await pool.aclose()
        await pool.aclose()

    assert stdio_cm.__aexit__.await_count == 1


@pytest.mark.anyio
async def test_call_tool_after_aclose_raises(tmp_path) -> None:
    stdio_cm = MagicMock()
    stdio_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    stdio_cm.__aexit__ = AsyncMock(return_value=None)
    sess_cm = MagicMock()
    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=MagicMock(content=[]))
    sess_cm.__aenter__ = AsyncMock(return_value=mock_session)
    sess_cm.__aexit__ = AsyncMock(return_value=None)

    pool = SiblingMCPPool(
        project_root=tmp_path,
        command_map={"iot": "iot-mcp-server"},
        timeout_sec=1.0,
    )

    with (
        patch("mcp.client.stdio.stdio_client", return_value=stdio_cm),
        patch("mcp.ClientSession", return_value=sess_cm),
    ):
        await pool.call_tool("iot", "t", {})
        await pool.aclose()

    with pytest.raises(RuntimeError, match="closed"):
        await pool.call_tool("iot", "t", {})
