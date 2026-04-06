"""Safety clearance demo — IoT reachability + work-order history gate."""

from __future__ import annotations

from pydantic import BaseModel

from ..results import SkillRunResult, SkillStepResult
from ._aliases import asset_id_field, site_name_field
from ._util import detail_ok, mcp_step


class SafetyClearanceArgs(BaseModel):
    site_name: str = site_name_field()
    asset_id: str = asset_id_field()


async def run_safety_clearance_check(pool, arguments: dict) -> SkillRunResult:
    args = SafetyClearanceArgs.model_validate(arguments)
    site = args.site_name.strip()
    aid = args.asset_id.strip()

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
            name="wo_get_work_orders",
            server="wo",
            tool="get_work_orders",
            arguments={"equipment_id": aid},
        )
    )

    sensors_ok = steps[0].ok and detail_ok(steps[0].detail)
    wo_ok = steps[1].ok and detail_ok(steps[1].detail)
    try:
        total = int(steps[1].detail.get("total", 0))
    except (TypeError, ValueError):
        total = 0

    try:
        total_sensors = int(steps[0].detail.get("total_sensors") or 0)
    except (TypeError, ValueError):
        total_sensors = 0

    clearance_pass = (
        sensors_ok
        and wo_ok
        and total > 0
        and total_sensors > 0
    )

    steps.append(
        SkillStepResult(
            name="clearance_decision",
            ok=clearance_pass,
            detail={
                "passed": clearance_pass,
                "rules": [
                    "iot_sensors must succeed with at least one sensor",
                    "work_orders must succeed with at least one order",
                ],
            },
        )
    )

    overall = all(s.ok for s in steps)
    return SkillRunResult(
        skill_id="assetopsbench_demo/safety_clearance_check",
        overall_ok=overall,
        steps=steps,
    )
