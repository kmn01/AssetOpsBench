"""Pump seal inspection skill — IoT + FMSR + work orders via sibling MCP."""

from __future__ import annotations

from pydantic import BaseModel

from ..results import SkillRunResult
from ._aliases import asset_id_field, asset_name_field, site_name_field
from ._util import mcp_step


class PumpSealArgs(BaseModel):
    site_name: str = site_name_field()
    asset_id: str = asset_id_field()
    asset_name: str = asset_name_field()


async def run_pump_seal_inspection(pool, arguments: dict) -> SkillRunResult:
    args = PumpSealArgs.model_validate(arguments)
    site = args.site_name.strip()
    aid = args.asset_id.strip()
    aname = args.asset_name.strip()

    steps: list = []
    steps.append(
        await mcp_step(
            pool,
            name="iot_sensors",
            server="iot",
            tool="sensors",
            arguments={"site_name": site, "asset_id": aid},
        )
    )
    steps.append(
        await mcp_step(
            pool,
            name="fmsr_failure_modes",
            server="fmsr",
            tool="get_failure_modes",
            arguments={"asset_name": aname},
        )
    )
    steps.append(
        await mcp_step(
            pool,
            name="wo_get_work_orders",
            server="wo",
            tool="get_work_orders",
            arguments={"equipment_id": aid},
        )
    )
    overall = all(s.ok for s in steps)
    return SkillRunResult(
        skill_id="assetopsbench/pump_seal_inspection",
        overall_ok=overall,
        steps=steps,
    )