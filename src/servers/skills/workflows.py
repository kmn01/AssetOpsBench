"""Composed multi-step skills (in-process calls into other MCP server modules)."""

from __future__ import annotations

from typing import List, Union

from pydantic import BaseModel, Field

from servers.fmsr.main import get_failure_modes
from servers.iot.main import sensors
from servers.wo.tools import get_work_orders


class WorkflowError(BaseModel):
    error: str


class WorkflowStepResult(BaseModel):
    name: str
    ok: bool
    detail: dict = Field(default_factory=dict)


class PumpSealInspectionWorkflowResult(BaseModel):
    site_name: str
    asset_id: str
    asset_name: str
    steps: List[WorkflowStepResult]


def run_pump_seal_inspection_workflow(
    site_name: str,
    asset_id: str,
    asset_name: str,
) -> Union[PumpSealInspectionWorkflowResult, WorkflowError]:
    """Run IoT sensors + FMSR failure modes + work orders in one MCP tool call."""
    site = (site_name or "").strip()
    aid = (asset_id or "").strip()
    aname = (asset_name or "").strip()
    if not site:
        return WorkflowError(error="site_name is required")
    if not aid:
        return WorkflowError(error="asset_id is required")
    if not aname:
        return WorkflowError(error="asset_name is required")

    steps: list[WorkflowStepResult] = []

    sn = sensors(site, aid)
    sn_dump = sn.model_dump()
    steps.append(
        WorkflowStepResult(
            name="iot_sensors",
            ok="error" not in sn_dump,
            detail=sn_dump,
        )
    )

    fm = get_failure_modes(aname)
    fm_dump = fm.model_dump()
    steps.append(
        WorkflowStepResult(
            name="fmsr_failure_modes",
            ok="error" not in fm_dump,
            detail=fm_dump,
        )
    )

    wo = get_work_orders(aid)
    wo_dump = wo.model_dump()
    steps.append(
        WorkflowStepResult(
            name="wo_get_work_orders",
            ok="error" not in wo_dump,
            detail=wo_dump,
        )
    )

    return PumpSealInspectionWorkflowResult(
        site_name=site,
        asset_id=aid,
        asset_name=aname,
        steps=steps,
    )
