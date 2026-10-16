"""Canonical product API composition.

The core engine factory remains in :mod:`hardware_splicer.api`; this module mounts
product-level routers that own durable workspace state, canonical machine and
electrical models, external interchange, runtime capability truth, capability reuse,
source-agnostic engineering planning, manufacturing and mechanical closure, bounded
execution, unified status, revision comparison, scoped physical evidence, review
evidence, semantic bounded-planner selection, and source-blind dual-agent evaluation.
"""

from __future__ import annotations

from fastapi import FastAPI

from .ai_project_conversation_api import create_ai_project_conversation_router
from .ai_project_orchestrator_api import create_ai_project_orchestrator_router
from .ai_project_repair_api import create_ai_project_repair_router
from .ai_project_tool_executor_api import create_ai_project_tool_executor_router
from .api import create_app as create_engine_app
from .capability_api import create_capability_router
from .capability_reuse_api import create_capability_reuse_router
from .circuit_json_api import create_circuit_json_router
from .dual_agent_cleanroom_api import create_dual_agent_cleanroom_router
from .document_evidence_api import create_document_evidence_router
from .electrical_design_api import create_electrical_design_router
from .electrical_interchange_api import create_electrical_interchange_router
from .engineering_action_api import create_engineering_action_router
from .engineering_assurance_api import create_engineering_assurance_router
from .engineering_api import create_engineering_router
from .engineering_execution_anchored_api import (
    _SAVE_PATH as ENGINEERING_EXECUTION_SAVE_PATH,
    create_engineering_execution_router,
)
from .engineering_package_api import create_engineering_package_router
from .engineering_package_download_api import create_engineering_package_download_router
from .engineering_revision_api import create_engineering_revision_router
from .engineering_review_api import create_engineering_review_router
from .engineering_review_identity_api import create_engineering_review_identity_router
from .engineering_source_ingestion_api import create_engineering_source_ingestion_router
from .engineering_source_multipart_api import create_engineering_source_multipart_router
from .engineering_source_role_api import create_engineering_source_role_router
from .engineering_status_api import create_engineering_status_router
from .fabricator_digital_thread_api import create_fabricator_digital_thread_router
from .fabricator_digital_thread_workbench import FabricatorDigitalThreadWorkbench
from .fabricator_integration_api import create_fabricator_integration_router
from .fabricator_integration_workbench import FabricatorIntegrationWorkbench
from .fabricator_intelligence_api import create_fabricator_intelligence_router
from .fabricator_intelligence_workbench import FabricatorIntelligenceWorkbench
from .fabricator_validation_api import create_fabricator_validation_router
from .fabricator_validation_workbench import FabricatorValidationWorkbench
from .machine_project_api import create_machine_project_router
from .manufacturing_api import create_manufacturing_router
from .mechanical_api import create_mechanical_router
from .physical_evidence_api import create_physical_evidence_router
from .physical_evidence_attested_api import create_physical_evidence_attested_router
from .physical_evidence_hash_api import create_physical_evidence_hash_router
from .physical_evidence_persistence_api import create_physical_evidence_persistence_router
from .artifact_retention import install_at_save_retention
from .project_api import create_project_router
from .project_artifact_api import create_project_artifact_router
from .project_candidates_api import create_project_candidates_router
from .project_review_packet_api import create_project_review_packet_router
from .device_api import create_device_router
from .donor_api import create_donor_router
from .parts_lookup_api import create_parts_lookup_router
from .project_assembly_api import create_project_assembly_router
from .project_model3d_api import create_project_model3d_router
from .project_parts_api import create_project_parts_router
from .project_findings_api import create_project_findings_router
from .project_compatibility import CompatibleProjectStore
from .project_engineering_plan_api import create_project_engineering_plan_router
from .project_pre_fabrication_plan_api import create_project_pre_fabrication_plan_router
from .project_physical_validation_api import create_project_physical_validation_router
from .project_store import ProjectStore
from .project_events_api import create_project_events_router
from .mission_api import create_mission_router
from .mission_store import MissionStore
from .physical_operator_api import create_physical_operator_router
from .physical_workbench import AgentPhysicalWorkbench
from .project_thread_api import create_project_thread_router
from .project_thread_store import ProjectThreadStore
from .semantic_circuit_api import create_semantic_circuit_router
from .source_conflict_api import create_source_conflict_router
from .source_storage_operations_api import create_source_storage_operations_router
from .source_upload_session_api import create_source_upload_session_router
from .stored_source_parser_api import create_stored_source_parser_router


def _include_anchored_execution_surface(app: FastAPI, store: ProjectStore) -> None:
    """Mount execution routes and guarantee one anchored persistence path on the app."""
    router = create_engineering_execution_router(store)
    app.include_router(router)
    existing = [
        route
        for route in app.routes
        if getattr(route, "path", None) == ENGINEERING_EXECUTION_SAVE_PATH
    ]
    if existing:
        return

    anchored = [
        route
        for route in router.routes
        if getattr(route, "path", None) == ENGINEERING_EXECUTION_SAVE_PATH
    ]
    if len(anchored) != 1:
        raise RuntimeError(
            "anchored execution persistence route is missing from its canonical router"
        )
    route = anchored[0]
    app.add_api_route(
        ENGINEERING_EXECUTION_SAVE_PATH,
        route.endpoint,
        methods=sorted(getattr(route, "methods", None) or {"POST"}),
        tags=["engineering", "execution"],
        name=getattr(route, "name", None) or "ingest_and_save_evidence",
    )


