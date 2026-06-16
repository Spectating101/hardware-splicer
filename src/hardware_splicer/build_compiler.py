from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .catalog import CATALOG_BUILD_IDS
from .compile_stages import run_artifact_stage, run_graph_stage_node
from .design_quality import build_design_quality_gate
from .fabrication_inspection import inspect_fabrication_package
from .functional_delivery import build_functional_delivery_score
from .netlist.ir import CircuitNetlist
from .netlist.lower import netlist_to_build_graph
from .runtime import ROOT

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
    "generic_mechatronics": "generic_low_voltage_build",
    "generic_low_voltage_build": "generic_low_voltage_build",
}

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

    graph_stage = run_graph_stage_node(build_id, build_dir, splice_plan=splice_plan)
    if graph_stage.error and not graph_stage.paths.build_graph:
        result = BuildCompileResult(
            ok=False,
            build_id=build_id,
            out_dir=target,
            design_quality=graph_stage.quality,
            build_graph_file=None,
            kicad_pcb_file=None,
            design_quality_file=str(build_dir / "DESIGN_QUALITY.json"),
            error=graph_stage.error,
        )
        write_fabrication_artifacts(target, result.to_dict())
        return result

    artifact = run_artifact_stage(
        build_id=build_id,
        build_dir=build_dir,
        graph_stage=graph_stage,
        resolved_modules=resolved_modules,
        export_gerber=export_gerber,
        export_gerber_fn=_export_gerber_if_possible if export_gerber else None,
    )
    quality = artifact["quality"]
    bom_paths = artifact["bom_paths"]
    gerber_dir = artifact["gerber_dir"]
    kicad_path = graph_stage.paths.kicad_pcb

    fab_zip = _write_fab_package(build_dir, quality, bom_paths, gerber_dir)
    if fab_zip:
        quality["fab_package_zip"] = fab_zip
        quality_path = Path(quality.get("design_quality_file") or build_dir / "DESIGN_QUALITY.json")
        quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")

    ok = graph_stage.ok
    result = BuildCompileResult(
        ok=ok,
        build_id=build_id,
        out_dir=target,
        design_quality=quality,
        build_graph_file=graph_stage.paths.build_graph,
        kicad_pcb_file=kicad_path,
        design_quality_file=quality.get("design_quality_file")
        or graph_stage.paths.design_quality
        or str(build_dir / "DESIGN_QUALITY.json"),
        gerber_package_dir=gerber_dir,
        error=None if ok else _summarize_blockers(quality),
    )
    write_fabrication_artifacts(target, result.to_dict())
    return result


def compile_from_netlist(
    netlist: Mapping[str, Any] | CircuitNetlist,
    out_dir: str | Path,
    *,
    build_id: str = "generic_low_voltage_build",
    export_gerber: bool = True,
) -> BuildCompileResult:
    """Compile netlist IR → ERC → PCB artifacts (general engine entry)."""
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    build_dir = target / "build_compilation"
    build_dir.mkdir(parents=True, exist_ok=True)

    circuit = netlist if isinstance(netlist, CircuitNetlist) else CircuitNetlist.from_dict(netlist)
    graph = netlist_to_build_graph(circuit)
    splice_plan = {
        "custom_graph": graph,
        "target": {"recommended_build_id": build_id},
        "netlist_source": circuit.source,
    }

    graph_stage = run_graph_stage_node(build_id, build_dir, splice_plan=splice_plan)
    artifact = run_artifact_stage(
        build_id=build_id,
        build_dir=build_dir,
        graph_stage=graph_stage,
        export_gerber=export_gerber,
        export_gerber_fn=_export_gerber_if_possible if export_gerber else None,
    )
    quality = artifact["quality"]
    fab_zip = _write_fab_package(build_dir, quality, artifact["bom_paths"], artifact["gerber_dir"])
    if fab_zip:
        quality["fab_package_zip"] = fab_zip
        quality_path = Path(quality.get("design_quality_file") or build_dir / "DESIGN_QUALITY.json")
        quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")

    ok = graph_stage.ok
    result = BuildCompileResult(
        ok=ok,
        build_id=build_id,
        out_dir=target,
        design_quality=quality,
        build_graph_file=graph_stage.paths.build_graph,
        kicad_pcb_file=graph_stage.paths.kicad_pcb,
        design_quality_file=quality.get("design_quality_file")
        or graph_stage.paths.design_quality
        or str(build_dir / "DESIGN_QUALITY.json"),
        gerber_package_dir=artifact["gerber_dir"],
        error=None if ok else (graph_stage.error or _summarize_blockers(quality)),
    )
    write_fabrication_artifacts(target, result.to_dict())
    return result


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


