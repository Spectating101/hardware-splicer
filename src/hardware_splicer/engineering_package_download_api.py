"""Verified download route for persisted Engineering Package ZIP files."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Mapping

from fastapi import APIRouter
from fastapi.responses import FileResponse

from .engineering_package import InvalidEngineeringPackage, validate_package_id
from .engineering_package_api import package_api_error, package_rows
from .project_store import ProjectNotFound, ProjectStore, validate_project_id


def _package_by_id(
    packages: list[Dict[str, Any]],
    package_id: str,
) -> Dict[str, Any]:
    for package in packages:
        if str(package.get("package_id") or "") == package_id:
            return package
    raise ProjectNotFound(f"Engineering Package {package_id!r}")


def verified_package_zip(
    store: ProjectStore,
    project_id: str,
    package: Mapping[str, Any],
) -> Path:
    safe_project = validate_project_id(project_id)
    package_id = validate_package_id(str(package.get("package_id") or ""))
    project_dir = (store.root / safe_project).resolve()
    packages_dir = (project_dir / "engineering_packages").resolve()
    zip_path = (packages_dir / f"{package_id}.zip").resolve()
    if project_dir.parent != store.root or packages_dir.parent != project_dir:
        raise InvalidEngineeringPackage("package download root escapes project boundary")
    if zip_path.parent != packages_dir:
        raise InvalidEngineeringPackage("package download path escapes package root")
    if not zip_path.is_file():
        raise ProjectNotFound(f"Engineering Package ZIP {package_id!r}")
    payload = zip_path.read_bytes()
    expected_size = int(package.get("zip_size_bytes") or 0)
    expected_sha = str(package.get("zip_sha256") or "")
    if len(payload) != expected_size:
        raise InvalidEngineeringPackage(
            f"Engineering Package ZIP size mismatch for {package_id}"
        )
    if hashlib.sha256(payload).hexdigest() != expected_sha:
        raise InvalidEngineeringPackage(
            f"Engineering Package ZIP hash mismatch for {package_id}"
        )
    return zip_path


def create_engineering_package_download_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["engineering-package-download"])

    @router.get(
        "/v1/projects/{project_id}/engineering-packages/{package_id}/download"
    )
    def download_package(project_id: str, package_id: str) -> FileResponse:
        try:
            safe_package_id = validate_package_id(package_id)
            envelope = store.load_latest_with_recovery(project_id)
            packages = package_rows(
                envelope["snapshot"].get("engineeringPackages")
            )
            package = _package_by_id(packages, safe_package_id)
            zip_path = verified_package_zip(store, project_id, package)
        except Exception as exc:
            raise package_api_error(exc) from exc
        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename=f"{safe_package_id}.zip",
            headers={
                "X-Hardware-Splicer-Package-Id": safe_package_id,
                "X-Hardware-Splicer-Package-Sha256": str(package["zip_sha256"]),
                "X-Hardware-Splicer-Source-Revision": str(package["source_revision"]),
            },
        )

    return router
