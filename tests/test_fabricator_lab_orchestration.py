from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.fabrication_capability_registry import (
    FabricationCapabilityDescriptor,
    FabricationCapabilityRegistry,
)
from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.fabrication_resource_leases import ResourceLeaseStore, WorkflowPlanRegistry
from hardware_splicer.fabrication_workflow_scheduler import FabricationWorkflowPlanner, FabricationWorkflowTask
from hardware_splicer.fabricator_lab_manifest import fabricator_lab_manifest
from hardware_splicer.fabricator_lab_workbench import FabricatorLabWorkbench
from hardware_splicer.product_api import create_product_app


def _capabilities() -> FabricationCapabilityRegistry:
    registry = FabricationCapabilityRegistry()
    registry.register(FabricationCapabilityDescriptor(
        operator_id="printer-a",
        kind="printer",
        display_name="Printer A",
        capabilities=("additive_fabrication", "pla"),
        limits={"build_x_mm": 220},
    ))
    registry.register(FabricationCapabilityDescriptor(
        operator_id="compiler-a",
        kind="simulator",
        display_name="Firmware compiler",
        capabilities=("firmware_compile",),
        limits={},
    ))
    registry.register(FabricationCapabilityDescriptor(
        operator_id="programmer-a",
        kind="programmer",
        display_name="OpenOCD bench",
        capabilities=("firmware_programming",),
        limits={},
    ))
    registry.register(FabricationCapabilityDescriptor(
        operator_id="meter-a",
        kind="instrument",
        display_name="Bench meter",
        capabilities=("voltage_measurement",),
        limits={},
    ))
    return registry


def _tasks():
    return [
        FabricationWorkflowTask(
            task_id="print-case",
            required_capabilities=("additive_fabrication", "pla"),
            duration_seconds=100,
            kind="printer",
            numeric_minimums={"build_x_mm": 200},
            requires_physical_authority=True,
        ),
        FabricationWorkflowTask(
            task_id="compile-fw",
            required_capabilities=("firmware_compile",),
            duration_seconds=20,
            kind="simulator",
        ),
        FabricationWorkflowTask(
            task_id="flash-fw",
            required_capabilities=("firmware_programming",),
            duration_seconds=30,
            dependencies=("compile-fw",),
            kind="programmer",
            requires_physical_authority=True,
        ),
        FabricationWorkflowTask(
            task_id="measure",
            required_capabilities=("voltage_measurement",),
            duration_seconds=10,
            dependencies=("print-case", "flash-fw"),
            kind="instrument",
        ),
    ]


def test_scheduler_parallelizes_independent_work_and_preserves_authority_boundary():
    planner = FabricationWorkflowPlanner(capabilities=_capabilities())
    plan = planner.plan(workflow_id="logger-build", tasks=_tasks())
    rows = {row["task_id"]: row for row in plan["tasks"]}
    assert rows["print-case"]["start_offset_seconds"] == 0
    assert rows["compile-fw"]["start_offset_seconds"] == 0
    assert rows["flash-fw"]["start_offset_seconds"] == 20
    assert rows["measure"]["start_offset_seconds"] == 100
    assert plan["makespan_seconds"] == 110
    assert plan["complete"] is True
    assert rows["print-case"]["physical_authority_granted"] is False
    assert rows["flash-fw"]["physical_authority_granted"] is False
    assert plan["resource_allocation_grants_physical_authority"] is False
    assert plan["plan_id"].startswith("wp-") and len(plan["plan_sha256"]) == 64


def test_scheduler_blocks_unsatisfied_capability_and_downstream_task():
    planner = FabricationWorkflowPlanner(capabilities=_capabilities())
    tasks = [
        FabricationWorkflowTask("mill-panel", ("five_axis_milling",), 30, kind="cnc"),
        FabricationWorkflowTask("inspect-panel", ("voltage_measurement",), 10, dependencies=("mill-panel",), kind="instrument"),
    ]
    plan = planner.plan(workflow_id="blocked", tasks=tasks)
    assert plan["complete"] is False
    blockers = {row["task_id"]: row["type"] for row in plan["blockers"]}
    assert blockers == {"mill-panel": "no_matching_resource", "inspect-panel": "dependency_unallocated"}


