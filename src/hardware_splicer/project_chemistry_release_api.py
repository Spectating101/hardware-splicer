"""Project-scoped authoritative release read for saved HS revision."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from .machine_project import MachineProject, ReleaseState, TraceabilityIssue
from .machine_release import assessment_allows
from .project_api import _project_error
from .project_chemistry_release_gate import assess_project_release
from .project_store import ProjectStore


def create_project_chemistry_release_router(store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/v1/projects", tags=["project-release"])

    @router.get("/{project_id}/engineering/release-gate")
    def evaluate_project_release_gate(
        project_id: str,
        revision: int | None = Query(default=None, ge=1),
        requested_state: ReleaseState | None = None,
    ) -> dict[str, Any]:
        try:
            envelope = (
                store.load(project_id, revision=revision)
                if revision is not None
                else store.load_latest_with_recovery(project_id)
            )
            snapshot = envelope["snapshot"]
            raw = snapshot.get("machineProject") or snapshot.get("machine_project")
            if not isinstance(raw, dict):
                raise ValueError("Project lacks a canonical MachineProject")
            project = MachineProject.model_validate(raw)
            if project.project_id != project_id:
                raise ValueError("MachineProject identity mismatch")
            assessment, chemistry = assess_project_release(
                project, snapshot, requested=requested_state,
            )
            current = store.load_latest_with_recovery(project_id)
            historical = int(envelope["revision"]) != int(current["revision"])
            if historical:
                assessment = assessment.model_copy(update={
                    "blockers": [
                        *assessment.blockers,
                        TraceabilityIssue(
                            code="historical_revision_not_authoritative",
                            object_id=project_id,
                            message="Historical revisions cannot authorize current physical work",
                        ),
                    ],
                })
        except Exception as exc:
            raise _project_error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "revision": envelope["revision"],
            "assessment": assessment.model_dump(mode="json"),
            "allowed": assessment_allows(assessment),
            "chemistry_gate": chemistry,
            "uses_persisted_chemistry": True,
            "historical_revision": historical,
            "physical_authority_granted": False,
        }

    return router
