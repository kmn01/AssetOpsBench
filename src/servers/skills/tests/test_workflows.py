from unittest.mock import patch

import pytest

from servers.fmsr.main import FailureModesResult
from servers.iot.main import ErrorResult as IoTError
from servers.iot.main import SensorsResult
from servers.wo.models import ErrorResult as WoError
from servers.wo.models import WorkOrderItem, WorkOrdersResult

from servers.skills.workflows import (
    WorkflowError,
    run_pump_seal_inspection_workflow,
)


@pytest.mark.parametrize(
    "site,aid,aname,err",
    [
        ("", "a", "p", "site_name"),
        ("MAIN", "", "p", "asset_id"),
        ("MAIN", "a", "", "asset_name"),
    ],
)
def test_workflow_validates_inputs(site, aid, aname, err):
    r = run_pump_seal_inspection_workflow(site, aid, aname)
    assert isinstance(r, WorkflowError)
    assert err in r.error


def test_workflow_runs_steps_with_mocks():
    wo_item = WorkOrderItem(
        wo_id="W1",
        wo_description="Inspect seal",
        collection="CM",
        primary_code="P",
        primary_code_description="Preventive",
        secondary_code="S",
        secondary_code_description="Seal",
        equipment_id="PUMP1",
        equipment_name="Pump 1",
        preventive=True,
        work_priority=1,
        actual_finish=None,
        duration=None,
        actual_labor_hours=None,
    )
    wo_ok = WorkOrdersResult(
        equipment_id="PUMP1",
        start_date=None,
        end_date=None,
        total=1,
        work_orders=[wo_item],
        message="ok",
    )
    sens = SensorsResult(
        site_name="MAIN",
        asset_id="PUMP1",
        total_sensors=1,
        sensors=["Vibration"],
        message="ok",
    )
    fm = FailureModesResult(asset_name="centrifugal pump", failure_modes=["Seal wear"])

    with (
        patch("servers.iot.main.sensors", return_value=sens),
        patch("servers.fmsr.main.get_failure_modes", return_value=fm),
        patch("servers.wo.tools.get_work_orders", return_value=wo_ok),
    ):
        r = run_pump_seal_inspection_workflow("MAIN", "PUMP1", "centrifugal pump")

    assert r.site_name == "MAIN"
    assert r.asset_id == "PUMP1"
    assert len(r.steps) == 3
    assert r.steps[0].name == "iot_sensors"
    assert r.steps[0].ok is True
    assert r.steps[1].ok is True
    assert r.steps[2].ok is True


def test_workflow_marks_iot_failure():
    fm = FailureModesResult(asset_name="pump", failure_modes=["x"])
    with (
        patch(
            "servers.iot.main.sensors",
            return_value=IoTError(error="no sensors"),
        ),
        patch("servers.fmsr.main.get_failure_modes", return_value=fm),
        patch(
            "servers.wo.tools.get_work_orders",
            return_value=WoError(error="no wo"),
        ),
    ):
        r = run_pump_seal_inspection_workflow("MAIN", "A", "pump")
    assert r.steps[0].ok is False
    assert r.steps[1].ok is True
    assert r.steps[2].ok is False
