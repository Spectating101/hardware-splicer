"""Canonical project wiring API backed by the shared headless engine."""
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from .integrations.wireviz import WireVizError
from .project_api import _project_error
from .project_store import ProjectStore
from .project_wiring import assess_project_wiring, list_wiring_assessments, load_wiring_assessment, wiring_bundle
from .wiring_harness import HarnessSpecification


class AssessWiringRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)
    material_assessment_id: str = Field(pattern=r"^materials-[a-f0-9]{32}$")
    specification: HarnessSpecification
    render: bool = Field(default=False, strict=True)


def create_project_wiring_router(store: ProjectStore):
    router = APIRouter(prefix="/v1/projects/{project_id}/wiring", tags=["projects", "wiring"])

    def call(function, *args, **kwargs):
        try:
            return function(store, *args, **kwargs)
        except WireVizError as exc:
            raise HTTPException(status_code=503, detail={"type": "wireviz_unavailable", "message": str(exc)}) from exc
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.post("/assess")
    def assess(project_id: str, request: AssessWiringRequest):
        return call(assess_project_wiring, project_id, **request.model_dump())

    @router.get("")
    def history(project_id: str):
        return call(list_wiring_assessments, project_id)

    @router.get("/{assessment_id}")
    def show(project_id: str, assessment_id: str):
        return call(load_wiring_assessment, project_id, assessment_id)

    @router.get("/{assessment_id}/csv", response_class=Response,
                responses={200: {"content": {"text/csv": {}}}})
    def csv_download(project_id: str, assessment_id: str):
        record = call(load_wiring_assessment, project_id, assessment_id)["assessment"]
        return Response(record["cut_list_csv"], media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{assessment_id}.csv"'})

    @router.get("/{assessment_id}/wireviz", response_class=Response,
                responses={200: {"content": {"application/yaml": {}}}})
    def wireviz_download(project_id: str, assessment_id: str):
        record = call(load_wiring_assessment, project_id, assessment_id)["assessment"]
        return Response(record["wireviz_document"], media_type="application/yaml",
                        headers={"Content-Disposition": f'attachment; filename="{assessment_id}.wireviz"'})

    @router.get("/{assessment_id}/export", response_class=Response,
                responses={200: {"content": {"application/zip": {}}}})
    def export(project_id: str, assessment_id: str):
        record = call(load_wiring_assessment, project_id, assessment_id)["assessment"]
        return Response(wiring_bundle(record), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{assessment_id}.zip"'})

    return router
