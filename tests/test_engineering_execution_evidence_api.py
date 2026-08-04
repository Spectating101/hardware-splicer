from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.engineering_execution import (
    ExecutionOperation,
    ExecutionResult,
    ExecutionStatus,
    execution_manifest,
)
from hardware_splicer.machine_project_seed import machine_project_from_intake
from hardware_splicer.product_api import create_product_app


def _project() -> dict:
    return machine_project_from_intake(
        {
            "project_name": "execution-api-project",
            "goal": "Retain software verification without physical authority.",
            "available_parts": [{"name": "controller", "type": "controller"}],
        }
    ).model_dump(mode="json")


def _manifest(status: ExecutionStatus) -> dict:
    return execution_manifest(
        ExecutionResult(
            execution_id="pytest-main",
            operation=ExecutionOperation.PYTEST,
            status=status,
            argv=["python", "-m", "pytest", "-q", "tests"],
            workspace="/workspace",
            tool="python",
            tool_available=True,
            returncode=0 if status == ExecutionStatus.PASSED else 1,
            duration_s=1.2,
            metadata={
                "network_authorized": False,
                "device_access_authorized": False,
                "flash_authorized": False,
                "power_on_authorized": False,
                "motion_authorized": False,
            },
        )
    )


def test_product_api_mounts_execution_evidence_route() -> None:
    assert "/v1/engineering/execution/evidence" in set(create_product_app().openapi()["paths"])


def test_passing_execution_evidence_does_not_count_as_physical() -> None:
    response = TestClient(create_product_app()).post(
        "/v1/engineering/execution/evidence",
        json={
            "machine_project": _project(),
            "execution": _manifest(ExecutionStatus.PASSED),
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["software_execution_evidence_count"] == 1
    assert body["physical_evidence_count"] == 0
    assert body["physical_authority_unchanged"] is True
    assert body["flash_authorized"] is False
    assert body["power_on_authorized"] is False
    assert body["motion_authorized"] is False
    assert body["release_assessment"]["achieved_state"] != "operationally_authorized"


def test_failed_execution_is_retained_as_failed_verification() -> None:
    response = TestClient(create_product_app()).post(
        "/v1/engineering/execution/evidence",
        json={
            "machine_project": _project(),
            "execution": _manifest(ExecutionStatus.FAILED),
        },
    )

    assert response.status_code == 200, response.text
    project = response.json()["machine_project"]
    verification = next(
        row
        for row in project["verifications"]
        if row["verification_id"] == "execution-verification-pytest-main"
    )
    assert verification["status"] == "failed"
