"""A board with no file, described by a person: it gets the same take-apart advice, and says everything came from the person."""

from __future__ import annotations

import copy
import json
import math
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.donor_capture import MAX_PARTS, DonorCaptureError, build_donor_salvage_plan, capture_options, capture_to_assembly
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

SPEC = {
    "schema_version": "hardware_splicer.donor_capture.v1",
    "name": "Dead RC car controller",
    "board": {"width_mm": 60, "length_mm": 40},
    "parts": [
        {"ref": "U3", "kind": "ic", "package": "SOIC", "marking": "L9110S", "x_mm": 20, "y_mm": 10},
        {"ref": "U4", "kind": "ic", "package": "SOIC", "marking": "motor driver", "x_mm": 30, "y_mm": 10},
        {"ref": "J1", "kind": "connector", "package": "JST", "marking": "", "x_mm": 8, "y_mm": 30},
        {"ref": "C1", "kind": "capacitor", "package": "electrolytic can", "marking": "470uF 16V", "x_mm": 45, "y_mm": 28},
        {"ref": "BT1", "kind": "battery", "package": "cell (18650 or similar)", "marking": "", "x_mm": 30, "y_mm": 25},
        {"ref": "R1", "kind": "resistor", "package": "0603", "marking": "103", "x_mm": 12, "y_mm": 12},
    ],
}


def _verdict(plan: dict, ref: str) -> dict:
    return next(p for p in plan["parts"] if p["ref"] == ref)["salvage"]


def test_a_typed_board_gets_the_same_advice_and_says_it_came_from_the_person() -> None:
    plan = build_donor_salvage_plan(SPEC)
    assert plan["mode"] == "salvage" and plan["origin"] == "typed" and plan["name"] == "Dead RC car controller"
    assert plan["source"]["typed"] is True and plan["source"]["pcb_sha256"] is None
    assert any("Everything here is what you typed or placed" in limit for limit in plan["limits"])
    assert any("house code" in limit for limit in plan["limits"])
    assert _verdict(plan, "U3")["verdict"] == "keep" and _verdict(plan, "U4")["verdict"] == "identify"
    # A typed marking is "what you read", never "what the file says".
    reasons = " ".join(_verdict(plan, "U3")["reasons"])
    assert 'you read its marking as "L9110S"' in reasons and "file" not in reasons and "datasheet" in reasons
    assert _verdict(plan, "BT1")["verdict"] == "skip" and any("lithium" in h for h in _verdict(plan, "BT1")["hazards"])
    assert _verdict(plan, "C1")["verdict"] == "test_first" and _verdict(plan, "R1")["verdict"] == "skip"
    assert plan["steps"][0]["kind"] == "prepare" and plan["steps"][-1]["kind"] == "finish"
    assert "measures nothing" in plan["authority"] and "from what you described" in plan["authority"] and "read from its file" not in plan["authority"]


def test_the_kind_the_person_chose_decides_how_a_part_is_treated_not_its_label() -> None:
    spec = copy.deepcopy(SPEC)
    spec["parts"] = [{"ref": "J9", "kind": "ic", "package": "DIP", "marking": "NE555", "x_mm": 10, "y_mm": 10},
                     {"ref": "U9", "kind": "connector", "package": "USB", "marking": "", "x_mm": 30, "y_mm": 20}]
    plan = build_donor_salvage_plan(spec)
    assert _verdict(plan, "J9")["verdict"] == "keep" and "marking" in " ".join(_verdict(plan, "J9")["reasons"])
    assert _verdict(plan, "U9")["verdict"] == "keep" and "connector" in " ".join(_verdict(plan, "U9")["reasons"])


def test_a_description_instead_of_a_part_number_is_not_an_identification_and_a_typed_400v_capacitor_is_left_alone() -> None:
    spec = copy.deepcopy(SPEC)
    spec["parts"] = [{"ref": "U1", "kind": "ic", "package": "QFP", "marking": "motor driver thing", "x_mm": 10, "y_mm": 10},
                     {"ref": "X9", "kind": "capacitor", "package": "film box", "marking": "275VAC X2", "x_mm": 30, "y_mm": 20},
                     {"ref": "Q7", "kind": "mains or power part", "package": "transformer", "marking": "", "x_mm": 40, "y_mm": 20}]
    plan = build_donor_salvage_plan(spec)
    assert _verdict(plan, "U1")["verdict"] == "identify"
    assert _verdict(plan, "X9")["verdict"] == "skip" and any("dangerous charge" in h for h in _verdict(plan, "X9")["hazards"])
    assert _verdict(plan, "Q7")["verdict"] != "keep" and any("mains" in h for h in _verdict(plan, "Q7")["hazards"])


