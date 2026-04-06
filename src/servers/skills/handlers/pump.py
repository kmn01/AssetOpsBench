"""Pump seal inspection skill — IoT + FMSR + work orders via sibling MCP."""

from __future__ import annotations

import asyncio

from pydantic import AliasChoices, BaseModel, Field, model_validator

from ..results import SkillRunResult
from ._aliases import site_name_field
from ._util import mcp_step


class PumpSealArgs(BaseModel):
    site_name: str = site_name_field()
    asset_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("asset_id", "asset", "equipment_id"),
    )
    asset_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("asset_name", "name", "equipment_name"),
    )

    @model_validator(mode="after")
    def _default_asset_name_from_id(self) -> "PumpSealArgs":
        """Allow a single equipment token when id and name are the same (e.g. PUMP1)."""
        aid = (self.asset_id or "").strip() or None
        aname = (self.asset_name or "").strip() or None
        if not aid and not aname:
            raise ValueError("provide asset_id and/or asset_name")
        if not aid:
            self.asset_id = aname
        if not aname:
            self.asset_name = aid
        return self


async def run_pump_seal_inspection(pool, arguments: dict) -> SkillRunResult:
    args = PumpSealArgs.model_validate(arguments)
    site = args.site_name.strip()
    aid = args.asset_id.strip()
    aname = args.asset_name.strip()

    # Run in parallel: three different sibling servers (distinct locks) and no
    # cross-step data dependency. Sequential worst-case was 3× sibling timeout
    # (e.g. 360s), exceeding plan-execute's default MCP_CLIENT_TIMEOUT_SEC (300s).
    iot_s, fmsr_s, wo_s = await asyncio.gather(
        mcp_step(
            pool,
            name="iot_sensors",
            server="iot",
            tool="sensors",
            arguments={"site_name": site, "asset_id": aid},
        ),
        mcp_step(
            pool,
            name="fmsr_failure_modes",
            server="fmsr",
            tool="get_failure_modes",
            arguments={"asset_name": aname},
        ),
        mcp_step(
            pool,
            name="wo_get_work_orders",
            server="wo",
            tool="get_work_orders",
            arguments={"equipment_id": aid},
        ),
    )
    steps = [iot_s, fmsr_s, wo_s]
    overall = all(s.ok for s in steps)
    return SkillRunResult(
        skill_id="assetopsbench/pump_seal_inspection",
        overall_ok=overall,
        steps=steps,
    )