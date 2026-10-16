from __future__ import annotations

from hardware_splicer.physical_fabrication_manifest import physical_fabrication_manifest
from hardware_splicer.product_api import create_product_app


def test_physical_manifest_is_bounded_to_canonical_fabrication_routes():
    manifest = physical_fabrication_manifest(create_product_app())
    assert manifest["task"] == "physical_fabrication"
    agent_ids = manifest["agent_operation_ids"]
    human_ids = manifest["human_only_operation_ids"]
    assert agent_ids
    assert human_ids
    assert set(agent_ids).isdisjoint(human_ids)
    assert all(
        operation["path"].startswith("/v1/fabrication/")
        for operation in manifest["agent_operations"] + manifest["human_only_operations"]
    )


def test_physical_manifest_does_not_tell_agent_it_can_approve_or_mint_authority():
    manifest = physical_fabrication_manifest(create_product_app())
    contract = manifest["authority_contract"]
    assert contract["projection_grants_physical_authority"] is False
    assert contract["agent_can_mint_grants"] is False
    assert contract["agent_can_approve_requests"] is False
    assert contract["agent_can_register_operators"] is False
    assert contract["agent_can_set_endpoints_or_credentials"] is False
    assert contract["agent_can_submit_raw_machine_commands"] is False
    assert contract["automatic_execution"] is False
    assert contract["physical_correctness_after_execution"] == "UNPROVEN"


def test_human_approval_routes_are_not_in_agent_operation_set():
    manifest = physical_fabrication_manifest(create_product_app())
    agent_paths = {operation["path"] for operation in manifest["agent_operations"]}
    human_paths = {operation["path"] for operation in manifest["human_only_operations"]}
    assert "/v1/fabrication/approval-requests/{request_id}/approve" in human_paths
    assert "/v1/fabrication/approval-requests/{request_id}/reject" in human_paths
    assert not any(path.endswith("/approve") or path.endswith("/reject") for path in agent_paths)
