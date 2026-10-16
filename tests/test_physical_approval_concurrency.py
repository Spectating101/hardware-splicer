from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from hardware_splicer.physical_approval import PhysicalApprovalStore
from hardware_splicer.physical_authority import PhysicalPlanGrantStore
from hardware_splicer.physical_operator import PhysicalOperatorRegistry, programmer_descriptor

HUMAN = {"kind": "human", "id": "project-owner"}


class Handle:
    def execute(self, plan):
        return {"ok": True}


def test_concurrent_approval_mints_only_one_grant(tmp_path):
    operators = PhysicalOperatorRegistry()
    operators.register(programmer_descriptor(operator_id="probe-1", display_name="Debug Probe"), Handle())
    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    approvals = PhysicalApprovalStore(tmp_path / "approvals", operators=operators, grants=grants)
    plan = operators.plan(
        operator_id="probe-1",
        project_id="fielddeck",
        mission_id="mission-concurrency",
        action="flash",
        payload={"artifact_id": "fw-1", "artifact_sha256": "a" * 64},
    )
    request = approvals.request(plan, requested_by={"kind": "agent", "id": "mission-agent"})

    def approve_once():
        try:
            return ("ok", approvals.approve(request["request_id"], author=HUMAN))
        except Exception as exc:
            return ("error", type(exc).__name__, str(exc))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _i: approve_once(), range(2)))

    assert [item[0] for item in results].count("ok") == 1
    assert [item[0] for item in results].count("error") == 1
    final = approvals.get(request["request_id"])
    assert final["status"] == "approved"
    assert final["grant_id"]
    grant_files = list((tmp_path / "grants").glob("pg-*.json"))
    assert len(grant_files) == 1
