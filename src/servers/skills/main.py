"""Skills MCP server: marketplace discovery, install state, and composed skills."""

from __future__ import annotations

import logging
import sys

import os

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
)
from .results import SkillInvocationError, SkillRunResult
from .runner import run_skill_impl

_log_level = getattr(
    logging, os.environ.get("LOG_LEVEL", "WARNING").upper(), logging.WARNING
)
logging.basicConfig(level=_log_level)
_log = logging.getLogger(__name__)

mcp = FastMCP("skills")


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


def main():
    _startup_validate_catalog()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()