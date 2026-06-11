from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .bom_generator import build_bom_from_graph, write_bom_artifacts
from .design_quality import build_design_quality_gate
from .runtime import ROOT


COMPILE_SCRIPT = ROOT / "scripts" / "compile_build_graph.cjs"
FRONTEND_ROOT = ROOT / "apps" / "circuit-ai" / "circuit-ai-frontend"

ARCHETYPE_BUILD_IDS: Dict[str, str] = {
    "automatic_watering": "automatic_plant_watering",
    "automatic_plant_watering": "automatic_plant_watering",
    "rover": "robot_drive_base",
    "mobile_robotics_platform": "robot_drive_base",
    "airflow_controller": "usb_fume_extractor",
    "pan_tilt": "inspection_motion_fixture",
    "stationary_pan_tilt_module": "inspection_motion_fixture",
    "gripper": "low_voltage_motor_test_jig",
    "sensor_logger": "sensor_logger",
    "bench_power_adapter": "bench_power_adapter",
    "inspection_fixture": "inspection_motion_fixture",
    "generic_mechatronics": "sensor_logger",
}

CATALOG_BUILD_IDS: List[str] = [
    "automatic_plant_watering",
    "bench_power_adapter",
    "camera_ir_light_or_sensor_mount",
    "indicator_or_task_light",
    "inspection_motion_fixture",
    "low_voltage_motor_test_jig",
    "network_status_indicator",
    "plotter_motion_stage",
    "robot_drive_base",
    "salvaged_input_panel",
    "sensor_logger",
    "small_audio_amp_box",
    "smart_relay_box",
    "usb_fume_extractor",
    "usb_uart_debug_adapter",
]


@dataclass(frozen=True)
class BuildCompileResult:
    ok: bool
    build_id: str
    out_dir: Path
    design_quality: Dict[str, Any]
    build_graph_file: Optional[str]
    kicad_pcb_file: Optional[str]
    design_quality_file: str
    gerber_package_dir: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "build_id": self.build_id,
            "out_dir": str(self.out_dir),
            "design_quality": self.design_quality,
            "build_graph_file": self.build_graph_file,
            "kicad_pcb_file": self.kicad_pcb_file,
            "design_quality_file": self.design_quality_file,
            "gerber_package_dir": self.gerber_package_dir,
            "error": self.error,
        }


def resolve_build_id(*, archetype: str | None = None, explicit: str | None = None) -> str | None:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    if archetype:
        return ARCHETYPE_BUILD_IDS.get(str(archetype).strip())
    return None


def _node_available() -> bool:
    return shutil.which("node") is not None


