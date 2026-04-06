"""Diagnostics / root-cause style bundle — sensors + failure modes + FM↔sensor mapping."""

from __future__ import annotations

from pydantic import BaseModel

from ..results import SkillRunResult
from ._aliases import asset_id_field, asset_name_field, site_name_field
from ._util import mcp_step


class DiagnosticsArgs(BaseModel):
    site_name: str = site_name_field()
    asset_id: str = asset_id_field()
    asset_name: str = asset_name_field()


async def run_asset_diagnostics_bundle(pool, arguments: dict) -> SkillRunResult:
    args = DiagnosticsArgs.model_validate(arguments)
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

    failure_modes: list = []
    sensors_list: list = []
    if steps[1].ok:
        failure_modes = steps[1].detail.get("failure_modes") or []
        if not isinstance(failure_modes, list):
            failure_modes = []
    if steps[0].ok:
        sensors_list = steps[0].detail.get("sensors") or []
        if not isinstance(sensors_list, list):
            sensors_list = []

    steps.append(
        await mcp_step(
            pool,
            name="fmsr_failure_mode_sensor_mapping",
            server="fmsr",
            tool="get_failure_mode_sensor_mapping",
            arguments={
                "asset_name": aname,
                "failure_modes": failure_modes[:5],
                "sensors": sensors_list[:10],
            },
        )
    )

    overall = all(s.ok for s in steps)
    return SkillRunResult(
        skill_id="assetopsbench_demo/asset_diagnostics_bundle",
        overall_ok=overall,
        steps=steps,
    )
