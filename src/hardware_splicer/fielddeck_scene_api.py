"""Read-only assets for the Fielddeck display swap preview."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


_FIELDDECK_ROOT = Path(__file__).resolve().parents[2] / "projects" / "cyberdeck-real-trial-20261020"
_FIELDDECK_ASSETS = {
    "7": ("digital_v1/cad/parts.json", "digital_v1/cad/FIELDDECK_7.glb"),
    "5": ("display_swap/parts.json", "display_swap/cad/FIELDDECK_5.glb"),
}
fielddeck_router = APIRouter(prefix="/v1/scenes/fielddeck", tags=["scenes"])


def _fielddeck_asset(revision: str, *, model: bool = False) -> FileResponse:
    assets = _FIELDDECK_ASSETS.get(revision)
    if assets is None:
        raise HTTPException(status_code=404, detail="Fielddeck revision not found")
    path = _FIELDDECK_ROOT / assets[1 if model else 0]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Fielddeck scene asset not found")
    return FileResponse(path, media_type="model/gltf-binary" if model else "application/json")


@fielddeck_router.get("/{revision}", response_class=FileResponse)
def get_fielddeck_scene(revision: str) -> FileResponse:
    return _fielddeck_asset(revision)


@fielddeck_router.get("/{revision}/model", response_class=FileResponse)
def get_fielddeck_model(revision: str) -> FileResponse:
    return _fielddeck_asset(revision, model=True)