def write_fabrication_artifacts(
    out_dir: str | Path,
    compile_payload: Mapping[str, Any],
    *,
    extra_artifacts: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Write FUNCTIONAL_DELIVERY.json and FABRICATION_INSPECTION.json for a compile tree."""
    out_path = Path(out_dir)
    build_dir = out_path / "build_compilation"
    design_quality = dict(compile_payload.get("design_quality") or {})
    artifact_inputs: Dict[str, Any] = {
        "build_graph": compile_payload.get("build_graph_file"),
        "build_kicad_pcb": compile_payload.get("kicad_pcb_file"),
        "fab_package_zip": design_quality.get("fab_package_zip")
        or (str(build_dir / "fab_package.zip") if (build_dir / "fab_package.zip").is_file() else None),
    }
    if extra_artifacts:
        artifact_inputs.update(dict(extra_artifacts))

    functional = build_functional_delivery_score(
        build_compilation=compile_payload,
        artifacts=artifact_inputs,
    )
    fd_path = out_path / "FUNCTIONAL_DELIVERY.json"
    fd_path.write_text(json.dumps(functional, indent=2), encoding="utf-8")
    inspection = inspect_fabrication_package(
        build_compilation=compile_payload,
        artifacts=artifact_inputs,
    )
    insp_path = out_path / "FABRICATION_INSPECTION.json"
    insp_path.write_text(json.dumps(inspection, indent=2), encoding="utf-8")
    return {
        "functional_delivery": str(fd_path),
        "fabrication_inspection": str(insp_path),
        "functional_delivery_score": functional.get("functional_delivery_score"),
        "honest_fabrication_ready": functional.get("honest_fabrication_ready"),
    }


def merge_fabrication_into_payload(
    payload: Dict[str, Any],
    *,
    compile_payload: Mapping[str, Any] | None = None,
    extra_artifacts: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Persist fabrication artifacts and merge paths/scores into an API payload."""
    out_dir = payload.get("out_dir") or (compile_payload or {}).get("out_dir")
    if not out_dir:
        return payload
    compile_body = dict(compile_payload or {})
    if not compile_body.get("design_quality") and payload.get("design_quality"):
        compile_body = {
            "ok": payload.get("ok"),
            "build_id": payload.get("build_id"),
            "out_dir": out_dir,
            "design_quality": payload.get("design_quality"),
            "build_graph_file": payload.get("build_graph_file"),
            "kicad_pcb_file": payload.get("kicad_pcb_file"),
        }
    compile_result = payload.get("compile_result")
    if isinstance(compile_result, Mapping) and not compile_body.get("design_quality"):
        compile_body = dict(compile_result)

    fab = write_fabrication_artifacts(out_dir, compile_body, extra_artifacts=extra_artifacts)
    out = dict(payload)
    out["functional_delivery"] = {
        "functional_delivery_score": fab.get("functional_delivery_score"),
        "honest_fabrication_ready": fab.get("honest_fabrication_ready"),
    }
    artifacts = dict(out.get("artifacts") or {})
    artifacts["functional_delivery"] = fab["functional_delivery"]
    artifacts["fabrication_inspection"] = fab["fabrication_inspection"]
    out["artifacts"] = artifacts
    return out


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
    graph_input = dict(splice_payload) if isinstance(splice_payload, dict) else {}
    graph_mode = str(
        build_compilation.get("graph_mode") or graph_input.get("graph_mode") or ""
    ).strip().lower()
    goal = str(build_compilation.get("goal") or graph_input.get("goal") or "").strip()
    constraints = dict(build_compilation.get("constraints") or graph_input.get("constraints") or {})
    salvage_mode = bool(
        build_compilation.get("salvage_mode")
        or graph_input.get("compose_from_inventory")
        or graph_mode == "salvage"
    )

    if graph_mode == "scratch":
        from .scratch_pipeline import compile_scratch_build

        scratch = compile_scratch_build(
            out_dir=str(out_dir),
            goal=goal or None,
            resolved_modules=resolved_modules if isinstance(resolved_modules, list) else None,
            export_gerber=export_gerber,
            constraints=constraints,
            salvage_mode=salvage_mode,
        )
        if scratch.compile_result is not None:
            result = scratch.compile_result
        else:
            result = BuildCompileResult(
                ok=False,
                build_id=scratch.build_id,
                out_dir=out_dir,
                design_quality={"build_ready": False, "circuit_readiness": "compile_failed"},
                build_graph_file=None,
                kicad_pcb_file=None,
                design_quality_file=str(out_dir / "build_compilation" / "DESIGN_QUALITY.json"),
                error=scratch.error or "scratch compile failed",
            )
        build_id = scratch.build_id
        payload = result.to_dict()
        payload["graph_mode"] = "scratch"
        payload["scratch_attempts"] = scratch.attempts
        payload["compile_casefile"] = scratch.compile_casefile
    else:
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
    fab = write_fabrication_artifacts(out_dir, payload)
    payload["functional_delivery"] = {
        "functional_delivery_score": fab.get("functional_delivery_score"),
        "honest_fabrication_ready": fab.get("honest_fabrication_ready"),
    }
    payload["fabrication_inspection_path"] = fab.get("fabrication_inspection")
    return payload
