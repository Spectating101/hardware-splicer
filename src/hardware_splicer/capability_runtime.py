"""Canonical runtime and project-use capability truth.

A catalog entry, an installed executable, a configured adapter, a compatible
version, a successful machine run, and use on the current project are different
facts. This module reports them separately so product copy and workflow guidance
cannot collapse "supported" into an unsupported readiness claim.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence

from .integrations.engineering_review import discover_kicad_happy
from .integrations.oss_catalog import OSS_CATALOG
from .runtime import ROOT

SCHEMA_VERSION = "hardware_splicer.capability_report.v1"

WhichFn = Callable[[str], str | None]
RunFn = Callable[..., Any]
DiscoverFn = Callable[..., Mapping[str, Any]]

_INTERNAL_CAPABILITIES: list[dict[str, Any]] = [
    {
        "id": "project-compatibility",
        "layer": "project",
        "name": "Durable project compatibility",
        "status": "core",
        "priority": "core",
        "license": "MIT",
        "hook": "CompatibleProjectStore",
        "claim": "Deterministic legacy-envelope migration and future-schema refusal",
        "implementation_path": "src/hardware_splicer/project_compatibility.py",
    },
    {
        "id": "electrical-interchange",
        "layer": "interchange",
        "name": "Canonical electrical interchange identity",
        "status": "core",
        "priority": "P0",
        "license": "MIT",
        "hook": "POST /v1/interchange/circuit-json/electrical-design",
        "claim": "Source component, port, net, trace, and KiCad aliases mapped to canonical electrical IDs",
        "implementation_path": "src/hardware_splicer/electrical_interchange.py",
    },
    {
        "id": "manufacturing-reconciliation",
        "layer": "package",
        "name": "Manufacturing reconciliation",
        "status": "core",
        "priority": "P0",
        "license": "MIT",
        "hook": "PROJECT_PACKAGE manufacturing_reconciliation",
        "claim": "Build-graph and BOM quantity contradictions block packaging",
        "implementation_path": "src/hardware_splicer/manufacturing_reconciliation.py",
    },
    {
        "id": "cadquery-isolated",
        "layer": "mechanical",
        "name": "Isolated generated CadQuery execution",
        "status": "core",
        "priority": "P0",
        "license": "MIT",
        "hook": "3D-Splicer generated CAD worker",
        "claim": "Generated Python runs in a bounded subprocess, not the API process",
        "implementation_path": "apps/3d-splicer/src/core/cadquery_generator.py",
        "python_module": "cadquery",
    },
    {
        "id": "platformio",
        "layer": "firmware",
        "name": "PlatformIO",
        "status": "opt_in",
        "priority": "P1",
        "license": "Apache-2.0",
        "hook": "Optional firmware project and compile adapter",
        "claim": "Firmware compile backend; compile success does not authorize flashing or operation",
        "commands": ["pio", "platformio"],
        "version_args": ["--version"],
    },
]

_BUILT_IN_PATHS: dict[str, str] = {
    "capability-studio": "apps/splice-ui/public/capability-studio.html",
    "kicanvas": "apps/splice-ui/src/components/DesignPreviewPanel.jsx",
    "circuit-json": "src/hardware_splicer/integrations/circuit_json_import.py",
    "compose-canvas": "src/hardware_splicer/api.py",
    "kicad-mcp": "scripts/kicad_mcp_dev_profile.sh",
    "kibot": "src/hardware_splicer/integrations/kibot_reference.py",
    "jlc-api": "src/hardware_splicer/integrations/jlcsearch_client.py",
    "skidl": "src/hardware_splicer/integrations",
    "atopile": "docs/ATOPILE_IMPORT.md",
}

_COMMAND_PROBES: dict[str, dict[str, Any]] = {
    "kicad-cli": {"commands": ["kicad-cli"], "args": ["--version"], "min_major": 9},
    "freerouting": {"commands": ["freerouting"], "args": ["--version"]},
    "kibot": {"commands": ["kibot"], "args": ["--version"]},
    "ibom": {
        "commands": ["generate_interactive_bom.py", "InteractiveHtmlBom"],
        "args": ["--version"],
    },
    "pcbdraw": {"commands": ["pcbdraw"], "args": ["--version"]},
    "kikit": {"commands": ["kikit"], "args": ["--version"]},
    "easyeda2kicad": {"commands": ["easyeda2kicad"], "args": ["--version"]},
    "esphome": {"commands": ["esphome"], "args": ["version"]},
    "nopscadlib": {"commands": ["openscad"], "args": ["--version"]},
}

_PYTHON_PROBES: dict[str, str] = {
    "build123d": "build123d",
    "cadquery-isolated": "cadquery",
}

_PROJECT_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "kicad-cli": (
        "build_compilation/**/*DRC*.json",
        "build_compilation/**/*ERC*.json",
        "build_compilation/**/*drc*.json",
        "build_compilation/**/*erc*.json",
    ),
    "kicad-happy": ("build_compilation/ENGINEERING_REVIEW.json",),
    "circuit-json": (
        "build_compilation/**/*circuit*json*.json",
        "build_compilation/**/*CIRCUIT*JSON*.json",
    ),
    "manufacturing-reconciliation": ("PROJECT_PACKAGE.json",),
    "platformio": (
        "firmware/**/.pio/build/**/*",
        "build_compilation/firmware/**/*",
    ),
    "ibom": ("build_compilation/exports/**/*ibom*", "build_compilation/exports/**/*.html"),
    "pcbdraw": ("build_compilation/exports/**/*pcbdraw*", "build_compilation/exports/**/*.svg"),
    "kikit": ("build_compilation/exports/kikit/**/*",),
    "easyeda2kicad": ("build_compilation/exports/lcsc_lib/**/*",),
    "cadquery-isolated": ("mechanical/**/*.stl", "mechanical/**/*.step", "mechanical/**/*.stp"),
}

_RUNTIME_FREE_IDS = {
    "capability-studio",
    "kicanvas",
    "circuit-json",
    "compose-canvas",
    "kicad-mcp",
    "skidl",
    "atopile",
    "project-compatibility",
    "electrical-interchange",
    "manufacturing-reconciliation",
}


def _definitions() -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in [*OSS_CATALOG, *_INTERNAL_CAPABILITIES]:
        capability_id = str(row.get("id") or "").strip()
        if not capability_id:
            continue
        by_id[capability_id] = {**by_id.get(capability_id, {}), **dict(row)}
    return [by_id[key] for key in sorted(by_id)]


def _version_text(result: Any) -> str | None:
    stdout = str(getattr(result, "stdout", "") or "").strip()
    stderr = str(getattr(result, "stderr", "") or "").strip()
    text = stdout or stderr
    return text.splitlines()[0].strip() if text else None


def _major(version: str | None) -> int | None:
    if not version:
        return None
    match = re.search(r"(?<!\d)(\d+)(?:\.\d+)", version)
    return int(match.group(1)) if match else None


def _run_version(
    executable: str,
    args: Sequence[str],
    *,
    run: RunFn,
) -> tuple[str | None, str | None]:
    try:
        result = run(
            [executable, *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
        )
    except Exception as exc:  # capability diagnostics must not break the product
        return None, f"version_probe_failed:{type(exc).__name__}"
    if int(getattr(result, "returncode", 1)) != 0:
        return _version_text(result), f"version_probe_exit:{getattr(result, 'returncode', None)}"
    return _version_text(result), None


def _command_runtime(
    probe: Mapping[str, Any],
    *,
    which: WhichFn,
    run: RunFn,
) -> dict[str, Any]:
    executable: str | None = None
    selected_name: str | None = None
    for name in probe.get("commands") or []:
        found = which(str(name))
        if found:
            executable = found
            selected_name = str(name)
            break
    if not executable:
        return {
            "discovered": False,
            "configured": False,
            "compatible": None,
            "path": None,
            "version": None,
            "probe_error": None,
        }

    version, probe_error = _run_version(
        executable,
        list(probe.get("args") or ["--version"]),
        run=run,
    )
    compatible: bool | None = None
    minimum = probe.get("min_major")
    if minimum is not None:
        parsed = _major(version)
        compatible = parsed is not None and parsed >= int(minimum)
    elif probe_error is None:
        compatible = True

    return {
        "discovered": True,
        "configured": True,
        "compatible": compatible,
        "path": executable,
        "command": selected_name,
        "version": version,
        "probe_error": probe_error,
    }


def _python_runtime(module: str) -> dict[str, Any]:
    discovered = importlib.util.find_spec(module) is not None
    version: str | None = None
    if discovered:
        try:
            version = importlib.metadata.version(module)
        except importlib.metadata.PackageNotFoundError:
            version = None
    return {
        "discovered": discovered,
        "configured": discovered,
        "compatible": True if discovered else None,
        "path": None,
        "module": module,
        "version": version,
        "probe_error": None,
    }


def _artifact_rows(build_dir: Path | None, patterns: Iterable[str]) -> list[Path]:
    if build_dir is None:
        return []
    rows: dict[str, Path] = {}
    for pattern in patterns:
        for candidate in build_dir.glob(pattern):
            if candidate.is_file():
                rows[str(candidate.resolve())] = candidate.resolve()
    return sorted(rows.values(), key=lambda path: str(path))


def _artifact_success(path: Path) -> bool:
    if path.suffix.lower() != ".json":
        return True
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(payload, Mapping):
        return True
    if payload.get("ok") is True:
        return True
    status = str(
        payload.get("status")
        or payload.get("review_status")
        or payload.get("verdict")
        or ""
    ).strip().lower()
    return status in {
        "success",
        "succeeded",
        "completed",
        "clear",
        "blocked",
        "review_required",
        "partial",
        "power_on_authorized",
    }


def _project_evidence(capability_id: str, build_dir: Path | None) -> dict[str, Any]:
    artifacts = _artifact_rows(build_dir, _PROJECT_ARTIFACTS.get(capability_id, ()))
    successful = [path for path in artifacts if _artifact_success(path)]
    latest = max(successful, key=lambda path: path.stat().st_mtime) if successful else None
    return {
        "machine_tested": bool(successful),
        "project_used": bool(artifacts),
        "last_successful_run": (
            datetime.fromtimestamp(latest.stat().st_mtime, timezone.utc).isoformat()
            if latest
            else None
        ),
        "artifacts": [str(path) for path in artifacts[:20]],
    }


def _kicad_happy_runtime(discover: DiscoverFn) -> dict[str, Any]:
    try:
        row = dict(discover())
    except Exception as exc:
        return {
            "discovered": False,
            "configured": False,
            "compatible": None,
            "path": None,
            "version": None,
            "probe_error": f"discovery_failed:{type(exc).__name__}",
        }
    available = bool(row.get("available"))
    return {
        "discovered": available,
        "configured": available,
        "compatible": True if available else None,
        "path": row.get("root"),
        "version": row.get("revision"),
        "capabilities": list(row.get("capabilities") or []),
        "missing_capabilities": list(row.get("missing_capabilities") or []),
        "probe_error": None,
    }


def _special_runtime(
    capability_id: str,
    *,
    environ: Mapping[str, str],
    which: WhichFn,
    run: RunFn,
    discover: DiscoverFn,
) -> dict[str, Any] | None:
    if capability_id == "kicad-happy":
        return _kicad_happy_runtime(discover)
    if capability_id == "freerouting":
        jar = str(environ.get("HARDWARE_SPLICER_FREEROUTING_JAR") or "").strip()
        if jar:
            path = Path(jar).expanduser()
            return {
                "discovered": path.is_file(),
                "configured": True,
                "compatible": True if path.is_file() else False,
                "path": str(path),
                "version": None,
                "probe_error": None if path.is_file() else "configured_jar_missing",
            }
    if capability_id == "tscircuit-autorouter":
        command = str(environ.get("HARDWARE_SPLICER_TSCIRCUIT_AUTOROUTER_CMD") or "").strip()
        package = ROOT / "node_modules" / "@tscircuit" / "capacity-autorouter"
        discovered = bool(command and which(command)) or package.exists()
        return {
            "discovered": discovered,
            "configured": bool(command) or package.exists(),
            "compatible": True if discovered else None,
            "path": which(command) if command else (str(package) if package.exists() else None),
            "version": None,
            "probe_error": None,
        }
    if capability_id == "jlc-api":
        enabled = str(environ.get("HARDWARE_SPLICER_JLC_ENRICH") or "0") == "1"
        return {
            "discovered": True,
            "configured": enabled,
            "compatible": True,
            "path": None,
            "version": None,
            "probe_error": None,
        }
    return None


def _runtime_for(
    definition: Mapping[str, Any],
    *,
    environ: Mapping[str, str],
    which: WhichFn,
    run: RunFn,
    discover: DiscoverFn,
) -> dict[str, Any]:
    capability_id = str(definition["id"])
    special = _special_runtime(
        capability_id,
        environ=environ,
        which=which,
        run=run,
        discover=discover,
    )
    if special is not None:
        return special

    probe = _COMMAND_PROBES.get(capability_id)
    if probe:
        return _command_runtime(probe, which=which, run=run)
    if definition.get("commands"):
        return _command_runtime(
            {
                "commands": definition.get("commands"),
                "args": definition.get("version_args") or ["--version"],
            },
            which=which,
            run=run,
        )

    module = _PYTHON_PROBES.get(capability_id) or definition.get("python_module")
    if module:
        return _python_runtime(str(module))

    implementation_path = (
        definition.get("implementation_path")
        or _BUILT_IN_PATHS.get(capability_id)
    )
    implementation_exists = bool(
        implementation_path and (ROOT / str(implementation_path)).exists()
    )
    if capability_id in _RUNTIME_FREE_IDS or implementation_path:
        return {
            "discovered": implementation_exists,
            "configured": implementation_exists,
            "compatible": True if implementation_exists else None,
            "path": str((ROOT / str(implementation_path)).resolve()) if implementation_exists else None,
            "version": None,
            "probe_error": None,
        }

    return {
        "discovered": False,
        "configured": False,
        "compatible": None,
        "path": None,
        "version": None,
        "probe_error": None,
    }


def _readiness(
    definition: Mapping[str, Any],
    runtime: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[str, str]:
    status = str(definition.get("status") or "planned")
    required = status == "core"
    if evidence.get("project_used"):
        return "used_on_project", "Inspect the recorded artifacts and unresolved findings."
    if evidence.get("machine_tested"):
        return "tested_on_machine", "Run this capability on the current project when relevant."
    if runtime.get("compatible") is False:
        return "incompatible", "Install a supported version before using this capability."
    if runtime.get("discovered") and runtime.get("configured"):
        return "ready", "Run the capability on this project to create project-scoped evidence."
    if runtime.get("discovered") and not runtime.get("configured"):
        return "installed_unconfigured", "Complete adapter configuration before use."
    if status == "planned":
        return "planned", "No supported product execution path exists yet."
    if status == "reference":
        return "reference_only", "This project is a design reference, not an installed backend."
    if required:
        return "missing_required", "Install or restore this required capability before release work."
    return "missing_optional", "Install and configure only when this project needs the capability."


def capability_report(
    *,
    build_dir: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    which: WhichFn | None = None,
    run: RunFn | None = None,
    kicad_happy_discover: DiscoverFn | None = None,
) -> dict[str, Any]:
    """Return honest runtime, compatibility, test, and project-use states."""

    resolved_build = Path(build_dir).resolve() if build_dir else None
    environment = dict(os.environ if environ is None else environ)
    which_fn = which or shutil.which
    run_fn = run or subprocess.run
    discover_fn = kicad_happy_discover or discover_kicad_happy

    rows: list[dict[str, Any]] = []
    for definition in _definitions():
        runtime = _runtime_for(
            definition,
            environ=environment,
            which=which_fn,
            run=run_fn,
            discover=discover_fn,
        )
        evidence = _project_evidence(str(definition["id"]), resolved_build)
        readiness, next_action = _readiness(definition, runtime, evidence)
        rows.append(
            {
                **dict(definition),
                "required": str(definition.get("status")) == "core",
                "implementation_available": bool(
                    runtime.get("discovered")
                    or str(definition.get("status")) in {"wired", "opt_in", "partial", "core"}
                ),
                "runtime": runtime,
                "evidence": evidence,
                "readiness": readiness,
                "next_action": next_action,
            }
        )

    counts: dict[str, int] = {}
    for row in rows:
        readiness = str(row["readiness"])
        counts[readiness] = counts.get(readiness, 0) + 1
    required_missing = [
        row["id"] for row in rows if row["required"] and row["readiness"] == "missing_required"
    ]
    return {
        "ok": not required_missing,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build_dir": str(resolved_build) if resolved_build else None,
        "definitions": {
            "discovered": "Executable, module, checkout, or built-in implementation is present.",
            "configured": "Required local configuration is present; this does not prove execution.",
            "compatible": "Detected version satisfies a defined compatibility check; null means not evaluated.",
            "machine_tested": "A successful capability artifact exists for the inspected project.",
            "project_used": "At least one project-scoped artifact records use of the capability.",
        },
        "counts": dict(sorted(counts.items())),
        "required_missing": required_missing,
        "capabilities": rows,
    }
