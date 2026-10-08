"""The assembly plan: a visual build sequence derived from the retained board. It reports and changes nothing."""

from __future__ import annotations

import hashlib
import math
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.assembly_plan import AssemblyPlanError, build_assembly_plan, _compress
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

REF = Path(__file__).resolve().parents[1] / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
PCB = (REF / "spi_flash_adapter_v1.kicad_pcb").read_text(encoding="utf-8")


def _tiny_board(footprints: str, edge: str = "") -> str:
    edge = edge or (
        '(gr_line (start 0 0) (end 20 0) (layer "Edge.Cuts"))(gr_line (start 20 0) (end 20 10) (layer "Edge.Cuts"))'
        '(gr_line (start 20 10) (end 0 10) (layer "Edge.Cuts"))(gr_line (start 0 10) (end 0 0) (layer "Edge.Cuts"))'
    )
    return f'(kicad_pcb (version 20240108) (general (thickness 1.2)) {edge} {footprints})'


def _fp(ref: str, name: str, at: str, layer: str = "F.Cu", crt: str = "-2 -1 2 1", pads: str = "") -> str:
    x0, y0, x1, y1 = crt.split()
    side = "F" if layer.startswith("F") else "B"
    return (
        f'(footprint "{name}" (layer "{layer}") (at {at}) (property "Reference" "{ref}") (property "Value" "v")'
        f'(fp_rect (start {x0} {y0}) (end {x1} {y1}) (layer "{side}.CrtYd")) {pads})'
    )


def test_the_reference_board_gets_a_plan_that_matches_the_file() -> None:
    plan = build_assembly_plan(PCB, pcb_sha256="sha256:abc")
    assert plan["schema_version"] == "hardware_splicer.assembly_plan.v1"
    assert plan["source"]["pcb_sha256"] == "sha256:abc"
    assert plan["board"]["size_mm"] == [90.0, 50.0] and plan["board"]["outline"]["kind"] == "rectangle"
    assert plan["board"]["thickness_mm"] == 1.6 and plan["board"]["thickness_basis"] == "stated in the board file"
    assert plan["counts"]["parts"] == PCB.count("(footprint ") == len(plan["parts"])
    u2 = next(p for p in plan["parts"] if p["ref"] == "U2")
    assert (u2["x"], u2["y"], u2["rotation_deg"], u2["side"], u2["kind"]) == (170.0, 88.0, 0.0, "front", "ic")
    assert u2["height_basis"] == "typical SOIC package" and u2["outline_basis"] == "courtyard outline"
    # SOIC-8 pad 1 is at the top left of the part, in board coordinates.
    assert u2["pin1"]["x"] < u2["x"] and u2["pin1"]["y"] < u2["y"]
    assert "approves" in plan["authority"] or "Nothing here approves" in plan["authority"]


def test_every_part_is_in_exactly_one_step_and_the_order_is_low_before_tall() -> None:
    plan = build_assembly_plan(PCB)
    in_steps = [ref for step in plan["steps"] for ref in step["refs"]]
    assert sorted(in_steps) == sorted(p["ref"] for p in plan["parts"])
    heights = {p["ref"]: p["height_mm"] for p in plan["parts"]}
    smd = [s for s in plan["steps"] if s["kind"] in {"passive", "ic"}]
    through = [s for s in plan["steps"] if s["kind"] == "connector"]
    assert max(heights[r] for s in smd for r in s["refs"]) < min(heights[r] for s in through for r in s["refs"])
    assert plan["steps"][-1]["kind"] == "verify" and plan["steps"][-1]["refs"] == []
    assert [s["order"] for s in plan["steps"]] == list(range(1, len(plan["steps"]) + 1))


def test_a_check_is_only_suggested_once_both_ends_are_in_the_board() -> None:
    plan = build_assembly_plan(PCB)
    placed: set[str] = set()
    for step in plan["steps"]:
        placed |= set(step["refs"])
        for check in step["checks"]:
            assert check["kind"] == "suggested_check"
            refs = {check["from"].split()[0], check["to"].split()[0]}
            if check["check"] == "continuity":
                assert refs <= placed, (step["title"], check)
    first = plan["steps"][0]
    assert first["checks"] == []  # nothing else is in yet, so nothing can be tested
    last = plan["steps"][-1]["checks"]
    assert last and all(c["check"] == "isolation" and "NOT" in c["expect"] for c in last)


def test_connector_pins_list_their_nets_and_what_else_is_on_them() -> None:
    plan = build_assembly_plan(PCB)
    j1 = next(c for c in plan["connections"] if c["ref"] == "J1")
    assert len(j1["pins"]) == 6
    gnd = next(p for p in j1["pins"] if p["net"] and p["net"].endswith("GND"))
    assert gnd["also_on_total"] >= 6 and len(gnd["also_on"]) <= 6
    assert all(p["pin"] for p in j1["pins"])


