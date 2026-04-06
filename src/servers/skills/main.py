"""Skills MCP server: marketplace discovery + composed workflows."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from .registry import (
    MarketplaceError,
    SkillManifestResponse,
    SkillSummary,
    get_manifest_for_skill,
    list_skill_summaries,
)
from .workflows import (
    PumpSealInspectionWorkflowResult,
    WorkflowError,
    run_pump_seal_inspection_workflow as _run_pump_seal_inspection_workflow,
)

_log_level = getattr(
    logging, os.environ.get("LOG_LEVEL", "WARNING").upper(), logging.WARNING
)
logging.basicConfig(level=_log_level)

mcp = FastMCP("skills")


class ListSkillsResult(BaseModel):
    """Wrapped list so MCP JSON stays a single object (FastMCP may unwrap bare lists)."""

    skills: list[SkillSummary] = Field(default_factory=list)


@mcp.tool()
def list_skills() -> ListSkillsResult:
    """List installable / enabled high-level skills from the marketplace manifest."""
    return ListSkillsResult(skills=list_skill_summaries())


@mcp.tool()
def get_skill_manifest(skill_id: str) -> SkillManifestResponse | MarketplaceError:
    """Return full metadata for one skill (required MCP servers, asset types, keywords)."""
    return get_manifest_for_skill(skill_id.strip())


@mcp.tool()
def run_pump_seal_inspection_workflow(
    site_name: str,
    asset_id: str,
    asset_name: str,
) -> PumpSealInspectionWorkflowResult | WorkflowError:
    """Composed workflow: IoT sensors + FMSR failure modes + work orders for one asset."""
    return _run_pump_seal_inspection_workflow(site_name, asset_id, asset_name)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
