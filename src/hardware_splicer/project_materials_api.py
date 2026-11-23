"""Canonical HTTP adapter for the shared project material-assessment engine."""
from fastapi import APIRouter, HTTPException, Response
from pydantic import Field

from .integrations.inventree import InvenTreeError
from .project_api import _project_error
from .project_materials import (
    InventoryCapture, MaterialModel, MaterialRequirement, assess_project_materials,
    import_inventree_materials, list_material_assessments, load_material_assessment, material_csv,
)
from .project_store import ProjectStore


class AssessMaterialsRequest(MaterialModel):
    expected_revision: int = Field(ge=1, strict=True)
    requirements: list[MaterialRequirement] = Field(min_length=1, max_length=500)
    inventory: InventoryCapture


class ImportInvenTreeRequest(MaterialModel):
    expected_revision: int = Field(ge=1, strict=True)
    assembly_part_id: int = Field(ge=1, strict=True)
    build_quantity: int = Field(default=1, ge=1, le=100, strict=True)


def create_project_materials_router(store: ProjectStore):
    router = APIRouter(prefix="/v1/projects/{project_id}/materials", tags=["projects", "materials"])

    def call(function, *args, **kwargs):
        try:
            return function(store, *args, **kwargs)
        except InvenTreeError as exc:
            raise HTTPException(status_code=503, detail={"type": "inventree_unavailable", "message": str(exc)}) from exc
        except Exception as exc:
            raise _project_error(exc) from exc

    @router.post("/assess")
    def assess(project_id: str, request: AssessMaterialsRequest):
        return call(assess_project_materials, project_id, **request.model_dump())

    @router.post("/import-inventree")
    def import_inventory(project_id: str, request: ImportInvenTreeRequest):
        return call(import_inventree_materials, project_id, **request.model_dump())

    @router.get("")
    def history(project_id: str):
        return call(list_material_assessments, project_id)

    @router.get("/{assessment_id}")
    def show(project_id: str, assessment_id: str):
        return call(load_material_assessment, project_id, assessment_id)

    @router.get("/{assessment_id}/csv", response_class=Response,
                responses={200: {"content": {"text/csv": {}}}})
    def csv_download(project_id: str, assessment_id: str):
        result = call(load_material_assessment, project_id, assessment_id)
        return Response(material_csv(result["assessment"]), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{assessment_id}.csv"'})

    return router
