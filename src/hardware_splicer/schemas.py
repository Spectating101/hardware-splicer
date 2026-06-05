from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping


def _require_dict(data: Any, name: str) -> Dict[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError(f"{name} must be an object")
    return dict(data)


def _dict_or_empty(data: Any, name: str) -> Dict[str, Any]:
    if data is None:
        return {}
    return _require_dict(data, name)


def _resolve_board_design_files(
    board_design_files: Dict[str, Dict[str, Any]], base_dir: Path
) -> Dict[str, Dict[str, Any]]:
    resolved: Dict[str, Dict[str, Any]] = {}
    for board_id, meta in board_design_files.items():
        row = dict(meta)
        path = str(row.get("path") or "").strip()
        if path and not Path(path).is_absolute():
            row["path"] = str((base_dir / path).resolve())
        resolved[board_id] = row
    return resolved


@dataclass(frozen=True)
class HardwareCompileSpec:
    project_name: str
    machine: Dict[str, Any]
    mechanism: Dict[str, Any] = field(default_factory=dict)
    board_design_files: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    run_mechanism_sim: bool = True
    simulation_fidelity: str = "starter"
    use_3d_splicer: bool = True
    render_stl: bool = False
    circuit_authority: Dict[str, Any] = field(default_factory=dict)
    circuit_release: Dict[str, Any] = field(default_factory=dict)
    mechanical_evidence: Dict[str, Any] = field(default_factory=dict)
    mechanical_measurement_capture: Dict[str, Any] = field(default_factory=dict)
    mechanical_simulation_capture: Dict[str, Any] = field(default_factory=dict)
    mechanical_bench_capture: Dict[str, Any] = field(default_factory=dict)
    mechanical_release: Dict[str, Any] = field(default_factory=dict)
    robotics_project: Dict[str, Any] = field(default_factory=dict)
    robotics_platform: Dict[str, Any] = field(default_factory=dict)
    robotics_actuation: Dict[str, Any] = field(default_factory=dict)
    robotics_simulation: Dict[str, Any] = field(default_factory=dict)
    control_stack: Dict[str, Any] = field(default_factory=dict)
    safety_case: Dict[str, Any] = field(default_factory=dict)
    robotics_bench_capture: Dict[str, Any] = field(default_factory=dict)
    robotics_release: Dict[str, Any] = field(default_factory=dict)
    robotics_validation: Dict[str, Any] = field(default_factory=dict)
    field_validation: Dict[str, Any] = field(default_factory=dict)
    robotics_project_release: Dict[str, Any] = field(default_factory=dict)
    integrated_bench_capture: Dict[str, Any] = field(default_factory=dict)
    mechatronics_release: Dict[str, Any] = field(default_factory=dict)
    target_mechanical_authority_level: str = "production_mechanical_release"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HardwareCompileSpec":
        raw = _require_dict(data, "spec")
        machine = _require_dict(raw.get("machine"), "machine")
        mechanism = _dict_or_empty(raw.get("mechanism"), "mechanism")
        board_design_files = _dict_or_empty(raw.get("board_design_files"), "board_design_files")
        normalized_files: Dict[str, Dict[str, Any]] = {}
        for key, value in board_design_files.items():
            normalized_files[str(key)] = _require_dict(value, f"board_design_files.{key}")

        fidelity = str(raw.get("simulation_fidelity") or "starter")
        if fidelity not in {"starter", "high"}:
            raise ValueError("simulation_fidelity must be 'starter' or 'high'")

        project_name = str(raw.get("project_name") or machine.get("machine_name") or "hardware_splicer_build").strip()
        if not project_name:
            raise ValueError("project_name must not be blank")

        return cls(
            project_name=project_name,
            machine=machine,
            mechanism=mechanism,
            board_design_files=normalized_files,
            run_mechanism_sim=bool(raw.get("run_mechanism_sim", True)),
            simulation_fidelity=fidelity,
            use_3d_splicer=bool(raw.get("use_3d_splicer", True)),
            render_stl=bool(raw.get("render_stl", False)),
            circuit_authority=_dict_or_empty(raw.get("circuit_authority"), "circuit_authority"),
            circuit_release=_dict_or_empty(raw.get("circuit_release"), "circuit_release"),
            mechanical_evidence=_dict_or_empty(raw.get("mechanical_evidence"), "mechanical_evidence"),
            mechanical_measurement_capture=_dict_or_empty(raw.get("mechanical_measurement_capture"), "mechanical_measurement_capture"),
            mechanical_simulation_capture=_dict_or_empty(raw.get("mechanical_simulation_capture"), "mechanical_simulation_capture"),
            mechanical_bench_capture=_dict_or_empty(raw.get("mechanical_bench_capture"), "mechanical_bench_capture"),
            mechanical_release=_dict_or_empty(raw.get("mechanical_release"), "mechanical_release"),
            robotics_project=_dict_or_empty(raw.get("robotics_project"), "robotics_project"),
            robotics_platform=_dict_or_empty(raw.get("robotics_platform"), "robotics_platform"),
            robotics_actuation=_dict_or_empty(raw.get("robotics_actuation"), "robotics_actuation"),
            robotics_simulation=_dict_or_empty(raw.get("robotics_simulation"), "robotics_simulation"),
            control_stack=_dict_or_empty(raw.get("control_stack"), "control_stack"),
            safety_case=_dict_or_empty(raw.get("safety_case"), "safety_case"),
            robotics_bench_capture=_dict_or_empty(raw.get("robotics_bench_capture"), "robotics_bench_capture"),
            robotics_release=_dict_or_empty(raw.get("robotics_release"), "robotics_release"),
            robotics_validation=_dict_or_empty(raw.get("robotics_validation"), "robotics_validation"),
            field_validation=_dict_or_empty(raw.get("field_validation"), "field_validation"),
            robotics_project_release=_dict_or_empty(raw.get("robotics_project_release"), "robotics_project_release"),
            integrated_bench_capture=_dict_or_empty(raw.get("integrated_bench_capture"), "integrated_bench_capture"),
            mechatronics_release=_dict_or_empty(raw.get("mechatronics_release"), "mechatronics_release"),
            target_mechanical_authority_level=str(raw.get("target_mechanical_authority_level") or "production_mechanical_release"),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "HardwareCompileSpec":
        import json

        source = Path(path)
        spec = cls.from_dict(json.loads(source.read_text(encoding="utf-8")))
        return replace(
            spec,
            board_design_files=_resolve_board_design_files(spec.board_design_files, source.parent),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "machine": self.machine,
            "mechanism": self.mechanism,
            "board_design_files": self.board_design_files,
            "run_mechanism_sim": self.run_mechanism_sim,
            "simulation_fidelity": self.simulation_fidelity,
            "use_3d_splicer": self.use_3d_splicer,
            "render_stl": self.render_stl,
            "circuit_authority": self.circuit_authority,
            "circuit_release": self.circuit_release,
            "mechanical_evidence": self.mechanical_evidence,
            "mechanical_measurement_capture": self.mechanical_measurement_capture,
            "mechanical_simulation_capture": self.mechanical_simulation_capture,
            "mechanical_bench_capture": self.mechanical_bench_capture,
            "mechanical_release": self.mechanical_release,
            "robotics_project": self.robotics_project,
            "robotics_platform": self.robotics_platform,
            "robotics_actuation": self.robotics_actuation,
            "robotics_simulation": self.robotics_simulation,
            "control_stack": self.control_stack,
            "safety_case": self.safety_case,
            "robotics_bench_capture": self.robotics_bench_capture,
            "robotics_release": self.robotics_release,
            "robotics_validation": self.robotics_validation,
            "field_validation": self.field_validation,
            "robotics_project_release": self.robotics_project_release,
            "integrated_bench_capture": self.integrated_bench_capture,
            "mechatronics_release": self.mechatronics_release,
            "target_mechanical_authority_level": self.target_mechanical_authority_level,
        }


@dataclass(frozen=True)
class HardwareCompileResult:
    ok: bool
    project_name: str
    request_id: str
    generated_at: str
    out_dir: str
    bundle_file: str
    report_file: str
    summary_file: str
    manifest_file: str
    metadata_file: str
    engineering: Dict[str, Any]
    mechanical_authority: Dict[str, Any] = field(default_factory=dict)
    robotics_actuation: Dict[str, Any] = field(default_factory=dict)
    robotics_simulation: Dict[str, Any] = field(default_factory=dict)
    robotics_platform_authority: Dict[str, Any] = field(default_factory=dict)
    mechatronics_authority: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)
    validation_issues: List[Dict[str, str]] = field(default_factory=list)
    splicer_url: str | None = None
    mecha_bundle_dir: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "project_name": self.project_name,
            "request_id": self.request_id,
            "generated_at": self.generated_at,
            "out_dir": self.out_dir,
            "bundle_file": self.bundle_file,
            "report_file": self.report_file,
            "summary_file": self.summary_file,
            "manifest_file": self.manifest_file,
            "metadata_file": self.metadata_file,
            "mecha_bundle_dir": self.mecha_bundle_dir,
            "splicer_url": self.splicer_url,
            "artifacts": self.artifacts,
            "validation_issues": self.validation_issues,
            "engineering": self.engineering,
            "mechanical_authority": self.mechanical_authority,
            "robotics_actuation": self.robotics_actuation,
            "robotics_simulation": self.robotics_simulation,
            "robotics_platform_authority": self.robotics_platform_authority,
            "mechatronics_authority": self.mechatronics_authority,
        }