def test_geometry_is_what_was_typed_and_sizes_say_whether_they_were_measured() -> None:
    base = capture_to_assembly(SPEC)
    assert base["board"]["size_mm"] == [60.0, 40.0] and base["board"]["outline"]["bbox"] == {"x0": 0.0, "y0": 0.0, "x1": 60.0, "y1": 40.0}
    u3 = next(p for p in base["parts"] if p["ref"] == "U3")
    assert u3["corners"] == [[16.3, 7.3], [23.7, 7.3], [23.7, 12.7], [16.3, 12.7]]      # KiCad's 7.4 x 5.4 SOIC-8 courtyard centred on (20, 10)
    assert u3["outline_basis"].startswith("KiCad library courtyard for a SOIC") and "did not measure" in u3["outline_basis"] and "larger than the part" in u3["outline_basis"]
    assert u3["identity"] == {"mpn": None, "manufacturer": None, "typed": "L9110S", "source": "typed"}
    measured = copy.deepcopy(SPEC)
    measured["parts"][0].update(width_mm=7.2, length_mm=5.1, rotation_deg=90)
    got = next(p for p in capture_to_assembly(measured)["parts"] if p["ref"] == "U3")
    assert got["outline_basis"] == "the size you gave it (typed, or drawn over your photo)"
    xs, ys = [c[0] for c in got["corners"]], [c[1] for c in got["corners"]]
    assert (round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)) == (5.1, 7.2)        # turned a quarter: width and length swap


def test_references_are_made_up_when_blank_and_never_repeat() -> None:
    spec = copy.deepcopy(SPEC)
    spec["parts"] = [{"kind": "capacitor", "package": "ceramic 0603", "x_mm": 5, "y_mm": 5}, {"ref": "C2", "kind": "capacitor", "package": "ceramic 0603", "x_mm": 8, "y_mm": 5}, {"kind": "capacitor", "package": "ceramic 0603", "x_mm": 12, "y_mm": 5}]
    refs = [p["ref"] for p in capture_to_assembly(spec)["parts"]]
    assert refs == ["C1", "C2", "C3"] and len(set(refs)) == 3


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda s: s.update(schema_version="x"), "schema_version"),
        (lambda s: s.update(name=""), "name is required"),
        (lambda s: s.update(name="x" * 81), "at most 80"),
        (lambda s: s.update(board=None), "board must give"),
        (lambda s: s["board"].update(width_mm=1), "between 5 and 500"),
        (lambda s: s["board"].update(length_mm=float("nan")), "must be a number"),
        (lambda s: s["board"].update(thickness_mm=50), "between 0.4 and 5"),
        (lambda s: s["parts"][0].update(kind="spaceship"), "kind must be one of"),
        (lambda s: s["parts"][0].update(package="SOT-999"), "package for ic"),
        (lambda s: s["parts"][0].update(x_mm=61), "between 0 and 60"),
        (lambda s: s["parts"][0].update(y_mm=-1), "between 0 and 40"),
        (lambda s: s["parts"][0].update(ref="U 3"), "letters, digits"),
        (lambda s: s["parts"][1].update(ref="u3"), "used twice"),
        (lambda s: s["parts"][0].update(rotation_deg=45), "0, 90, 180 or 270"),
        (lambda s: s["parts"][0].update(rotation_deg=True), "0, 90, 180 or 270"),
        (lambda s: s["parts"][0].update(side="top"), "front or back"),
        (lambda s: s["parts"][0].update(marking="x" * 41), "at most 40"),
        (lambda s: s["parts"][0].update(marking="a\u0000b"), "control or invisible characters"),
        (lambda s: s["parts"][0].update(marking=["list"]), "must be text"),
        (lambda s: s["parts"][0].update(width_mm=0), "between 0.5 and 120"),
        (lambda s: s.update(parts="nope"), "list of at most"),
        (lambda s: s.update(parts=[SPEC["parts"][0]] * (MAX_PARTS + 1)), "at most 300"),
        (lambda s: s["parts"].append("not a part"), "must be an object"),
    ],
)
def test_a_description_that_cannot_make_a_board_is_refused_with_a_reason(mutate, message: str) -> None:
    spec = copy.deepcopy(SPEC)
    mutate(spec)
    with pytest.raises(DonorCaptureError, match=message):
        build_donor_salvage_plan(spec)


