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
from .electrical_design_api import create_electrical_design_router
from .electrical_interchange_api import create_electrical_interchange_router
from .engineering_action_api import create_engineering_action_router
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
from .machine_project_api import create_machine_project_router
from .manufacturing_api import create_manufacturing_router
from .mechanical_api import create_mechanical_router
from .mechanical_brep_adapter_api import create_mechanical_brep_adapter_router
from .mechanical_brep_anchor_api import create_mechanical_brep_anchor_router
from .mechanical_brep_mating_api import create_mechanical_brep_mating_router
from .mechanical_brep_mesh_api import create_mechanical_brep_mesh_router
from .mechanical_brep_sweep_api import create_mechanical_brep_sweep_router
from .physical_evidence_api import create_physical_evidence_router
from .physical_evidence_attested_api import create_physical_evidence_attested_router
from .physical_evidence_hash_api import create_physical_evidence_hash_router
from .physical_evidence_persistence_api import create_physical_evidence_persistence_router
from .project_api import create_project_router
from .project_compatibility import CompatibleProjectStore
from .project_engineering_plan_api import create_project_engineering_plan_router
from .project_store import ProjectStore
from .semantic_circuit_api import create_semantic_circuit_router
from .source_conflict_api import create_source_conflict_router
from .source_storage_operations_api import create_source_storage_operations_router
from .source_upload_session_api import create_source_upload_session_router
from .stored_source_parser_api import create_stored_source_parser_router
from .workbench_anchor_intent_api import create_workbench_anchor_intent_router
from .workbench_placement_api import create_workbench_placement_router
from .workbench_step_binding_api import create_workbench_step_binding_router


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


def create_product_app(project_store: ProjectStore | None = None) -> FastAPI:
    """Build the canonical user-facing API with all product route families."""

    resolved_store = project_store or CompatibleProjectStore()
    app = create_engine_app()
    app.state.project_store = resolved_store
    app.include_router(create_project_router(resolved_store))
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
    app.include_router(create_engineering_source_role_router(resolved_store))
    app.include_router(create_workbench_step_binding_router(resolved_store))
    app.include_router(create_workbench_placement_router(resolved_store))
    app.include_router(create_workbench_anchor_intent_router(resolved_store))
    app.include_router(create_project_engineering_plan_router(resolved_store))
    app.include_router(create_ai_project_orchestrator_router(resolved_store))
    app.include_router(create_dual_agent_cleanroom_router(resolved_store))
    app.include_router(create_ai_project_tool_executor_router(resolved_store))
    app.include_router(create_ai_project_repair_router(resolved_store))
    app.include_router(create_ai_project_conversation_router(resolved_store))
    app.include_router(create_engineering_package_router(resolved_store))
    app.include_router(create_engineering_package_download_router(resolved_store))
    app.include_router(create_engineering_action_router())
    app.include_router(create_manufacturing_router())
    app.include_router(create_mechanical_router(resolved_store))
    app.include_router(create_mechanical_brep_mesh_router(resolved_store))
    app.include_router(create_mechanical_brep_anchor_router(resolved_store))
    app.include_router(create_mechanical_brep_mating_router())
    app.include_router(create_mechanical_brep_sweep_router(resolved_store))
    app.include_router(create_mechanical_brep_adapter_router(resolved_store))
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