def test_scheduler_rejects_dependency_cycles():
    planner = FabricationWorkflowPlanner(capabilities=_capabilities())
    with pytest.raises(FabricationValidationError, match="cycle"):
        planner.plan(
            workflow_id="cycle",
            tasks=[
                FabricationWorkflowTask("a", ("firmware_compile",), 1, dependencies=("b",)),
                FabricationWorkflowTask("b", ("firmware_compile",), 1, dependencies=("a",)),
            ],
        )


def test_plan_bound_lease_prevents_concurrent_claim_and_token_is_not_public():
    planner = FabricationWorkflowPlanner(capabilities=_capabilities())
    plan = planner.plan(workflow_id="logger-build", tasks=_tasks())
    plans = WorkflowPlanRegistry()
    plans.register(plan)
    leases = ResourceLeaseStore(plans=plans)
    acquired = leases.acquire(
        plan_id=plan["plan_id"],
        task_id="print-case",
        holder_id="agent-a",
        ttl_seconds=300,
    )
    lease = acquired["lease"]
    assert acquired["lease_token"].startswith("lt-")
    assert "lease_token" not in lease
    assert lease["grants_physical_authority"] is False
    assert lease["physical_execution_authorized"] is False
    public = leases.list_public()
    assert len(public) == 1 and "lease_token" not in public[0]
    with pytest.raises(FabricationValidationError, match="already leased"):
        leases.acquire(
            plan_id=plan["plan_id"],
            task_id="print-case",
            holder_id="agent-b",
            ttl_seconds=300,
        )
    with pytest.raises(FabricationValidationError, match="token"):
        leases.release(lease["lease_id"], lease_token="lt-wrong")
    released = leases.release(lease["lease_id"], lease_token=acquired["lease_token"])
    assert released["released"] is True
    assert leases.list_public() == []


def test_stale_lease_expires_and_resource_becomes_available():
    planner = FabricationWorkflowPlanner(capabilities=_capabilities())
    plan = planner.plan(workflow_id="logger-build", tasks=_tasks())
    plans = WorkflowPlanRegistry()
    plans.register(plan)
    leases = ResourceLeaseStore(plans=plans)
    start = datetime(2026, 10, 17, 0, 0, tzinfo=timezone.utc)
    leases.acquire(
        plan_id=plan["plan_id"],
        task_id="print-case",
        holder_id="agent-a",
        ttl_seconds=30,
        now=start,
    )
    assert leases.list_public(now=start + timedelta(seconds=31)) == []


def test_canonical_lab_surface_fails_closed_and_manifest_never_equates_lease_with_authority():
    client = TestClient(create_product_app())
    assert client.get("/v1/fabricator/lab/resources").status_code == 503
    manifest = fabricator_lab_manifest(create_product_app())
    assert manifest["authority_contract"]["schedule_grants_physical_authority"] is False
    assert manifest["authority_contract"]["lease_grants_physical_authority"] is False
    assert manifest["authority_contract"]["lease_starts_machine"] is False


def test_configured_lab_api_plans_and_leases_exact_scheduled_resource():
    workbench = FabricatorLabWorkbench(capabilities=_capabilities())
    client = TestClient(create_product_app(fabricator_lab_workbench=workbench))
    response = client.post(
        "/v1/fabricator/lab/workflows",
        json={
            "workflow_id": "simple",
            "tasks": [
                {
                    "task_id": "print-case",
                    "required_capabilities": ["additive_fabrication", "pla"],
                    "duration_seconds": 60,
                    "kind": "printer",
                    "requires_physical_authority": True,
                }
            ],
        },
    )
    assert response.status_code == 201
    plan = response.json()["plan"]
    assert plan["tasks"][0]["resource_id"] == "printer-a"
    lease_response = client.post(
        f"/v1/fabricator/lab/workflows/{plan['plan_id']}/tasks/print-case/lease",
        json={"holder_id": "planner-agent", "ttl_seconds": 60},
    )
    assert lease_response.status_code == 201
    payload = lease_response.json()
    assert payload["lease"]["resource_id"] == "printer-a"
    assert payload["lease"]["physical_execution_authorized"] is False
    assert payload["lease_token"].startswith("lt-")