def test_it_is_deterministic_and_does_not_hold_internal_fields() -> None:
    one, two = build_assembly_plan(PCB), build_assembly_plan(PCB)
    assert one == two
    assert not any(key.startswith("_") for part in one["parts"] for key in part)


@pytest.mark.parametrize(
    ("degrees", "expected"),
    [(0, [(8, 9), (12, 9), (12, 11), (8, 11)]), (90, [(9, 12), (9, 8), (11, 8), (11, 12)])],
)
def test_a_rotated_part_has_its_outline_turned_the_way_kicad_turns_it(degrees: int, expected: list[tuple[int, int]]) -> None:
    board = _tiny_board(_fp("R1", "Resistor_SMD:R_0603_1608Metric", f"10 10 {degrees}", crt="-2 -1 2 1"))
    part = build_assembly_plan(board)["parts"][0]
    got = [(round(x), round(y)) for x, y in part["corners"]]
    assert got == expected, (degrees, got)
    assert part["rotation_deg"] == float(degrees)


def test_a_back_side_part_is_mirrored_and_goes_after_the_front() -> None:
    front = _fp("R1", "Resistor_SMD:R_0603_1608Metric", "10 5", crt="1 -1 3 1")
    back = _fp("R2", "Resistor_SMD:R_0603_1608Metric", "10 5", layer="B.Cu", crt="1 -1 3 1")
    plan = build_assembly_plan(_tiny_board(front + back))
    by_ref = {p["ref"]: p for p in plan["parts"]}
    assert by_ref["R1"]["side"] == "front" and by_ref["R2"]["side"] == "back"
    # The same local box lands on the other side of the part's origin when the part is on the back.
    assert min(c[0] for c in by_ref["R1"]["corners"]) == 11 and max(c[0] for c in by_ref["R2"]["corners"]) == 9
    sides = [s["side"] for s in plan["steps"] if s["kind"] != "verify"]
    assert sides == ["front", "back"]
    flips = [s["turn_board_over"] for s in plan["steps"] if s["kind"] != "verify"]
    assert flips == [False, True]


def test_a_part_without_a_courtyard_falls_back_to_its_pads_and_says_so() -> None:
    fp = '(footprint "X:Unknown" (layer "F.Cu") (at 5 5) (property "Reference" "U9") (pad "1" smd rect (at -1 0) (size 1 1) (layers "F.Cu")) (pad "2" smd rect (at 1 0) (size 1 1) (layers "F.Cu")))'
    part = build_assembly_plan(_tiny_board(fp))["parts"][0]
    assert part["outline_basis"].startswith("pad extent")
    assert part["height_basis"] == "default for an IC"
    xs = [c[0] for c in part["corners"]]
    assert min(xs) == 3.5 and max(xs) == 6.5


def test_an_irregular_outline_is_reported_as_its_bounding_box() -> None:
    edge = '(gr_line (start 0 0) (end 20 0) (layer "Edge.Cuts"))(gr_line (start 20 0) (end 10 10) (layer "Edge.Cuts"))(gr_line (start 10 10) (end 0 0) (layer "Edge.Cuts"))'
    plan = build_assembly_plan(_tiny_board("", edge))
    assert plan["board"]["outline"]["kind"] == "bounding_box_of_irregular_outline"


@pytest.mark.parametrize("text", ["", "(kicad_sch)", "((((", "not a board", "(kicad_pcb (version 1))"])
def test_text_that_is_not_a_usable_board_is_refused(text: str) -> None:
    with pytest.raises(AssemblyPlanError):
        build_assembly_plan(text)


def test_non_finite_numbers_in_the_file_do_not_poison_the_plan() -> None:
    board = _tiny_board(_fp("R1", "Resistor_SMD:R_0603_1608Metric", "nan inf 0"))
    part = build_assembly_plan(board)["parts"][0]
    assert all(math.isfinite(v) for corner in part["corners"] for v in corner)


def test_reference_lists_are_compressed_for_reading() -> None:
    assert _compress(["R1", "R2", "R3", "R5"]) == "R1–R3, R5"
    assert _compress(["TP1", "TP2"]) == "TP1, TP2"
    assert _compress(["C3", "R1"]) == "C3, R1"


