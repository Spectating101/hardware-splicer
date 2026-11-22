"""Read-only manifests and assets for project scenes."""

import json
import logging
import os
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .state_paths import repo_root


_FIELDDECK_ID = "cyberdeck-real-trial-20261020"
_SCENES = "/v1/scenes"
project_scene_router = APIRouter(tags=["scenes"])
fielddeck_router = APIRouter(prefix=f"{_SCENES}/fielddeck", tags=["scenes"])


def _repo_root() -> Path:
    """Project scenes live in a checkout's projects/; an installed package points at one explicitly."""
    return repo_root()


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
    projects = _repo_root() / "projects"
    project = _confined_path(_repo_root(), f"projects/{project_id}")
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


def _scene_asset_path(project_id: str, revision: str, asset: str, *, legacy: bool = False) -> Path:
    manifest = _manifest(project_id)
    entry = next((row for row in manifest["revisions"] if row["id"] == revision), None) if manifest else None
    if entry is None or (legacy and revision not in {"7", "5"}):
        raise HTTPException(404, "Fielddeck revision not found" if legacy else "Scene revision not found")

    relative = entry.get(asset)
    project = _repo_root() / "projects" / project_id
    prefix = project.relative_to(_repo_root())
    path = None
    if isinstance(relative, str) and Path(relative).is_relative_to(prefix):
        path = _confined_path(project, str(Path(relative).relative_to(prefix)))
    if path is None or not path.is_file():
        raise HTTPException(404, "Fielddeck scene asset not found" if legacy else "Scene asset not found")
    return path


def _scene_asset(project_id: str, revision: str, asset: str, *, legacy: bool = False) -> FileResponse:
    path = _scene_asset_path(project_id, revision, asset, legacy=legacy)
    return FileResponse(path, media_type="model/gltf-binary" if asset == "glb" else "application/json")


@fielddeck_router.get("/{revision}", response_class=FileResponse)
def get_fielddeck_scene(revision: str) -> FileResponse:
    return _scene_asset(_FIELDDECK_ID, revision, "parts", legacy=True)


@fielddeck_router.get("/{revision}/model", response_class=FileResponse)
def get_fielddeck_model(revision: str) -> FileResponse:
    return _scene_asset(_FIELDDECK_ID, revision, "glb", legacy=True)


project_scene_router.include_router(fielddeck_router)


def _registered_cases(manifest: dict) -> list[str]:
    """Registered digital cases this scene explicitly declares; a project is never matched by name."""
    cases = manifest.get("registered_cases")
    return [case for case in cases if isinstance(case, str)] if isinstance(cases, list) else []


