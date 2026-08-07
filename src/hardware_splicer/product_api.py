"""Canonical product API composition.

The core engine factory remains in :mod:`hardware_splicer.api`; this module mounts
product-level routers that own durable workspace state, canonical machine and
electrical models, external interchange, runtime capability truth, source-agnostic
engineering planning, manufacturing and mechanical closure, bounded execution,
unified status, revision comparison, scoped physical evidence, review evidence,
semantic bounded-planner selection, and source-blind dual-agent evaluation.
"""

from __future__ import annotations

from fastapi import FastAPI

from .ai_project_conversation_api import create_ai_project_conversation_router
from .ai_project_orchestrator_api import create_ai_project_orchestrator_router
from .ai_project_repair_api import create_ai_project_repair_router
from .ai_project_tool_executor_api import create_ai_project_tool_executor_router
from .api import create_app as create_engine_app
from .capability_api import create_capability_router
from .circuit_json_api import create_circuit_json_router
from .dual_agent_cleanroom_api import create_dual_agent_cleanroom_router
from .electrical_design_api import create_electrical_design_router
from .electrical_interchange_api import create_electrical_interchange_router
from .engineering_action_api import create_engineering_action_router
from .engineering_api import create_engineering_router
from .engineering_execution_api import create_engineering_execution_router
from .engineering_package_api import create_engineering_package_router
from .engineering_package_download_api import (
    create_engineering_package_download_router,
)
from .engineering_revision_api import create_engineering_revision_router
from .engineering_review_api import create_engineering_review_router
from .engineering_review_identity_api import create_engineering_review_identity_router
from .engineering_source_ingestion_api import create_engineering_source_ingestion_router
from .engineering_source_multipart_api import (
    create_engineering_source_multipart_router,
)
from .engineering_source_role_api import create_engineering_source_role_router
from .engineering_status_api import create_engineering_status_router
from .machine_project_api import create_machine_project_router
from .manufacturing_api import create_manufacturing_router
from .mechanical_api import create_mechanical_router
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
    app.include_router(create_semantic_circuit_router())
    app.include_router(create_engineering_router(resolved_store))
    app.include_router(create_engineering_source_ingestion_router(resolved_store))
    app.include_router(create_engineering_source_multipart_router(resolved_store))
    app.include_router(create_source_upload_session_router(resolved_store))
    app.include_router(create_source_storage_operations_router(resolved_store))
    app.include_router(create_stored_source_parser_router(resolved_store))
    app.include_router(create_engineering_source_role_router(resolved_store))
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
    app.include_router(create_mechanical_router())
    app.include_router(create_engineering_execution_router(resolved_store))
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
