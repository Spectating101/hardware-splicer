"""HS reviews WireStudio designs with WireStudio's own part data and says which findings the design already warned about."""

from __future__ import annotations

import copy
import json
import os

import pytest

from hardware_splicer.wirestudio_bridge import PART_FILE_ERRATA, main, review_design, review_examples, snapshot


def _rules(review):
    return [(f["rule"], "design_already_warns" in f) for f in review["findings"]]


def test_the_snapshot_is_pinned_and_licensed():
    meta = snapshot()["meta"]
    assert len(meta["commit"]) == 40 and meta["license"].startswith("MIT")
    assert meta["counts"] == {"components": 102, "boards": 27, "examples": 76}


def test_the_examples_review():
    result = review_examples()
    assert result["designs"] == 76
    assert result["findings_by_rule"] == {"five_volt_signal_into_mcu": 3, "led_data_below_vih": 7, "part_file_disagrees_with_maker": 1}
    assert result["findings_not_already_in_the_designs"] == 8


def test_a_5v_signal_into_an_esp32_pin_is_an_error_with_the_cited_limit_and_the_designs_own_note():
    review = review_design(snapshot()["examples"]["access-panel"])
    assert _rules(review) == [("five_volt_signal_into_mcu", True)] * 2
    assert "VDD + 0.3" in review["findings"][0]["basis"]
    assert "GPIO32" in review["findings"][0]["design_already_warns"]["text"]


def test_without_the_hand_written_warning_the_same_problem_is_still_found():
    design = copy.deepcopy(snapshot()["examples"]["access-panel"])
    design["warnings"] = []
    assert _rules(review_design(design)) == [("five_volt_signal_into_mcu", False)] * 2


def test_a_level_shifter_in_the_design_clears_it():
    design = copy.deepcopy(snapshot()["examples"]["access-panel"])
    design["components"].append({"id": "shift", "library_id": "level_shifter", "label": "Shifter", "params": {}})
    assert not any(f["rule"] == "five_volt_signal_into_mcu" for f in review_design(design)["findings"])


def test_the_ld2420_part_file_is_corrected_from_the_makers_manual_and_its_correct_wiring_is_not_flagged():
    review = review_design(snapshot()["examples"]["presence-rf"])
    assert _rules(review) == [("part_file_disagrees_with_maker", False)]
    assert "3.0 V~3.6 V" in review["findings"][0]["basis"]
    assert snapshot()["components"]["ld2420"]["electrical"]["vcc_min"] == 4.5  # the snapshot itself is left unchanged
    assert PART_FILE_ERRATA["ld2420"]["vcc_range"] == (3.0, 3.6)


@pytest.mark.parametrize("example", ["atom-lite", "s3-devkitc", "esp32cam", "bench-io"])
def test_board_mounted_parts_and_unstated_ranges_are_not_blamed_on_the_design(example):
    assert review_design(snapshot()["examples"][example])["findings"] == []


def test_an_unknown_board_is_refused(capsys, tmp_path):
    design = copy.deepcopy(snapshot()["examples"]["access-panel"])
    design["board"]["library_id"] = "no-such-board"
    with pytest.raises(ValueError, match="not in the WireStudio snapshot"):
        review_design(design)
    path = tmp_path / "d.json"
    path.write_text(json.dumps(design))
    assert main([str(path)]) == 2
    capsys.readouterr()


def test_firmware_generation_says_plainly_when_wirestudio_is_not_configured(tmp_path, monkeypatch):
    from hardware_splicer.wirestudio_bridge import generate_with_wirestudio

    monkeypatch.delenv("HS_WIRESTUDIO_GENERATE", raising=False)
    result = generate_with_wirestudio(snapshot()["examples"]["access-panel"], tmp_path / "out")
    assert result["generated"] is False and "HS_WIRESTUDIO_GENERATE" in result["reason"]
    assert result["review"]["counts"]["error"] == 2  # the review still runs
    monkeypatch.setenv("HS_WIRESTUDIO_GENERATE", str(tmp_path / "missing"))
    assert "does not exist" in generate_with_wirestudio(snapshot()["examples"]["access-panel"], tmp_path / "out")["reason"]


GENERATE = os.environ.get("HS_WIRESTUDIO_GENERATE_TEST")


@pytest.mark.skipif(not GENERATE, reason="set HS_WIRESTUDIO_GENERATE_TEST to a wirestudio-generate command")
def test_firmware_generation_with_a_real_wirestudio(tmp_path, monkeypatch):
    from hardware_splicer.wirestudio_bridge import generate_with_wirestudio

    monkeypatch.setenv("HS_WIRESTUDIO_GENERATE", GENERATE)
    result = generate_with_wirestudio(snapshot()["examples"]["usbc-led-strip"], tmp_path / "out")
    assert result["generated"] is True and result["files"] == ["esphome.yaml", "wiring.txt"]
    assert "esphome:" in (tmp_path / "out" / "esphome.yaml").read_text()
