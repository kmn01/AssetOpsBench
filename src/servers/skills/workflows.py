"""Composed multi-step skills (in-process calls into other MCP server modules)."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
    steps: list[WorkflowStepResult]


def _append_step(
    steps: list[WorkflowStepResult], name: str, result: BaseModel
) -> None:
    data = result.model_dump()
    steps.append(
        WorkflowStepResult(name=name, ok="error" not in data, detail=data),
    )


def run_pump_seal_inspection_workflow(
    site_name: str,
    asset_id: str,
    asset_name: str,
) -> PumpSealInspectionWorkflowResult | WorkflowError:
    """Run IoT sensors + FMSR failure modes + work orders in one MCP tool call."""
    from servers.fmsr.main import get_failure_modes
    from servers.iot.main import sensors
    from servers.wo.tools import get_work_orders

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

    _append_step(steps, "iot_sensors", sensors(site, aid))
    _append_step(steps, "fmsr_failure_modes", get_failure_modes(aname))
    _append_step(steps, "wo_get_work_orders", get_work_orders(aid))

    return PumpSealInspectionWorkflowResult(
        site_name=site,
        asset_id=aid,
        asset_name=aname,
        steps=steps,
    )
