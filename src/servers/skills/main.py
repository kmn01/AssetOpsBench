"""Skills MCP server: marketplace discovery, install state, and composed skills."""

from __future__ import annotations

import logging
import os
import sys

import anyio
from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from .registry import (
    MarketplaceError,
    MarketplaceLoadError,
    SkillListItem,
    SkillManifestView,
    get_manifest_for_fqid,
    list_skill_items,
    load_skill_catalog,
    maybe_bootstrap_install_state,
)
from .results import SkillInvocationError, SkillRunResult
from .runner import run_skill_impl

_log_level = getattr(
    logging, os.environ.get("LOG_LEVEL", "WARNING").upper(), logging.WARNING
)
logging.basicConfig(level=_log_level)
_log = logging.getLogger(__name__)

mcp = FastMCP("skills")


def _exc_group_is_only_client_disconnect(exc: BaseException) -> bool:
    """True when every leaf is only ``ClosedResourceError`` (stdin closed first).

    Plan-execute / IDE MCP clients often close stdio right after the last tool
    result is consumed; the server can still be in ``_send_response``, which
    then raises — buried inside nested ``ExceptionGroup``s. Not a user-facing
    failure once the tool already completed.
    """
    if isinstance(exc, anyio.ClosedResourceError):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return bool(exc.exceptions) and all(
            _exc_group_is_only_client_disconnect(e) for e in exc.exceptions
        )
    return False


class ListSkillsResult(BaseModel):
    """Catalog listing with optional load error (duplicate FQID, bad pack, etc.)."""

    skills: list[SkillListItem] = Field(default_factory=list)
    catalog_error: str | None = None


def _startup_validate_catalog() -> None:
    try:
        load_skill_catalog()
    except MarketplaceLoadError as exc:
        _log.critical("Skill catalog failed to load: %s", exc)
        sys.exit(1)


@mcp.tool()
def list_skills() -> ListSkillsResult:
    """List all skills from merged pack manifests with installed/runnable flags."""
    try:
        return ListSkillsResult(skills=list_skill_items())
    except MarketplaceLoadError as exc:
        return ListSkillsResult(skills=[], catalog_error=str(exc))


@mcp.tool()
def get_skill_manifest(skill_id: str) -> SkillManifestView | MarketplaceError:
    """Return metadata for one skill. ``skill_id`` must be a full FQID ``pack_id/skill_id``."""
    return get_manifest_for_fqid(skill_id.strip())


@mcp.tool()
async def run_skill(
    skill_id: str,
    arguments: dict,
) -> SkillRunResult | SkillInvocationError:
    """Run a skill by FQID. ``arguments`` are validated by the skill's handler."""
    return await run_skill_impl(skill_id.strip(), arguments or {})


def main() -> None:
    _startup_validate_catalog()
    maybe_bootstrap_install_state()
    try:
        mcp.run(transport="stdio")
    except BaseExceptionGroup as eg:
        if _exc_group_is_only_client_disconnect(eg):
            _log.debug("MCP stdio client disconnected during shutdown (benign).")
            return
        raise


if __name__ == "__main__":
    main()