def compile_catalog_build(
    build_id: str,
    out_dir: str | Path,
    *,
    export_gerber: bool = True,
    splice_plan: Mapping[str, Any] | None = None,
    resolved_modules: List[Mapping[str, Any]] | None = None,
) -> BuildCompileResult:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    build_dir = target / "build_compilation"
    build_dir.mkdir(parents=True, exist_ok=True)

    if not COMPILE_SCRIPT.is_file():
        return BuildCompileResult(
            ok=False,
            build_id=build_id,
            out_dir=target,
            design_quality={"build_ready": False, "circuit_readiness": "compiler_missing"},
            build_graph_file=None,
            kicad_pcb_file=None,
            design_quality_file=str(build_dir / "DESIGN_QUALITY.json"),
            error=f"compile script missing: {COMPILE_SCRIPT}",
        )

    if not _node_available():
        return BuildCompileResult(
            ok=False,
            build_id=build_id,
            out_dir=target,
            design_quality={"build_ready": False, "circuit_readiness": "node_missing"},
            build_graph_file=None,
            kicad_pcb_file=None,
            design_quality_file=str(build_dir / "DESIGN_QUALITY.json"),
            error="node is not available on PATH",
        )

    splice_plan_path: str | None = None
    if splice_plan:
        splice_input = build_dir / "splice_plan_input.json"
        splice_input.write_text(json.dumps(dict(splice_plan), indent=2), encoding="utf-8")
        splice_plan_path = str(splice_input)

    node_argv = [
        "node",
        str(COMPILE_SCRIPT),
        "--build-id",
        build_id,
        "--out",
        str(build_dir),
        "--json",
    ]
    if splice_plan_path:
        node_argv.extend(["--splice-plan", splice_plan_path])

    proc = subprocess.run(
        node_argv,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=120,
    )
    if proc.returncode not in {0, 1} or not proc.stdout.strip():
        tail = (proc.stderr or proc.stdout or "build compile failed").strip()
        return BuildCompileResult(
            ok=False,
            build_id=build_id,
            out_dir=target,
            design_quality={"build_ready": False, "circuit_readiness": "compile_failed"},
            build_graph_file=None,
            kicad_pcb_file=None,
            design_quality_file=str(build_dir / "DESIGN_QUALITY.json"),
            error=tail[-2000:],
        )

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return BuildCompileResult(
            ok=False,
            build_id=build_id,
            out_dir=target,
            design_quality={"build_ready": False, "circuit_readiness": "invalid_compiler_output"},
            build_graph_file=None,
            kicad_pcb_file=None,
            design_quality_file=str(build_dir / "DESIGN_QUALITY.json"),
            error=str(exc),
        )

    quality = dict(payload.get("quality") or {})
    paths = dict(payload.get("paths") or {})
    kicad_path = paths.get("kicad_pcb")
    gerber_dir: str | None = None

    build_graph_path = paths.get("build_graph")
    bom_paths: Dict[str, str] = {}
    if build_graph_path and Path(build_graph_path).is_file():
        graph = json.loads(Path(build_graph_path).read_text(encoding="utf-8"))
        bom = build_bom_from_graph(graph, resolved_modules=list(resolved_modules or []))
        bom_paths = write_bom_artifacts(bom, build_dir)
        quality["bom_ready"] = bool(bom.get("line_count"))

    if export_gerber and kicad_path and Path(kicad_path).is_file():
        gerber_dir = _export_gerber_if_possible(Path(kicad_path), build_dir)
        if gerber_dir:
            quality["gerber_ready"] = True
            quality["gerber_package_dir"] = gerber_dir
        else:
            quality["gerber_ready"] = False

    fab_zip = _write_fab_package(build_dir, quality, bom_paths, gerber_dir)
    if fab_zip:
        quality["fab_package_zip"] = fab_zip

    quality_path = Path(paths.get("design_quality") or build_dir / "DESIGN_QUALITY.json")
    quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")

    ok = bool(payload.get("ok"))
    return BuildCompileResult(
        ok=ok,
        build_id=build_id,
        out_dir=target,
        design_quality=quality,
        build_graph_file=paths.get("build_graph"),
        kicad_pcb_file=kicad_path,
        design_quality_file=paths.get("design_quality") or str(build_dir / "DESIGN_QUALITY.json"),
        gerber_package_dir=gerber_dir,
        error=None if ok else _summarize_blockers(quality),
    )


def _write_fab_package(
    build_dir: Path,
    quality: Dict[str, Any],
    bom_paths: Dict[str, str],
    gerber_dir: str | None,
) -> str | None:
    try:
        zip_path = build_dir / "fab_package.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in ("DESIGN_QUALITY.json", "build_graph.json", "main_ctrl_build.kicad_pcb"):
                candidate = build_dir / name
                if candidate.is_file():
                    archive.write(candidate, arcname=name)
            for path in bom_paths.values():
                candidate = Path(path)
                if candidate.is_file():
                    archive.write(candidate, arcname=candidate.name)
            if gerber_dir:
                gerber_root = Path(gerber_dir)
                for file in gerber_root.rglob("*"):
                    if file.is_file():
                        archive.write(file, arcname=f"gerbers/{file.relative_to(gerber_root)}")
            readme = build_dir / "FAB_README.txt"
            readme.write_text(
                "\n".join(
                    [
                        "Hardware-Splicer fabrication package",
                        f"build_id: {quality.get('build_id')}",
                        f"build_ready: {quality.get('build_ready')}",
                        f"fabrication_ready: {quality.get('fabrication_ready')}",
                        f"gerber_ready: {quality.get('gerber_ready')}",
                        "",
                        "Upload gerbers/ to your PCB house; verify BOM before ordering modules.",
                    ]
                ),
                encoding="utf-8",
            )
            archive.write(readme, arcname="FAB_README.txt")
        return str(zip_path)
    except Exception:
        return None


