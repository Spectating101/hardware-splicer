"""Revisioned API for deterministic Engineering Package creation and listing."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .engineering_package import (
    ENGINEERING_PACKAGE_MANIFEST_SCHEMA,
    ENGINEERING_PACKAGE_RECORD_SCHEMA,
    ENGINEERING_PACKAGE_SCHEMA,
    EngineeringPackageError,
    InvalidEngineeringPackage,
    build_engineering_package,
)
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class EngineeringPackageAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateEngineeringPackageRequest(EngineeringPackageAPIModel):
    expected_revision: int = Field(ge=1)


def package_api_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, ProjectNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "engineering_package_not_found", "message": str(exc)},
        )
    if isinstance(exc, RevisionConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "engineering_package_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, InvalidEngineeringPackage):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_engineering_package", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (ProjectStoreError, EngineeringPackageError)):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "engineering_package_error", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_engineering_package_request", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "engineering_package_error", "message": str(exc)},
    )


def package_rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def package_for_revision(
    packages: list[Dict[str, Any]],
    source_revision: int,
) -> Dict[str, Any] | None:
    return next(
        (
            package
            for package in packages
            if int(package.get("source_revision") or 0) == int(source_revision)
        ),
        None,
    )


def create_engineering_package_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["engineering-package"])

    @router.get("/v1/engineering/packages/schema")
    def package_schema() -> Dict[str, Any]:
        return {
            "schema_version": ENGINEERING_PACKAGE_SCHEMA,
            "manifest_schema": ENGINEERING_PACKAGE_MANIFEST_SCHEMA,
            "record_schema": ENGINEERING_PACKAGE_RECORD_SCHEMA,
            "deterministic_zip": True,
            "content_addressed_identity": True,
            "file_sha256_manifest": True,
            "raw_source_bytes_included": False,
            "package_authority_effect": "none",
            "physical_authority_unchanged": True,
            "package_authorizes_physical_action": False,
        }

    @router.get("/v1/projects/{project_id}/engineering-packages")
    def list_packages(project_id: str) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            packages = package_rows(
                envelope["snapshot"].get("engineeringPackages")
            )
        except Exception as exc:
            raise package_api_error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "revision": envelope["revision"],
            "packages": packages,
            "package_count": len(packages),
        }

    @router.post("/v1/projects/{project_id}/engineering-packages")
    def create_package(
        project_id: str,
        request: CreateEngineeringPackageRequest,
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            snapshot = deepcopy(envelope["snapshot"])
            packages = package_rows(snapshot.get("engineeringPackages"))
            existing = package_for_revision(packages, request.expected_revision)
            if existing is not None:
                return {
                    "ok": True,
                    "project_id": project_id,
                    "revision": current_revision,
                    "package": existing,
                    "idempotent": True,
                    "authority_unchanged": True,
                }
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )

            package = build_engineering_package(
                store,
                project_id,
                current_revision,
                snapshot,
                source_saved_at=str(envelope.get("saved_at") or ""),
            )
            packages.append(package)
            snapshot["engineeringPackages"] = packages
            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "engineering_package_export",
                    "engineering_package_id": package["package_id"],
                    "engineering_package_source_revision": current_revision,
                    "engineering_package_snapshot_sha256": package["snapshot_sha256"],
                    "engineering_package_manifest_sha256": package["manifest_sha256"],
                    "engineering_package_zip_sha256": package["zip_sha256"],
                    "raw_source_bytes_included": False,
                    "package_authority_effect": "none",
                    "physical_authority_unchanged": True,
                },
            )
        except Exception as exc:
            raise package_api_error(exc) from exc

        return {
            "ok": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "package": package,
            "idempotent": False,
            "authority_unchanged": True,
        }

    return router