def test_no_odd_value_makes_the_capture_crash() -> None:
    odd = [None, True, 0, -1, 1e308, float("nan"), float("inf"), "", "x" * 500, [], {}, [[]], "😀", 10**30, "J1; drop table"]
    rng = random.Random(20261010)

    def leaves(node, path=()):
        if isinstance(node, dict):
            for key, value in node.items():
                yield from leaves(value, path + (key,))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from leaves(value, path + (index,))
        else:
            yield path

    paths = list(leaves(SPEC))
    for _ in range(500):
        spec = copy.deepcopy(SPEC)
        for path in rng.sample(paths, k=rng.randint(1, 3)):
            target = spec
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = rng.choice(odd)
        try:
            plan = build_donor_salvage_plan(spec)
        except DonorCaptureError:
            continue
        assert plan["origin"] == "typed" and all(math.isfinite(c) for part in plan["parts"] for corner in part["corners"] for c in corner)


def test_an_empty_board_and_a_full_one_both_plan() -> None:
    empty = build_donor_salvage_plan({"name": "bare", "board": {"width_mm": 30, "length_mm": 20}, "parts": []})
    assert [s["kind"] for s in empty["steps"]] == ["prepare", "finish"] and empty["summary"]["counts"]["skip"] == 0
    full = copy.deepcopy(SPEC)
    full["parts"] = [{"kind": "resistor", "package": "0603", "x_mm": 1 + i % 50, "y_mm": 1 + i // 50, "marking": "103"} for i in range(MAX_PARTS)]
    assert build_donor_salvage_plan(full)["summary"]["counts"]["skip"] == MAX_PARTS


def test_the_options_list_every_kind_with_a_typical_size_and_says_it_is_typical() -> None:
    options = capture_options()
    assert "Measure the real part" in options["size_basis"]
    assert set(options["kinds"]) >= {"connector", "ic", "capacitor", "resistor", "battery", "mains or power part"}
    soic = options["kinds"]["ic"]["packages"]["SOIC"]
    assert (soic["width_mm"], soic["length_mm"], soic["mounting"], soic["size_is_typical"]) == (7.4, 5.4, "smd", False)
    assert "courtyard" in soic["size_source"] and "Package_SO:SOIC-8" in soic["size_source"]
    assert options["kinds"]["capacitor"]["prefix"] == "C"


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    return TestClient(create_product_app(ProjectStore(tmp_path / "store"))), tmp_path


def test_the_options_and_a_plan_are_served_and_nothing_is_stored(api) -> None:
    client, tmp_path = api
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    assert client.get("/v1/donors/options").json()["options"]["kinds"]["ic"]["prefix"] == "U"
    posted = client.post("/v1/donors/salvage-plan", json=SPEC)
    assert posted.status_code == 200 and posted.json()["plan"]["origin"] == "typed"
    assert posted.json()["plan"] == build_donor_salvage_plan(SPEC)
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before


def test_a_bad_request_is_a_clear_422_and_a_huge_one_is_refused_early(api) -> None:
    client, _ = api
    bad = client.post("/v1/donors/salvage-plan", json={**SPEC, "parts": [{"kind": "x"}]})
    assert bad.status_code == 422 and bad.json()["detail"]["type"] == "invalid_donor_capture" and "kind must be one of" in bad.json()["detail"]["message"]
    assert client.post("/v1/donors/salvage-plan", content=b"not json", headers={"content-type": "application/json"}).status_code == 422
    deep = b"[" * 30000 + b"0" + b"]" * 30000
    assert client.post("/v1/donors/salvage-plan", content=deep, headers={"content-type": "application/json"}).status_code == 422

    def pieces():
        for _ in range(100000):
            yield b"x" * 1024

    assert client.post("/v1/donors/salvage-plan", content=pieces(), headers={"content-type": "application/json"}).status_code == 413
    assert client.post("/v1/donors/salvage-plan", json={**SPEC, "name": "x" * 200000}).status_code == 413


def test_a_marking_that_looks_like_a_part_number_is_taken_as_read_not_as_proved() -> None:
    spec = copy.deepcopy(SPEC)
    spec["parts"] = [{"ref": "U1", "kind": "ic", "package": "SOIC", "marking": "KZ-17", "x_mm": 10, "y_mm": 10}]
    got = _verdict(build_donor_salvage_plan(spec), "U1")
    # The rule cannot tell a house code from a part number, and says so instead of trusting it.
    assert got["verdict"] == "keep" and any("house code" in r and "check it against a datasheet" in r for r in got["reasons"])


# --- review findings (Grok), each reproduced before it was fixed -----------------------------------------------------------------


@pytest.mark.parametrize("hidden", ["\u202eNE555", "\u200bNE555", "NE\u200d555", "NE\u2028555", "\ufeffNE555", "NE555\u202c", "NE\u0085555"])
def test_invisible_and_direction_changing_characters_are_refused_in_every_text_field(hidden: str) -> None:
    for field in ("marking", "ref"):
        spec = copy.deepcopy(SPEC)
        spec["parts"][0][field] = hidden if field == "marking" else "U" + hidden
        with pytest.raises(DonorCaptureError, match="control or invisible characters|letters, digits"):
            build_donor_salvage_plan(spec)
    spec = copy.deepcopy(SPEC)
    spec["name"] = "Router " + hidden
    with pytest.raises(DonorCaptureError, match="control or invisible characters"):
        build_donor_salvage_plan(spec)


def test_ordinary_non_english_text_is_still_welcome() -> None:
    spec = copy.deepcopy(SPEC)
    spec["name"] = "Placa de coche de juguete — ñ マザー"
    spec["parts"][0]["marking"] = "ΩµC 1kΩ"
    assert build_donor_salvage_plan(spec)["name"].startswith("Placa")


@pytest.mark.parametrize("where", ["board.width_mm", "board.length_mm", "board.thickness_mm", "x_mm", "y_mm", "width_mm", "length_mm"])
def test_an_integer_too_big_to_be_a_number_is_a_clear_refusal_not_a_server_error(where: str) -> None:
    spec = copy.deepcopy(SPEC)
    huge = 10 ** 400
    if where.startswith("board."):
        spec["board"][where.split(".")[1]] = huge
    else:
        spec["parts"][0][where] = huge
    with pytest.raises(DonorCaptureError, match="must be a number"):
        build_donor_salvage_plan(spec)


def test_the_api_answers_a_huge_integer_with_422_not_500(api) -> None:
    client, _ = api
    body = ('{"name":"x","board":{"width_mm":1' + "0" * 400 + ',"length_mm":40},"parts":[]}').encode()
    response = client.post("/v1/donors/salvage-plan", content=body, headers={"content-type": "application/json"})
    assert response.status_code == 422 and "must be a number" in response.json()["detail"]["message"]


def test_a_typed_board_never_talks_about_a_file_and_does_not_upgrade_a_reading_to_a_decision() -> None:
    plan = build_donor_salvage_plan(SPEC)
    text = json.dumps([[s["instruction"], s["checks"]] for s in plan["steps"]]) + json.dumps([p["salvage"]["basis"] for p in plan["parts"]])
    assert "file" not in text.replace("typed or placed: nothing was read from a file", "")
    assert all(p["salvage"]["basis"].startswith("rule of thumb on the part's kind and package, plus the marking you read") for p in plan["parts"])
    chip = _verdict(plan, "U3")
    assert chip["verdict"] == "keep" and chip["label"] == "Worth taking, if the marking checks out"
    step = next(s for s in plan["steps"] if "U3" in s["refs"])
    assert step["verdict_label"] == chip["label"] and any("compare it with a datasheet" in c["expect"] for c in step["checks"]) and not any("you now know" in c["expect"] for c in step["checks"])
    assert any("sizes are KiCad's library courtyards or typical for the package unless you gave them" in limit for limit in plan["limits"])
    # A file's chip keeps the plain label: it was named by the file, not by a reading.
    assert _verdict(build_donor_salvage_plan({**SPEC, "parts": [p for p in SPEC["parts"] if p["ref"] == "J1"]}), "J1")["label"] == "Worth taking"


def test_every_size_comes_from_a_real_library_footprint_or_says_it_is_typical() -> None:
    from hardware_splicer.donor_capture import _TABLE
    from hardware_splicer.part_lookup import footprint_size, libraries_available

    if not libraries_available():
        pytest.skip("KiCad's libraries are not installed")
    typical_only = []
    for kind, packages in _TABLE.items():
        for package, (rule_name, real, _w, _l, _mounting) in packages.items():
            if real is not None:
                assert footprint_size(real) is not None, f"{kind}/{package}: {real} is not a footprint in KiCad's library"
            else:
                typical_only.append((kind, package))
            info = capture_options()["kinds"][kind]["packages"][package]
            assert info["size_is_typical"] is (real is None), (kind, package)
            assert ("courtyard" in info["size_source"]) is (real is not None)
    assert sorted(typical_only) == [("battery", "cell (18650 or similar)"), ("battery", "lithium pouch"), ("connector", "other connector"), ("other", "something else")]


def test_a_part_with_no_library_footprint_is_drawn_at_a_typical_size_and_says_so() -> None:
    spec = copy.deepcopy(SPEC)
    spec["parts"] = [{"ref": "BT1", "kind": "battery", "package": "lithium pouch", "x_mm": 30, "y_mm": 20}]
    part = capture_to_assembly(spec)["parts"][0]
    assert part["outline_basis"].startswith("typical size for a lithium pouch")