# --- over HTTP -------------------------------------------------------------------------------------------------------


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_BUILD_FILE_ROOTS", raising=False)
    build = tmp_path / "build"
    (build / "build_compilation").mkdir(parents=True)
    for source in REF.glob("spi_flash_adapter_v1.kicad_*"):
        shutil.copy(source, build / "build_compilation" / source.name)
    store = ProjectStore(tmp_path / "store")
    api = TestClient(create_product_app(store))
    snapshot = {"projectId": "robot", "projectName": "Robot", "currentStage": "design", "buildDir": str(build),
                "machineProject": {"project_id": "robot", "name": "Robot", "purpose": "plan"}}
    assert api.put("/v1/projects/robot/snapshot", json={"snapshot": snapshot, "expected_revision": 0}).status_code == 200
    return api, store, tmp_path


def test_the_plan_is_served_for_a_retained_revision_and_changes_nothing(world) -> None:
    api, store, tmp_path = world

    def tree(root: Path) -> dict[str, str]:
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}

    before = tree(tmp_path)
    response = api.get("/v1/projects/robot/revisions/1/assembly-plan")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True and body["plan"]["counts"]["parts"] == 40
    assert body["plan"]["source"]["pcb_sha256"].startswith("sha256:")
    assert tree(tmp_path) == before


def test_a_revision_without_a_retained_board_says_so_plainly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    store = ProjectStore(tmp_path / "store")
    api = TestClient(create_product_app(store))
    snapshot = {"projectId": "robot", "projectName": "Robot", "buildDir": str(tmp_path / "missing"),
                "machineProject": {"project_id": "robot", "name": "Robot", "purpose": "plan"}}
    assert api.put("/v1/projects/robot/snapshot", json={"snapshot": snapshot, "expected_revision": 0}).status_code == 200
    body = api.get("/v1/projects/robot/revisions/1/assembly-plan").json()
    assert body["available"] is False and body["reason"] == "no retained pcb"
    assert api.get("/v1/projects/robot/revisions/9/assembly-plan").status_code == 404


_KICAD_COMPARE = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import pcbnew
from hardware_splicer.assembly_plan import build_assembly_plan

source, scratch = sys.argv[2], sys.argv[3]
board = pcbnew.LoadBoard(source)
parts = {f.GetReference(): f for f in board.GetFootprints()}
# Turn and flip parts with KiCad itself, so the plan is read from a file KiCad wrote.
for ref, (degrees, flip) in {"R2": (90, False), "R3": (37, False), "U2": (180, False), "C3": (0, True), "C4": (45, True), "U1": (270, True)}.items():
    if flip:
        parts[ref].Flip(parts[ref].GetPosition(), False)
    parts[ref].SetOrientationDegrees(degrees)
board.Save(scratch)
reloaded = pcbnew.LoadBoard(scratch)
plan = build_assembly_plan(open(scratch, encoding="utf-8").read())
mm = pcbnew.ToMM
worst, compared = 0.0, 0
for part in plan["parts"]:
    fp = {f.GetReference(): f for f in reloaded.GetFootprints()}[part["ref"]]
    fp.BuildCourtyardCaches()
    box = fp.GetCourtyard(pcbnew.B_CrtYd if fp.GetLayer() == pcbnew.B_Cu else pcbnew.F_CrtYd).BBox()
    if box.GetWidth() <= 0:
        continue
    xs, ys = [c[0] for c in part["corners"]], [c[1] for c in part["corners"]]
    error = max(abs(min(xs) - mm(box.GetLeft())), abs(min(ys) - mm(box.GetTop())), abs(max(xs) - mm(box.GetRight())), abs(max(ys) - mm(box.GetBottom())))
    worst, compared = max(worst, error), compared + 1
print(json.dumps({"compared": compared, "worst_mm": worst, "back": sum(1 for p in plan["parts"] if p["side"] == "back")}))
'''


def test_outlines_agree_with_kicads_own_geometry_for_turned_and_flipped_parts(tmp_path: Path) -> None:
    import json
    import shutil as _shutil
    import subprocess

    python = _shutil.which("python3") or "python3"
    probe = subprocess.run([python, "-c", "import pcbnew"], capture_output=True, timeout=60)
    if probe.returncode != 0:
        pytest.skip("pcbnew is not importable from the system python")
    done = subprocess.run(
        [python, "-c", _KICAD_COMPARE, str(Path(__file__).resolve().parents[1] / "src"), str(REF / "spi_flash_adapter_v1.kicad_pcb"), str(tmp_path / "turned.kicad_pcb")],
        capture_output=True, text=True, timeout=120,
    )
    assert done.returncode == 0, done.stderr[-800:]
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert result["compared"] == 40, result          # nothing may be skipped: a comparison of zero parts proves nothing
    assert result["back"] == 3, result                # three parts really are on the back
    # KiCad's courtyard includes half the line width, about 0.05 mm. A wrong turn or mirror would be off by millimetres.
    assert result["worst_mm"] < 0.1, result
