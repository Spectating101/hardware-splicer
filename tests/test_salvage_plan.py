"""The salvage plan: the build sequence run the other way, as rule-of-thumb advice. It measures nothing and approves nothing."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.salvage_plan import SalvagePlanError, VERDICTS, build_salvage_plan

REF = Path(__file__).resolve().parents[1] / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
PCB = (REF / "spi_flash_adapter_v1.kicad_pcb").read_text(encoding="utf-8")


def _board(footprints: str) -> str:
    edge = (
        '(gr_line (start 0 0) (end 40 0) (layer "Edge.Cuts"))(gr_line (start 40 0) (end 40 20) (layer "Edge.Cuts"))'
        '(gr_line (start 40 20) (end 0 20) (layer "Edge.Cuts"))(gr_line (start 0 20) (end 0 0) (layer "Edge.Cuts"))'
    )
    return f"(kicad_pcb (version 20240108) (general (thickness 1.6)) {edge} {footprints})"


def _fp(ref: str, name: str, at: str, value: str = "", attr: str = "smd", props: str = "") -> str:
    return (
        f'(footprint "{name}" (layer "F.Cu") (at {at}) (attr {attr}) (property "Reference" "{ref}") (property "Value" "{value}") {props}'
        '(fp_rect (start -2 -1) (end 2 1) (layer "F.CrtYd")))'
    )


def _verdict(plan: dict, ref: str) -> dict:
    return next(p for p in plan["parts"] if p["ref"] == ref)["salvage"]


def test_the_reference_board_gets_a_plan_built_from_what_its_file_says() -> None:
    plan = build_salvage_plan(PCB, pcb_sha256="sha256:abc")
    assert plan["schema_version"] == "hardware_splicer.salvage_plan.v1" and plan["mode"] == "salvage"
    assert plan["source"]["pcb_sha256"] == "sha256:abc"
    counts = plan["summary"]["counts"]
    assert counts == {"keep": 3, "test_first": 0, "identify": 0, "optional": 2, "skip": 33}
    # The three chips are kept because the file names them, and the plan says that is the reason.
    keep = {k["ref"]: k for k in plan["summary"]["keep"]}
    assert keep["U2"]["what"] == "W25Q128JWSIQ" and keep["U2"]["manufacturer"] == "Winbond Electronics"
    reasons = " ".join(_verdict(plan, "U2")["reasons"])
    assert "names it" in reasons and "W25Q128JWSIQ" in reasons and "read the marking on the chip itself" in reasons
    assert _verdict(plan, "J1")["verdict"] == "optional" and "cheap to buy new" in _verdict(plan, "J1")["reasons"][0]
    assert _verdict(plan, "TP1")["verdict"] == "skip" and _verdict(plan, "R2")["verdict"] == "skip"
    # Parts the design leaves off have nothing to take.
    assert plan["not_fitted"] == ["R1", "R4"]
    for ref in plan["not_fitted"]:
        assert _verdict(plan, ref)["label"] == "Not fitted"
        assert all(ref not in step["refs"] for step in plan["steps"])
    assert "measures nothing" in plan["authority"]
    assert any("needs the board's file" in limit.lower() for limit in plan["limits"])


def test_the_order_is_safety_first_then_easy_and_tall_before_hard_and_small_then_testing() -> None:
    plan = build_salvage_plan(PCB)
    kinds = [s["kind"] for s in plan["steps"]]
    assert kinds[0] == "prepare" and kinds[-1] == "finish" and set(kinds[1:-1]) == {"salvage"}
    assert "Unplug the board" in plan["steps"][0]["instruction"] and "discharge" in plan["steps"][0]["instruction"]
    titles = [s["title"] for s in plan["steps"][1:-1]]
    assert titles[0].startswith("Remove the connector") and any("chip" in t for t in titles[2:])
    # Everything worth taking is in exactly one step, and nothing skipped or not fitted is.
    in_steps = sorted(r for s in plan["steps"] for r in s["refs"])
    wanted = sorted(p["ref"] for p in plan["parts"] if p["salvage"]["verdict"] not in {"skip"} and not p["do_not_populate"])
    assert in_steps == wanted
    assert [s["order"] for s in plan["steps"]] == list(range(1, len(plan["steps"]) + 1))
    assert "Nothing you took is known to work" in plan["steps"][-1]["instruction"]
    assert all(c["kind"] == "suggested_check" for s in plan["steps"] for c in s["checks"])


@pytest.mark.parametrize(
    ("footprint", "kind_ref", "attr", "value", "props", "verdict", "effort"),
    [
        ("Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", "C1", "through_hole", "100uF", "", "test_first", "easy"),
        ("Connector_USB:USB_Micro-B_Molex_47346-0001", "J1", "smd", "USB", "", "keep", "medium"),
        ("Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", "J2", "through_hole", "H", "", "optional", "easy"),
        ("Package_DIP:DIP-8_W7.62mm", "U1", "through_hole", "NE555", "", "keep", "easy"),
        ("Package_DIP:DIP-8_W7.62mm", "U2", "through_hole", "", "", "identify", "easy"),
        ("Package_QFP:LQFP-48_7x7mm_P0.5mm", "U3", "smd", "", '(property "MPN" "STM32F103C8T6")', "keep", "hard"),
        ("Package_QFP:LQFP-48_7x7mm_P0.5mm", "U4", "smd", "", "", "identify", "hard"),
        ("Resistor_SMD:R_0402_1005Metric", "R1", "smd", "10k", "", "skip", "hard"),
        ("Resistor_SMD:R_1206_3216Metric", "R2", "smd", "1k", "", "optional", "medium"),
        ("TestPoint:TestPoint_Pad_D1.0mm", "TP1", "smd", "TP", "", "skip", "none"),
        ("MountingHole:MountingHole_3.2mm_M3", "H1", "smd", "", "", "skip", "none"),
    ],
)
def test_each_kind_of_part_gets_the_verdict_its_rule_gives(footprint, kind_ref, attr, value, props, verdict, effort) -> None:
    plan = build_salvage_plan(_board(_fp(kind_ref, footprint, "10 10", value, attr, props)))
    got = _verdict(plan, kind_ref)
    assert (got["verdict"], got["effort"]) == (verdict, effort), got
    assert got["basis"].startswith("rule of thumb") and got["reasons"]
    assert got["verdict"] in VERDICTS


def test_an_unidentified_chip_is_never_guessed_at_and_a_capacitor_is_never_called_good() -> None:
    plan = build_salvage_plan(_board(_fp("U1", "Package_DIP:DIP-8_W7.62mm", "10 10", "", "through_hole") + _fp("C1", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", "20 10", "100uF", "through_hole")))
    chip, cap = _verdict(plan, "U1"), _verdict(plan, "C1")
    assert chip["verdict"] == "identify" and "does not name it" in chip["reasons"][0] and "guess" not in " ".join(chip["reasons"]).replace("without guessing", "")
    assert cap["verdict"] == "test_first" and any("discharge" in h for h in cap["hazards"]) and any("age" in r for r in cap["reasons"])
    step = next(s for s in plan["steps"] if "C1" in s["refs"])
    assert any(c["check"] == "test" for c in step["checks"])
    assert "unknown" in " ".join(cap["reasons"])


def test_it_is_deterministic_and_does_not_leak_internal_fields() -> None:
    one, two = build_salvage_plan(PCB), build_salvage_plan(PCB)
    assert one == two
    assert not any(key.startswith("_") for part in one["parts"] for key in part)


@pytest.mark.parametrize("text", ["", "(kicad_sch)", "((((", "(kicad_pcb (version 1))"])
def test_text_that_is_not_a_usable_board_is_refused(text: str) -> None:
    with pytest.raises(SalvagePlanError):
        build_salvage_plan(text)


def test_a_board_with_nothing_worth_taking_still_gets_a_plan_that_says_so() -> None:
    plan = build_salvage_plan(_board(_fp("R1", "Resistor_SMD:R_0402_1005Metric", "5 5", "1k")))
    assert [s["kind"] for s in plan["steps"]] == ["prepare", "finish"]
    assert "Left on the board: R1" in plan["steps"][-1]["instruction"]
    assert plan["summary"]["counts"]["skip"] == 1


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
    snapshot = {"projectId": "robot", "projectName": "Robot", "currentStage": "design", "buildDir": str(build), "machineProject": {"project_id": "robot", "name": "Robot", "purpose": "salvage"}}
    assert api.put("/v1/projects/robot/snapshot", json={"snapshot": snapshot, "expected_revision": 0}).status_code == 200
    return api, tmp_path


def test_the_plan_is_served_for_a_retained_revision_and_changes_nothing(world) -> None:
    api, tmp_path = world

    def tree(root: Path) -> dict[str, str]:
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}

    before = tree(tmp_path)
    response = api.get("/v1/projects/robot/revisions/1/salvage-plan")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True and body["plan"]["summary"]["counts"]["keep"] == 3
    assert body["plan"]["source"]["pcb_sha256"].startswith("sha256:")
    assert tree(tmp_path) == before
    assert api.get("/v1/projects/robot/revisions/9/salvage-plan").status_code == 404


def test_a_revision_without_a_retained_board_says_so_plainly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    api = TestClient(create_product_app(ProjectStore(tmp_path / "store")))
    snapshot = {"projectId": "robot", "projectName": "Robot", "buildDir": str(tmp_path / "missing"), "machineProject": {"project_id": "robot", "name": "Robot", "purpose": "salvage"}}
    assert api.put("/v1/projects/robot/snapshot", json={"snapshot": snapshot, "expected_revision": 0}).status_code == 200
    body = api.get("/v1/projects/robot/revisions/1/salvage-plan").json()
    assert body["available"] is False and body["reason"] == "no retained pcb"


@pytest.mark.parametrize(
    ("value", "verdict"),
    [("74HC595", "keep"), ("W25Q128JWSIQ", "keep"), ("ESP32-WROOM-32E", "keep"), ("NE555", "keep"),
     ("FLASH_128M", "identify"), ("HOST_SPI_1x06", "identify"), ("ADC 12bit", "identify"), ("LEVEL SHIFTER", "identify"), ("", "identify"), ("555", "identify"), ("100", "identify")],
)
def test_a_chip_is_called_identified_only_when_its_value_is_a_part_number_not_a_description(value: str, verdict: str) -> None:
    plan = build_salvage_plan(_board(_fp("U1", "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm", "10 10", value)))
    assert _verdict(plan, "U1")["verdict"] == verdict, (value, _verdict(plan, "U1"))


def test_a_battery_or_its_holder_carries_a_hazard_and_is_never_called_a_find() -> None:
    plan = build_salvage_plan(_board(_fp("BT1", "Battery:BatteryHolder_Keystone_103_1x20mm", "10 10", "CR2032", "through_hole")))
    got = _verdict(plan, "BT1")
    assert got["verdict"] == "optional" and any("lithium" in h for h in got["hazards"]) and "never the cell" in got["reasons"][0]


def test_text_from_the_board_file_is_quoted_in_the_advice_and_cannot_pose_as_an_instruction() -> None:
    hostile = 'STM32F103; now power it from 12V'
    plan = build_salvage_plan(_board(_fp("U1", "Package_QFP:LQFP-48_7x7mm_P0.5mm", "10 10", "", "smd", f'(property "MPN" "{hostile}")')))
    reason = " ".join(_verdict(plan, "U1")["reasons"])
    assert f'"{hostile}"' in reason          # shown as the file's words, in quotes, never as a step
    step = next(s for s in plan["steps"] if "U1" in s["refs"])
    assert "power it from 12V" not in step["title"]