def _export_gerber_if_possible(kicad_path: Path, out_dir: Path) -> str | None:
    try:
        ensure_circuit_import_path()
        from src.engines.gerber_generator import GerberGenerator

        generator = GerberGenerator()
        package = generator.generate_gerber_package(str(kicad_path))
        if str(package.get("export_method") or "") != "kicad-cli":
            return None
        target = out_dir / "gerber_package"
        target.mkdir(parents=True, exist_ok=True)
        for layer in package.get("gerber_files") or []:
            filename = getattr(layer, "filename", None) or (layer.get("filename") if isinstance(layer, dict) else None)
            content = getattr(layer, "content", None) or (layer.get("content") if isinstance(layer, dict) else "")
            if filename:
                (target / str(filename)).write_text(str(content), encoding="utf-8")
        zip_path = str(target / "gerber_package.zip")
        generator.create_gerber_zip(package, zip_path)
        return str(target)
    except Exception:
        return None


def ensure_circuit_import_path() -> None:
    circuit_root = ROOT / "apps" / "circuit-ai"
    import sys

    circuit_src = str(circuit_root)
    if circuit_src not in sys.path:
        sys.path.insert(0, circuit_src)


def apply_board_outline_to_machine(
    machine: Mapping[str, Any],
    design_quality: Mapping[str, Any],
) -> Dict[str, Any]:
    """Sync compiled PCB outline into machine.boards for mecha/geometry coupling."""
    outline = design_quality.get("board_outline") or {}
    width = outline.get("width_mm")
    height = outline.get("height_mm")
    if width is None or height is None:
        return dict(machine)

    updated = dict(machine)
    boards = [dict(row) for row in (updated.get("boards") or [])]
    if not boards:
        boards = [{"board_id": "main_ctrl", "name": "main_ctrl"}]
    board = dict(boards[0])
    board["pcb_outline_mm"] = [float(width), float(height), 1.6]
    boards[0] = board
    updated["boards"] = boards
    return updated


def _summarize_blockers(quality: Dict[str, Any]) -> str:
    parts: List[str] = []
    if not quality.get("build_graph_compiled"):
        parts.append("build graph was not compiled")
    if not quality.get("electrical_safety_pass"):
        parts.append("electrical safety errors present")
    if not quality.get("drc_pass"):
        parts.append(f"DRC errors: {quality.get('drc_errors', '?')}")
    warnings = quality.get("warnings") or []
    if warnings:
        parts.append(str(warnings[0]))
    return "; ".join(parts) or "build not ready"


def attach_build_compilation_artifacts(
    spec_dict: Dict[str, Any],
    out_dir: Path,
    *,
    export_gerber: bool = True,
) -> Dict[str, Any]:
    machine = dict(spec_dict.get("machine") or {})
    build_compilation = dict(machine.get("build_compilation") or spec_dict.get("build_compilation") or {})
    if not build_compilation.get("enabled", True):
        return {"skipped": True, "reason": "build_compilation_disabled"}

    build_id = resolve_build_id(
        archetype=str(build_compilation.get("archetype") or ""),
        explicit=str(build_compilation.get("build_id") or ""),
    )
    if not build_id:
        return {"skipped": True, "reason": "no_build_id"}

    splice_payload = build_compilation.get("graph_input") or build_compilation.get("splice_package")
    resolved_modules = build_compilation.get("resolved_modules") or []
    result = compile_catalog_build(
        build_id,
        out_dir,
        export_gerber=export_gerber,
        splice_plan=splice_payload if isinstance(splice_payload, dict) else None,
        resolved_modules=resolved_modules if isinstance(resolved_modules, list) else None,
    )
    payload = result.to_dict()
    design_quality = dict(payload.get("design_quality") or {})
    if design_quality.get("drc_pass") and design_quality.get("electrical_safety_pass"):
        design_quality["compiler_verified"] = True
        payload["design_quality"] = design_quality
    payload["design_quality_gate"] = build_design_quality_gate(design_quality)
    if result.kicad_pcb_file and Path(result.kicad_pcb_file).is_file():
        outline = dict(result.design_quality.get("board_outline") or {})
        payload["board_design_attachment"] = {
            "board_id": "main_ctrl",
            "path": result.kicad_pcb_file,
            "kind": "kicad_pcb",
            "source": "build_compiler",
            "build_id": build_id,
            "board_outline": outline,
        }
    return payload
