"""Bounded intact-input reuse deliverables, not a catalog-board substitution.

Artifacts are stored by the existing mission package/run owners. No evidence,
donor contract, project revision, readiness or physical authority is promoted.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Literal, Mapping
import zipfile

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from .stored_source_parser import read_registered_source_bytes

SCHEMA = "hardware_splicer.intact_input_reuse.v1"
REPORT_SCHEMA = "hardware_splicer.intact_input_reuse_run.v1"


class IntactReuseError(ValueError):
    pass


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InputBinding(_Model):
    device_alias: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    button: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    action: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")


class MechanicalProposal(_Model):
    approach: Literal["external_actuator", "remote_contact"]
    load_path: str = Field(min_length=1, max_length=1000)
    independent_return: str = Field(min_length=1, max_length=1000)
    travel_stop: str = Field(min_length=1, max_length=1000)


class IntactReuseSpec(_Model):
    design_class: Literal["intact_input_reuse"]
    donors_used: list[str] = Field(min_length=1, max_length=1)
    source_ids: list[str] = Field(min_length=1, max_length=16)
    interface: InputBinding
    mechanical: MechanicalProposal


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def discovery(view: Mapping, snapshot: Mapping) -> dict:
    """Small schema and contextual IDs, never an identified/measured donor."""
    donors = [row["donor_id"] for row in view.get("intake", {}).get("donors", [])]
    sources = [row["source_id"] for row in snapshot.get("engineeringSources", []) if row.get("source_id")]
    return {
        "schema": IntactReuseSpec.model_json_schema(),
        "operation": "intact_reuse",
        "donor_ids": donors, "registered_source_ids": sources[:16], "registered_source_count": len(sources),
        "example": {
            "design_class": "intact_input_reuse", "donors_used": donors[:1], "source_ids": sources[:1],
            "interface": {"device_alias": "donor_mouse", "button": "left", "action": "activate"},
            "mechanical": {"approach": "external_actuator",
                           "load_path": "Proposed separate pedal frame carries foot load, not the mouse switch.",
                           "independent_return": "Proposed return mechanism; force and travel remain unmeasured.",
                           "travel_stop": "Proposed adjustable hard stop; dimensions require actual specimen evidence."},
        },
        "scope": "Normalized host-button events only. Bindings/mechanics are proposals, not observed USB reports or measured geometry.",
        "instructions": "Replace example with your grounded design; required donor/source lists may be empty until intake/admission is prepared. Propose via mission events, then run intact_reuse. Its response's bundle_download_path returns the software review ZIP before physical readiness, never a READY build package. Read the hashed run for checks and source lineage.",
    }


# Expected action positions/counts are explicit, independent acceptance oracles. This same
# program exercises the EXACT adapter.py bytes delivered in the bundle.
_REPLAY_TESTS = '''"""Offline synthetic inputs, never measured USB/foot-pedal evidence."""
import importlib.util
import json
from pathlib import Path

root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("delivered_adapter", root / "adapter.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
binding = json.loads((root / "contract.json").read_text())["interface"]
device, button = binding["device_alias"], binding["button"]
def event(kind, dev=device, btn=button):
    return {"type": kind, "device": dev, **({"button": btn} if kind in {"pressed", "released"} else {})}
connect, down, up, disconnect = [event(kind) for kind in ("connected", "pressed", "released", "disconnected")]
other_device = device + "_other"
other_button = button + "_other"
cases = [
    ("no_connection", [up, down, down], []),
    ("held_at_connect", [connect, down, down, up, down], [4]),
    ("hold_no_repeat", [connect, up] + [down] * 100, [2]),
    ("hundred_press_release_cycles", [connect, up] + [down, down, up] * 100, [2 + 3*n for n in range(100)]),
    ("other_device_isolated", [connect, up, event("pressed", other_device), event("disconnected", other_device), down], [4]),
    ("other_button_ignored", [connect, up, event("pressed", btn=other_button), event("released", btn=other_button), down], [4]),
    ("reconnect_requires_release", [connect, up, down, disconnect, up, down, connect, down, up, down], [2, 9]),
]
results = []
for name, events, expected_steps in cases:
    adapter = module.Adapter(**binding)
    emissions = [(step, action) for step, item in enumerate(events) for action in adapter.feed(item)]
    actual_steps = [step for step, action in emissions]
    actions = [action for step, action in emissions]
    expected = [{"type": "action", "action": binding["action"], "device_alias": device}] * len(expected_steps)
    results.append({"name": name, "pass": actions == expected and actual_steps == expected_steps,
                    "expected_actions": len(expected_steps), "actual_actions": len(actions),
                    "expected_action_steps": expected_steps, "actual_action_steps": actual_steps})
print(json.dumps({"kind": "synthetic_normalized_event_replay", "scenarios": results}, sort_keys=True))
raise SystemExit(0 if all(row["pass"] for row in results) else 1)
'''


def _archive(files: Mapping[str, str]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, text in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, text.encode("utf-8"))
    return out.getvalue()


def build_intact_reuse(spec: Mapping, *, view: Mapping, project: Mapping, candidate_id: str, project_root: Path) -> tuple[dict, bytes]:
    try:
        design = IntactReuseSpec.model_validate(spec).model_dump()
    except ValidationError as exc:
        raise IntactReuseError(str(exc)) from exc
    known_donors = {row["donor_id"] for row in view.get("intake", {}).get("donors", [])}
    if not set(design["donors_used"]) <= known_donors:
        raise IntactReuseError("intact reuse donor must be referenced by this mission intake")
    source_rows = {row["source_id"]: row for row in project["snapshot"].get("engineeringSources", []) if row.get("source_id")}
    sources = []
    for ident in sorted(set(design["source_ids"])):
        row = source_rows.get(ident)
        content_hash = row.get("content_hash", "") if row else ""
        if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", content_hash):
            raise IntactReuseError(f"source {ident!r} must be registered with its content hash")
        try:
            read_registered_source_bytes(view["project_id"], row, project_root=project_root)
        except (OSError, ValueError) as exc:
            raise IntactReuseError(f"source {ident!r} retained bytes could not be hash-verified") from exc
        sources.append({"source_id": ident, "content_hash": content_hash,
                        "interpretation": "Registered source reference, not independently reviewed physical evidence."})
    physical_questions = [
        "Actual specimen identity, condition and continued electrical safety remain unestablished.",
        "Actual USB descriptors, host-device identity, normalized event mapping and target application binding require evidence.",
        "Mechanical fit, button force/travel and allowable limits are unmeasured; no fabrication dimensions are supplied.",
        "Pedal loads, return, stability, cable strain and service life require separate physical assessment.",
    ]
    if design["mechanical"]["approach"] == "remote_contact":
        physical_questions.append("Switch-node topology, contact behavior and reclaimed switch/wire suitability are unknown; no wiring or pinout is generated.")
    contract = {"schema_version": SCHEMA, "design": design, "interface": design["interface"],
                "project_id": view["project_id"], "mission_id": view["mission_id"],
                "candidate_id": candidate_id, "mission_anchor_revision": view["revision"],
                "source_read_revision": project["revision"], "spec_sha256": _sha(_json(spec).encode()),
                "sources": sources, "unresolved_physical_questions": physical_questions,
                "physical_correctness": "UNPROVEN", "physical_authority_granted": False,
                "fabrication_ready": False, "power_on_ready": False}
    files = {
        "adapter.py": Path(__file__).with_name("intact_reuse_adapter.py").read_text(),
        "contract.json": _json(contract), "test_adapter.py": _REPLAY_TESTS,
        "example-events.jsonl": "\n".join(json.dumps({"type": kind, "device": design["interface"]["device_alias"],
                                                       **({"button": design["interface"]["button"]} if kind in {"released", "pressed"} else {})}, sort_keys=True)
                                             for kind in ["connected", "released", "pressed", "pressed", "released"]) + "\n",
        "README.md": (
            "# Intact input-device reuse: SOFTWARE REVIEW BUNDLE\n\n"
            "Not a fabrication/READY package or physical validation. No purchased development board is substituted.\n\n"
            "Run `python test_adapter.py` for offline synthetic replay. Run `python adapter.py < example-events.jsonl` "
            "to emit one symbolic action. Requires only Python's standard library.\n\n"
            "The adapter consumes normalized events, NOT USB bytes, GPIO or evdev. It does not enumerate/select "
            "a device, inject keys, execute action names, flash, energize or contact hardware. An actual host bridge "
            "and observed device mapping remain unimplemented. Labels in contract.json are proposed logical bindings.\n\n"
            "A connect/reconnect starts disarmed until a release. One press emits one action; repeated press "
            "events while held do not repeat. Other devices/buttons do not trigger it. A real bridge must report "
            "initial state and disconnects reliably; synthetic tests cannot establish that behavior.\n\n"
            "contract.json contains source hashes, proposed mechanism and unresolved physical questions. "
            "No vendor-specific report layout, switch-node mapping, PCB geometry, force or safe stop dimension is inferred.\n"
        ),
    }
    with tempfile.TemporaryDirectory(prefix="hs-intact-replay-") as temp:
        root = Path(temp)
        for name in ("adapter.py", "contract.json", "test_adapter.py"):
            (root / name).write_text(files[name], encoding="utf-8")
        try:
            result = subprocess.run([sys.executable, "-I", str(root / "test_adapter.py")],
                                    cwd=root, capture_output=True, text=True, timeout=10, check=False)
            checks = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            raise IntactReuseError("delivered adapter replay could not complete") from exc
    scenarios = checks.get("scenarios", [])
    if result.returncode != 0 or len(scenarios) != 7 or not all(row.get("pass") is True for row in scenarios):
        raise IntactReuseError("delivered adapter failed synthetic replay; no passing bundle produced")
    files["offline-checks.json"] = _json(checks)
    data = _archive(files)
    report = {
        "schema_version": REPORT_SCHEMA, "scope": "SOFTWARE_REVIEW_ONLY", "contract": contract,
        "offline_checks": checks, "software_checks_passed": True,
        "package_sha256": _sha(data), "package_bytes": len(data),
        "bundle_download_path_template": f"/v1/projects/{view['project_id']}/missions/{view['mission_id']}/runs/{{name}}/bundle",
        "files": [{"name": name, "sha256": _sha(text.encode()), "bytes": len(text.encode())} for name, text in sorted(files.items())],
        "physical_correctness": "UNPROVEN", "physical_authority_granted": False,
    }
    return report, data
