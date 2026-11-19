"""Read-only manifests and assets for project scenes."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIELDDECK_ID = "cyberdeck-real-trial-20261020"
_SCENES = "/v1/scenes"
project_scene_router = APIRouter(tags=["scenes"])
fielddeck_router = APIRouter(prefix=f"{_SCENES}/fielddeck", tags=["scenes"])


def _confined_path(root: Path, relative: str) -> Path | None:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return None
    try:
        resolved = (root / path).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved if resolved.is_relative_to(root) else None


def _manifest(project_id: str) -> dict | None:
    projects = _REPO_ROOT / "projects"
    project = _confined_path(_REPO_ROOT, f"projects/{project_id}")
    if project is None or project.parent != projects or project.name != project_id:
        return None
    path = _confined_path(project, "scene.json")
    if path is None or not path.is_file():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (isinstance(manifest, dict) and manifest.get("schema") == "hardware_splicer.scene_manifest.v1"
            and manifest.get("project_id") == project_id):
        return manifest
    return None


def _scene_asset(project_id: str, revision: str, asset: str, *, legacy: bool = False) -> FileResponse:
    manifest = _manifest(project_id)
    entry = next((row for row in manifest["revisions"] if row["id"] == revision), None) if manifest else None
    if entry is None or (legacy and revision not in {"7", "5"}):
        raise HTTPException(404, "Fielddeck revision not found" if legacy else "Scene revision not found")

    relative = entry.get(asset)
    project = _REPO_ROOT / "projects" / project_id
    prefix = project.relative_to(_REPO_ROOT)
    path = None
    if isinstance(relative, str) and Path(relative).is_relative_to(prefix):
        path = _confined_path(project, str(Path(relative).relative_to(prefix)))
    if path is None or not path.is_file():
        raise HTTPException(404, "Fielddeck scene asset not found" if legacy else "Scene asset not found")
    return FileResponse(path, media_type="model/gltf-binary" if asset == "glb" else "application/json")


@fielddeck_router.get("/{revision}", response_class=FileResponse)
def get_fielddeck_scene(revision: str) -> FileResponse:
    return _scene_asset(_FIELDDECK_ID, revision, "parts", legacy=True)


@fielddeck_router.get("/{revision}/model", response_class=FileResponse)
def get_fielddeck_model(revision: str) -> FileResponse:
    return _scene_asset(_FIELDDECK_ID, revision, "glb", legacy=True)


project_scene_router.include_router(fielddeck_router)


@project_scene_router.get(_SCENES)
def list_scenes() -> list[dict]:
    return [
        {"project_id": manifest["project_id"], "title": manifest["title"],
         "geometry_status": manifest["geometry_status"], "revisions": [row["id"] for row in manifest["revisions"]]}
        for path in sorted((_REPO_ROOT / "projects").glob("*/scene.json"))
        if (manifest := _manifest(path.parent.name)) is not None
    ]


@project_scene_router.get(f"{_SCENES}/{{project_id}}")
def get_scene_manifest(project_id: str) -> dict:
    manifest = _manifest(project_id)
    if manifest is None:
        raise HTTPException(404, "Scene project not found")
    return manifest


@project_scene_router.get(f"{_SCENES}/{{project_id}}/{{revision}}/parts", response_class=FileResponse)
def get_scene_parts(project_id: str, revision: str) -> FileResponse:
    return _scene_asset(project_id, revision, "parts")


@project_scene_router.get(f"{_SCENES}/{{project_id}}/{{revision}}/model", response_class=FileResponse)
def get_scene_model(project_id: str, revision: str) -> FileResponse:
    return _scene_asset(project_id, revision, "glb")