def create_product_app(
    project_store: ProjectStore | None = None,
    physical_workbench: AgentPhysicalWorkbench | None = None,
    fabricator_workbench: FabricatorIntegrationWorkbench | None = None,
    fabricator_digital_thread_workbench: FabricatorDigitalThreadWorkbench | None = None,
    fabricator_intelligence_workbench: FabricatorIntelligenceWorkbench | None = None,
    fabricator_validation_workbench: FabricatorValidationWorkbench | None = None,
) -> FastAPI:
    """Build the canonical user-facing API with all product route families."""

    resolved_store = install_at_save_retention(project_store or CompatibleProjectStore())
    app = create_engine_app()
    app.state.project_store = resolved_store
    # Physical routes are always discoverable, but fail closed with 503 until a
    # server-owned runtime is configured. No machine endpoint/credential is
    # inferred from mission or agent input.
    app.state.physical_workbench = physical_workbench
    # Fabricator integration routes follow the same fail-closed rule. Tool paths,
    # machine URLs and registered project/job roots live only in server runtime.
    app.state.fabricator_workbench = fabricator_workbench
    # Digital-thread routes expose retained artifact ids and bounded transforms,
    # never raw paths/endpoints/credentials. They also fail closed until injected.
    app.state.fabricator_digital_thread_workbench = fabricator_digital_thread_workbench
    # Intelligence routes consume retained observations/provider-owned quotes;
    # no supplier quote ingestion or physical-evidence promotion is agent-facing.
    app.state.fabricator_intelligence_workbench = fabricator_intelligence_workbench
    # Validation procedures/criteria and evidence resolution are server-owned;
    # agents can list frozen procedures and evaluate retained evidence ids only.
    app.state.fabricator_validation_workbench = fabricator_validation_workbench
    app.include_router(create_project_router(resolved_store))
    app.include_router(create_project_artifact_router(resolved_store))
    app.include_router(create_project_model3d_router(resolved_store))
    app.include_router(create_project_assembly_router(resolved_store))
    app.include_router(create_device_router())
    app.include_router(create_donor_router())
    app.include_router(create_parts_lookup_router())
    app.include_router(create_project_parts_router(resolved_store))
    app.include_router(create_project_candidates_router(resolved_store))
    app.include_router(create_project_review_packet_router(resolved_store))
    app.include_router(create_project_thread_router(ProjectThreadStore(resolved_store)))
    app.include_router(create_mission_router(MissionStore(resolved_store)))
    app.include_router(create_physical_operator_router())
    app.include_router(create_fabricator_integration_router())
    app.include_router(create_fabricator_digital_thread_router())
    app.include_router(create_fabricator_intelligence_router())
    app.include_router(create_fabricator_validation_router())
    app.include_router(create_project_events_router(resolved_store))
    app.include_router(create_project_findings_router(resolved_store))
    app.include_router(create_machine_project_router())
    app.include_router(create_electrical_design_router())
    app.include_router(create_circuit_json_router())
    app.include_router(create_electrical_interchange_router())
    app.include_router(create_capability_router())
    app.include_router(create_capability_reuse_router())
    app.include_router(create_semantic_circuit_router())
    app.include_router(create_engineering_router(resolved_store))
    app.include_router(create_engineering_source_ingestion_router(resolved_store))
    app.include_router(create_engineering_source_multipart_router(resolved_store))
    app.include_router(create_source_upload_session_router(resolved_store))
    app.include_router(create_source_storage_operations_router(resolved_store))
    app.include_router(create_stored_source_parser_router(resolved_store))
    app.include_router(create_document_evidence_router(resolved_store))
    app.include_router(create_engineering_source_role_router(resolved_store))
    app.include_router(create_project_engineering_plan_router(resolved_store))
    app.include_router(create_project_pre_fabrication_plan_router(resolved_store))
    app.include_router(create_project_physical_validation_router(resolved_store))
    app.include_router(create_engineering_assurance_router(resolved_store))
    app.include_router(create_ai_project_orchestrator_router(resolved_store))
    app.include_router(create_dual_agent_cleanroom_router(resolved_store))
    app.include_router(create_ai_project_tool_executor_router(resolved_store))
    app.include_router(create_ai_project_repair_router(resolved_store))
    app.include_router(create_ai_project_conversation_router(resolved_store))
    app.include_router(create_engineering_package_router(resolved_store))
    app.include_router(create_engineering_package_download_router(resolved_store))
    app.include_router(create_engineering_action_router())
    app.include_router(create_manufacturing_router())
    app.include_router(create_mechanical_router())
    _include_anchored_execution_surface(app, resolved_store)
    app.include_router(create_engineering_status_router())
    app.include_router(create_engineering_revision_router(resolved_store))
    app.include_router(create_physical_evidence_router())
    app.include_router(create_physical_evidence_hash_router())
    app.include_router(create_physical_evidence_attested_router())
    app.include_router(create_physical_evidence_persistence_router(resolved_store))
    app.include_router(create_source_conflict_router())
    app.include_router(create_engineering_review_router())
    app.include_router(create_engineering_review_identity_router())
    return app


app = create_product_app()
