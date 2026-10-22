"""External engineering-engine orchestration (opt-in, local-only, never release).

HS owns the task graph and proof manifest. SolidCraft/FreeCAD/atopile/tscircuit
own their native computations. No commands from a model or HTTP payload run.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA = "hardware_splicer.external_engine_plan.v1"
REPORT_SCHEMA = "hardware_splicer.external_engine_execution.v1"
ENGINES = {
    "solidcraft": {"bin": "solidcraft-cli", "operations": ("run_script",),
                   "source_ext": (".json",), "domain": "mechanical",
                   "upstream": "https://github.com/tangency-labs/solidcraft",
                   "license": "MIT OR Apache-2.0"},
    "freecad": {"bin": "FreeCADCmd", "alternates": ("freecadcmd",),
                "operations": ("inspect_step",), "source_ext": (".step", ".stp"),
                "domain": "mechanical",
                "upstream": "https://github.com/FreeCAD/FreeCAD",
                "license": "LGPL-2.0-or-later"},
    "atopile": {"bin": "ato", "operations": ("build",),
                "source_ext": (".ato",), "domain": "electronics",
                "upstream": "https://github.com/atopile/atopile",
                "license": "MIT"},
    "tscircuit": {"bin": "tsci", "operations": ("build", "check"),
                  "source_ext": (".tsx", ".ts"),
                  "domain": "electronics",
                  "upstream": "https://github.com/tscircuit/cli",
                  "license": "MIT"},
}
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_MAX_SOURCE = 5_000_000
_MAX_ARTIFACT = 32_000_000
_MAX_TASKS = 12
_EXTENSION = {".step", ".stp", ".json", ".kicad_pcb", ".kicad_sch",
              ".csv", ".svg", ".pdf", ".stl", ".gbr", ".drl"}


class EnginePlanError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _relative_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or len(value) > 240:
        raise EnginePlanError(f"invalid {label} path")
    candidate = Path(value)
    if (candidate.is_absolute() or
            any(component in {"..", ".", ""} for component in candidate.parts)):
        raise EnginePlanError(f"{label} must be a relative path inside workspace")
    return candidate


def _contained(root: Path, relative: Path, *, existing: bool = True) -> Path:
    untrusted = root / relative
    if any((root / Path(*relative.parts[:n])).is_symlink()
           for n in range(1, len(relative.parts) + 1)):
        raise EnginePlanError("symlinked source or artifact path is not allowed")
    target = untrusted.resolve()
    if not target.is_relative_to(root.resolve()):
        raise EnginePlanError("file escapes declared workspace")
    if existing and not target.is_file():
        raise EnginePlanError("required source file missing")
    return target


def validate_plan(plan: Mapping[str, Any]) -> dict:
    if not isinstance(plan, Mapping) or plan.get("schema") != SCHEMA:
        raise EnginePlanError("unsupported external-engine plan")
    ident = plan.get("id")
    if not isinstance(ident, str) or not _ID.fullmatch(ident):
        raise EnginePlanError("invalid plan id")
    raw_tasks = plan.get("tasks")
    if not isinstance(raw_tasks, list) or not 1 <= len(raw_tasks) <= _MAX_TASKS:
        raise EnginePlanError("plan requires 1-12 tasks")
    tasks = []
    seen = set()
    for raw in raw_tasks:
        if not isinstance(raw, Mapping):
            raise EnginePlanError("task must be a mapping")
        if set(raw) - {"id", "engine", "operation", "source", "source_task", "depends_on", "artifact_paths"}:
            raise EnginePlanError("unsupported task key")
        tid, engine, op = raw.get("id"), raw.get("engine"), raw.get("operation")
        if not isinstance(tid, str) or not _ID.fullmatch(tid) or tid in seen:
            raise EnginePlanError("invalid or duplicate task id")
        if engine not in ENGINES or op not in ENGINES[engine]["operations"]:
            raise EnginePlanError("unsupported external engine operation")
        source_from = raw.get("source_task")
        if source_from is not None:
            if engine != "freecad" or op != "inspect_step" or source_from not in seen:
                raise EnginePlanError("only FreeCAD STEP inspection may consume a preceding task output")
            parent = next(item for item in tasks if item["id"] == source_from)
            if parent["engine"] != "solidcraft" or parent["operation"] != "run_script":
                raise EnginePlanError("FreeCAD source task must be SolidCraft's STEP export")
            if raw.get("source") is not None:
                raise EnginePlanError("cannot specify source and source_task together")
            source = None
        else:
            source = _relative_path(raw.get("source"), "source")
            if source.suffix.lower() not in ENGINES[engine]["source_ext"]:
                raise EnginePlanError("source extension incompatible with selected tool")
        deps = raw.get("depends_on", [])
        if not isinstance(deps, list) or len(set(deps)) != len(deps) or any(dep not in seen for dep in deps):
            raise EnginePlanError("dependencies must refer to preceding tasks (acyclic order)")
        if source_from is not None and source_from not in deps:
            deps = [*deps, source_from]
        artifact_paths = raw.get("artifact_paths", [])
        if not isinstance(artifact_paths, list) or len(artifact_paths) > 12:
            raise EnginePlanError("too many expected artifacts")
        artifacts = [_relative_path(p, "artifact") for p in artifact_paths]
        if any(path.suffix.lower() not in _EXTENSION for path in artifacts):
            raise EnginePlanError("unsupported output artifact extension")
        if engine in {"atopile", "tscircuit"} and not artifacts:
            raise EnginePlanError("electronics tasks must declare expected native output artifacts")
        tasks.append({"id": tid, "engine": engine, "operation": op,
                      "source": source.as_posix() if source is not None else None,
                      "source_task": source_from, "depends_on": list(deps),
                      "artifact_paths": [p.as_posix() for p in artifacts]})
        seen.add(tid)
    return {"schema": SCHEMA, "id": ident, "tasks": tasks}


def discover_engines() -> dict:
    rows = []
    for name, info in ENGINES.items():
        which = next((shutil.which(item) for item in (info["bin"], *info.get("alternates", ()))
                      if shutil.which(item)), None)
        rows.append({"id": name, "domain": info["domain"], "operations": list(info["operations"]),
                     "source_extensions": list(info["source_ext"]),
                     "upstream": info["upstream"], "license": info["license"],
                     "available": which is not None, "executable": which,
                     "execution_mode": "local_explicit_operator_opt_in"})
    return {"schema": "hardware_splicer.external_engine_registry.v1",
            "engines": rows,
            "physical_authority": False}


def preview_engine_plan(plan: Mapping[str, Any]) -> dict:
    valid = validate_plan(plan)
    detected = {p["id"]: p for p in discover_engines()["engines"]}
    return {"schema": "hardware_splicer.external_engine_preview.v1",
            "plan_id": valid["id"],
            "tasks": [{**task, "engine_available": detected[task["engine"]]["available"],
                       "status": "ready_for_local_opt_in" if detected[task["engine"]]["available"]
                       else "blocked_missing_external_engine"}
                      for task in valid["tasks"]],
            "executes_external_code": False, "execution_authorized": False,
            "fabrication_authorized": False, "power_on_authorized": False,
            "release_authorized": False}


def _freecad_inspection_script(source: Path, result: Path) -> str:
    # No user-provided Python is executed. This fixed template reads only the
    # declared STEP file. json.dumps safely encodes both paths as literals.
    return (
        "import json, Part, FreeCAD\n"
        "shape=Part.Shape()\n"
        f"shape.read({json.dumps(str(source))})\n"
        "bb=shape.BoundBox\n"
        "record={'shape_valid':bool(shape.isValid()),"
        "'solid_count':len(shape.Solids),'volume_mm3':float(shape.Volume),"
        "'bbox_mm':[float(bb.XLength),float(bb.YLength),float(bb.ZLength)]}\n"
        f"open({json.dumps(str(result))},'w').write(json.dumps(record))\n"
        "print(json.dumps(record))\n"
    )


def run_external_engine_plan(plan: Mapping[str, Any], *, workspace: str | Path,
                             output_dir: str | Path, confirm_execute: bool = False,
                             timeout_s: int = 120) -> dict:
    """Run external CLIs only from a local operator-authorized Python caller."""
    valid = validate_plan(plan)
    if not confirm_execute:
        raise EnginePlanError("external executable invocation requires explicit operator opt-in")
    if not isinstance(timeout_s, int) or not 1 <= timeout_s <= 600:
        raise EnginePlanError("invalid external runtime budget")
    root = Path(workspace).resolve(strict=True)
    if not root.is_dir():
        raise EnginePlanError("workspace must be a directory")
    out = Path(output_dir).resolve()
    if out == root or out.is_relative_to(root) or root.is_relative_to(out):
        raise EnginePlanError("artifacts and source workspace must be separate directories")
    if out.exists() and any(out.iterdir()):
        raise EnginePlanError("output directory must be empty")
    # Preflight all source paths before executing any provider.
    sources: dict[str, Path] = {}
    for item in valid["tasks"]:
        if item["source_task"] is not None:
            continue
        source = _contained(root, Path(item["source"]))
        if source.stat().st_size > _MAX_SOURCE:
            raise EnginePlanError("external source file exceeds size ceiling")
        sources[item["id"]] = source
    out.mkdir(parents=True, exist_ok=True)
    results = []
    states = {}
    discovered = {row["id"]: row for row in discover_engines()["engines"]}
    for task in valid["tasks"]:
        ident, engine, operation = task["id"], task["engine"], task["operation"]
        dependency_failures = [dep for dep in task["depends_on"] if states.get(dep) != "tool_passed_artifact_observed"]
        if dependency_failures:
            row = {"id": ident, "engine": engine, "status": "blocked_dependency",
                   "blocked_by": dependency_failures}
        elif not discovered[engine]["available"]:
            row = {"id": ident, "engine": engine, "status": "blocked_missing_external_engine"}
        else:
            binary = str(discovered[engine]["executable"])
            task_dir = out / ident
            task_dir.mkdir(exist_ok=False)
            src = ((out / task["source_task"] / "model.step").resolve()
                   if task["source_task"] is not None else sources[ident])
            if engine == "solidcraft":
                # Immutable authored CAD recipe, separate model export and results.
                model = task_dir / "model.step"
                evidence = task_dir / "results.json"
                cmd = [binary, "run", str(src), "--out", str(model),
                       "--json-out", str(evidence)]
                required = [model, evidence]
            elif engine == "freecad":
                evidence = task_dir / "step_inspection.json"
                worker = task_dir / "inspect_step.py"
                worker.write_text(_freecad_inspection_script(src, evidence), encoding="utf-8")
                cmd = [binary, str(worker)]
                required = [evidence]
            else:
                cmd = [binary, operation]
                required = []
            try:
                # Native electronics commands discover project config from
                # their local entrypoint directory, not the HS root.
                native_cwd = src.parent if engine in {"atopile", "tscircuit"} else root
                # A native tool may leave last run's outputs in the project.
                # Capture their generation times to reject stale artifacts.
                prior_outputs = {}
                for rel in task["artifact_paths"]:
                    target = _contained(root, Path(rel), existing=False)
                    prior_outputs[str(target)] = (
                        target.stat().st_mtime_ns if target.is_file() else None
                    )
                completed = subprocess.run(cmd, cwd=str(native_cwd), capture_output=True,
                                           text=True, timeout=timeout_s, check=False,
                                           env={**os.environ, "CI": "1"})
                status = "executed" if completed.returncode == 0 else "blocked_tool_error"
                diag = (completed.stdout[-1500:] + "\n" + completed.stderr[-1500:]).strip()[-2200:]
                exit_code = completed.returncode
            except (subprocess.TimeoutExpired, OSError) as exc:
                status, diag, exit_code = "blocked_execution_failure", type(exc).__name__, None
            artifacts = []
            if status == "executed":
                requested = []
                for rel in task["artifact_paths"]:
                    file = _contained(root, Path(rel), existing=False)
                    requested.append(file)
                for file in required + requested:
                    if not file.is_file() or file.is_symlink() or file.stat().st_size == 0 or file.stat().st_size > _MAX_ARTIFACT:
                        status = "blocked_missing_or_invalid_output"
                        break
                    if (str(file) in prior_outputs and prior_outputs[str(file)] is not None
                            and file.stat().st_mtime_ns <= prior_outputs[str(file)]):
                        status = "blocked_stale_project_artifact"
                        break
                    if file == (task_dir / "model.step") and not file.read_bytes()[:100].lstrip().startswith(b"ISO-10303-21;"):
                        status = "blocked_not_step_export"
                        break
                    blob = file.read_bytes()
                    artifacts.append({"path": str(file.relative_to(out)) if file.is_relative_to(out)
                                      else task["source"] if file == src else file.relative_to(root).as_posix(),
                                      "sha256": _sha(blob), "size_bytes": len(blob)})
                if not required and not requested:
                    status = "blocked_no_output_evidence"
                elif status == "executed":
                    status = "tool_passed_artifact_observed"
            row = {"id": ident, "engine": engine, "operation": operation, "status": status,
                   "exit_code": exit_code, "command_identity": info_bin_name(binary),
                   "diagnostic_tail": diag, "artifacts": artifacts,
                   "physical_validation_performed": False}
        states[ident] = row["status"]
        results.append(row)
    report = {"schema": REPORT_SCHEMA, "plan_id": valid["id"],
              "plan_sha256": _sha(_canonical(valid)), "tasks": results,
              "completed": sum(r["status"] == "tool_passed_artifact_observed" for r in results),
              "blocked": sum(r["status"] != "tool_passed_artifact_observed" for r in results),
              "source_evidence_authenticated": False,
              "electrical_operation_verified": False,
              "exact_mechanical_assembly_verified": False,
              "fabrication_authorized": False, "power_on_authorized": False,
              "release_authorized": False}
    (out / "ENGINE_ORCHESTRATION_REPORT.json").write_bytes(_canonical(report))
    return report


def info_bin_name(path: str) -> str:
    return Path(path).name
