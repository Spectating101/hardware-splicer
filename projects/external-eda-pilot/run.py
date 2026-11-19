"""Reproduce the source-bound five-case external EDA / native CAD pilot.

Launch with a Python that has KiCad pcbnew. Pass a separate CadQuery
interpreter with --cad-python. No source checkout is modified by this runner.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURE = ROOT / "projects/bench-probe-fixture"
SOURCE = ROOT / "hardware/reference_designs/spi_flash_adapter_v1"
BOARD = SOURCE / "spi_flash_adapter_v1.kicad_pcb"
SCH = SOURCE / "spi_flash_adapter_v1.kicad_sch"
LOCK = json.loads((HERE / "engine-lock.json").read_text())
EXPECT = {"baseline": True, "passing_relocation": True,
          "moved_no_reroute": False, "moved_with_track": False,
          "wrong_net": False}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_variant(name: str, output: Path) -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    f = board.FindFootprintByReference("TP12")
    if f is None:
        raise ValueError("TP12 missing")
    pad = next(iter(f.Pads()))
    old = pad.GetPosition()
    if name == "wrong_net":
        wrong = next(iter(board.FindFootprintByReference("TP11").Pads())).GetNet()
        pad.SetNet(wrong)
    else:
        dx, dy = (1, -1) if name == "passing_relocation" else (2, 0)
        f.Move(pcbnew.VECTOR2I(pcbnew.FromMM(dx), pcbnew.FromMM(dy)))
        if name in ("passing_relocation", "moved_with_track"):
            tr = pcbnew.PCB_TRACK(board)
            tr.SetStart(old)
            tr.SetEnd(pad.GetPosition())
            tr.SetWidth(pcbnew.FromMM(0.25))
            tr.SetLayer(pcbnew.F_Cu)
            tr.SetNet(pad.GetNet())
            board.Add(tr)
    pcbnew.SaveBoard(str(output), board)


def checked_run(args: list[str]) -> str:
    p = subprocess.run(args, cwd=ROOT, check=True, capture_output=True,
                       text=True, timeout=120)
    return p.stdout + p.stderr


def run(out: Path, kx_repo: Path, ak_repo: Path, cad_python: str) -> dict:
    source_manifest = json.loads((FIXTURE / "geometry.json").read_text())
    if sha(BOARD) != source_manifest["board_sha256"]:
        raise ValueError("source board sha256 does not match authoritative fixture")
    module_path = ROOT / "src/hardware_splicer/integrations/external_eda_verification.py"
    spec = importlib.util.spec_from_file_location("hs_external_checker", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("external verifier module not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    (out / "cases").mkdir(parents=True, exist_ok=True)
    inputs: dict[str, Path] = {"baseline": BOARD}
    for name in EXPECT:
        if name == "baseline":
            continue
        copy = out / "cases" / (name + ".kicad_pcb")
        create_variant(name, copy)
        inputs[name] = copy
    case_report = {}
    for name, b in inputs.items():
        receipt = module.verify_board(
            SCH, b, out / "checks" / name,
            kiskill_repo=kx_repo,
            kiskill_commit=LOCK["kiskill"]["commit"],
            akcli_repo=ak_repo,
            akcli_commit=LOCK["akcli"]["commit"],
        )
        actual = receipt["checks"]["digital_review_pass"]
        case_report[name] = {
            "expected_acceptance": EXPECT[name],
            "actual_acceptance": actual,
            "sha256": sha(b),
            "drc": receipt["native_drc_counts"],
            "kiskill_roundtrip": receipt["checks"]["kiskill_roundtrip"],
            "akcli_equivalent": receipt["checks"]["akcli_schematic_pcb_equivalent"],
        }
        print(name, "expected=" + str(EXPECT[name]), "actual=" + str(actual),
              "drc=" + str(receipt["native_drc_counts"]), flush=True)
    if any(r["actual_acceptance"] != r["expected_acceptance"]
           for r in case_report.values()):
        raise AssertionError("control case classification mismatch")

    for name in ("baseline", "passing_relocation"):
        dest = out / "mechanical" / name
        dest.mkdir(parents=True, exist_ok=True)
        print(checked_run([
            cad_python, str(FIXTURE / "build.py"),
            "--board", str(inputs[name]), "--output", str(dest),
            "--kicad-python", "/usr/bin/python3"
        ]).strip(), flush=True)

    audit_path = out / "geometry-audit.json"
    checked_run([
        cad_python, str(HERE / "verify_cad.py"),
        str(out / "mechanical/baseline"),
        str(out / "mechanical/passing_relocation"),
        str(audit_path),
    ])
    geometry = json.loads(audit_path.read_text())
    if not geometry.get("passed"):
        raise AssertionError("mechanical output audit failed")
    summary = {
        "schema": "hs.external_eda_pilot.v1",
        "source_sha256": sha(BOARD),
        "upstream_pins": LOCK,
        "cases": case_report,
        "geometry": geometry,
        "expected_case_outcomes_matched": True,
        "digital_validation_only": True,
        "physical_test_performed": False,
        "citerefinery_handoff": "candidate_evidence_requires_review",
    }
    (out / "pilot-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kiskill-repo", type=Path, required=True)
    p.add_argument("--akcli-repo", type=Path, required=True)
    p.add_argument("--cad-python", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = run(a.out.resolve(), a.kiskill_repo, a.akcli_repo, a.cad_python)
    print("PILOT_SUCCESS", len(result["cases"]), "cases, native KiCad + STEP")