@project_scene_router.get(_SCENES)
def list_scenes() -> list[dict]:
    return [
        {"project_id": manifest["project_id"], "title": manifest["title"],
         "geometry_status": manifest["geometry_status"], "revisions": [row["id"] for row in manifest["revisions"]],
         "registered_cases": _registered_cases(manifest)}
        for path in sorted((_repo_root() / "projects").glob("*/scene.json"))
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


@project_scene_router.get(f"{_SCENES}/{{project_id}}/records")
def get_scene_records(project_id: str) -> dict:
    """Return the JSON source records a manifest lists inside its own project folder, verbatim."""
    manifest = _manifest(project_id)
    if manifest is None:
        raise HTTPException(404, "Scene project not found")
    project = _repo_root() / "projects" / project_id
    prefix = project.relative_to(_repo_root())
    records = []
    for source in manifest.get("sources") or []:
        relative = source.get("path") if isinstance(source, dict) else None
        if not isinstance(relative, str) or not relative.endswith(".json") or not Path(relative).is_relative_to(prefix):
            continue
        path = _confined_path(project, str(Path(relative).relative_to(prefix)))
        if path is None or not path.is_file():
            records.append({"label": source.get("label"), "path": relative, "status": "missing", "data": None})
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            records.append({"label": source.get("label"), "path": relative, "status": "unreadable", "data": None})
            continue
        records.append({"label": source.get("label"), "path": relative, "status": "read", "data": data})
    return {"project_id": project_id, "records": records}


# ---- Measured fit -----------------------------------------------------------------------------
# The scene's own CAD model, measured: part-to-part interference and clearance, and overall size.
# scene_fit.py runs in the native CAD interpreter (it needs trimesh, scipy and manifold3d); the
# report is cached under the model's and sidecar's hashes, so each revision is measured once.
_fit_locks: dict[str, threading.Lock] = {}
_fit_guard = threading.Lock()


def _fit_lock(key: str) -> threading.Lock:
    with _fit_guard:
        return _fit_locks.setdefault(key, threading.Lock())


def scene_fit_report(glb: Path, parts: Path) -> dict:
    from . import scene_fit
    from .digital_project import native_python
    from .file_digest import sha256_file
    from .state_paths import state_dir

    key = f"{sha256_file(glb)[:24]}-{sha256_file(parts)[:24]}-{scene_fit.VERSION}"
    cache = state_dir() / "scene-fit" / f"{key}.json"
    with _fit_lock(key):
        if cache.is_file():
            try:
                return json.loads(cache.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        try:
            done = subprocess.run(
                [native_python(), "-I", scene_fit.__file__, "--glb", str(glb), "--parts", str(parts)],
                capture_output=True, text=True, timeout=600, check=False,
                env={key_: value for key_, value in os.environ.items() if key_ in {"PATH", "HOME", "LANG", "LC_ALL"}})
            report = json.loads(done.stdout) if done.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired, ValueError):
            report = None
        if report is None:
            logging.getLogger(__name__).warning("scene fit failed for %s", glb.name, exc_info=False)
            raise HTTPException(503, "Fit measurement unavailable: the CAD runtime could not measure this model.")
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(".tmp")
        tmp.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
        os.replace(tmp, cache)
        return report


@project_scene_router.get(f"{_SCENES}/{{project_id}}/{{revision}}/fit")
def get_scene_fit(project_id: str, revision: str) -> dict:
    """Measured interference, clearance and size of one scene revision's CAD model."""
    glb = _scene_asset_path(project_id, revision, "glb")
    parts = _scene_asset_path(project_id, revision, "parts")
    return {"project_id": project_id, "revision": revision, **scene_fit_report(glb, parts)}


# ---- Evidence records and live KiCad checks ---------------------------------------------------

@project_scene_router.get(f"{_SCENES}/{{project_id}}/evidence")
def get_scene_evidence(project_id: str) -> dict:
    """The evidence records a scene manifest lists (strategy, simulation, receipts, tool runs, BOM)."""
    from .scene_evidence import scene_evidence

    manifest = _manifest(project_id)
    if manifest is None:
        raise HTTPException(404, "Scene project not found")
    return {"project_id": project_id, "records": scene_evidence(_repo_root(), manifest)}


def _revision_file(project_id: str, revision: str, field: str) -> Path | None:
    from .scene_evidence import EvidenceError, resolve

    manifest = _manifest(project_id)
    entry = next((row for row in manifest["revisions"] if row["id"] == revision), None) if manifest else None
    if entry is None:
        raise HTTPException(404, "Scene revision not found")
    if not entry.get(field):
        return None
    try:
        return resolve(_repo_root(), entry[field])
    except EvidenceError:
        raise HTTPException(404, "Scene board file not found") from None


def _kicad_report(kind: str, path: Path, out: Path) -> dict | None:
    argv = (["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity"] if kind == "drc"
            else ["kicad-cli", "sch", "erc", "--format", "json", "--severity-all"])
    try:
        subprocess.run([*argv, "-o", str(out), str(path)], capture_output=True, timeout=300, check=False,
                       env={key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL"}})
        return json.loads(out.read_text(encoding="utf-8"))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


@project_scene_router.get(f"{_SCENES}/{{project_id}}/{{revision}}/kicad")
def get_scene_kicad_checks(project_id: str, revision: str) -> dict:
    """KiCad's own DRC and ERC on the revision's board and schematic, each violation traced to parts."""
    import tempfile

    from .file_digest import sha256_file
    from .scene_evidence import summarise_kicad
    from .state_paths import state_dir

    board = _revision_file(project_id, revision, "board")
    schematic = _revision_file(project_id, revision, "schematic")
    if board is None:
        raise HTTPException(404, "This scene revision has no KiCad board")
    key = "-".join(sha256_file(path)[:24] for path in (board, schematic) if path)
    cache = state_dir() / "scene-kicad" / f"{key}.json"
    with _fit_lock(f"kicad-{key}"):
        if cache.is_file():
            try:
                raw = json.loads(cache.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = None
        else:
            raw = None
        if raw is None:
            with tempfile.TemporaryDirectory(prefix="hs-kicad-") as work:
                raw = {"drc": _kicad_report("drc", board, Path(work) / "drc.json"),
                       "erc": _kicad_report("erc", schematic, Path(work) / "erc.json") if schematic else None}
            if raw["drc"] is None:
                raise HTTPException(503, "KiCad checks unavailable: kicad-cli could not check this board.")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(raw), encoding="utf-8")
    project = _repo_root() / "projects" / project_id
    footprints = []
    bom_path = project / "BOM.json"
    if bom_path.is_file():
        try:
            footprints = [{"ref": item["id"], "bbox": item["bbox_kicad_mm"]}
                          for item in json.loads(bom_path.read_text(encoding="utf-8")).get("items", [])
                          if item.get("bbox_kicad_mm")]
        except (OSError, ValueError, KeyError):
            footprints = []
    summary = summarise_kicad(raw["drc"], raw["erc"], footprints)
    # Reference designators → this revision's part ids, so the workspace can select them.
    parts = {}
    parts_path = _scene_asset_path(project_id, revision, "parts")
    for part in json.loads(parts_path.read_text(encoding="utf-8")).get("parts", []):
        parts[part.get("node_name")] = part.get("part_id")
    for report in (summary["drc"], summary["erc"]):
        for row in (report or {}).get("violations", []):
            row["part_ids"] = sorted({parts[ref] for ref in row["parts"] if ref in parts})
            row["net_ids"] = sorted({parts[f"net:{net}"] for net in row.get("nets", []) if f"net:{net}" in parts})
    return {"project_id": project_id, "revision": revision, "board": board.name,
            "schematic": schematic.name if schematic else None, **summary}
