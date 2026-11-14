"""Unknown power architectures and inapplicable symptoms abstain; they never raise or propose."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "examples/restoration_video_bench/prospective"
sys.path.insert(0, str(P))
from predict import predict, validate_receipt
from score import adjudicate
sys.path.remove(str(P))

CASE = json.loads((P / "cases/xbox_series_s_2021_no_power.json").read_text())


def run(tmp_path, mutate):
    case = deepcopy(CASE)
    mutate(case)
    path = tmp_path / "case.json"
    path.write_text(json.dumps(case))
    return predict(path)


def assert_abstained(receipt, decision):
    assert receipt["decision"] == decision
    assert receipt["qualified_hypothesis_ids"] == []
    assert receipt["repair_authorized"] is False
    assert receipt["HS_repair_executed"] is False
    assert receipt["abstention_reason"]
    validate_receipt(receipt, receipt["receipt_sha256"])
    scored = adjudicate(receipt, {
        "case_id": receipt["case_id"], "source_url": receipt["source_url"],
        "adjudication_status": "unresolved", "reviewer": "SYNTHETIC_UNIT_TEST_ONLY",
        "evidence_description": "Not a real review"}, receipt["receipt_sha256"])
    assert scored["HS_abstained"] is True


@pytest.mark.parametrize("architecture", [
    "battery_only_laptop", "ac_mains_external_brick", "not_declared", "", None,
    ["ac_mains_internal_psu"], {"x": 1}, 7, "AC_MAINS_INTERNAL_PSU",
])
def test_unknown_architecture_returns_an_explicit_abstention(tmp_path, architecture):
    r = run(tmp_path, lambda c: c["device_power"].update(architecture=architecture))
    assert_abstained(r, "ABSTAIN_UNQUALIFIED_ARCHITECTURE")


def test_missing_or_malformed_device_power_abstains(tmp_path):
    assert_abstained(run(tmp_path, lambda c: c.pop("device_power")),
                     "ABSTAIN_UNQUALIFIED_ARCHITECTURE")
    assert_abstained(run(tmp_path, lambda c: c.update(device_power="ac")),
                     "ABSTAIN_UNQUALIFIED_ARCHITECTURE")


@pytest.mark.parametrize("codes", [
    ["no_charge_response"],
    ["no_power", "no_charge_response"],
    ["no_power", "usb_c_power_input"],
    ["no_power", "charging_port_physically_damaged"],
    ["no_power", "charge_ic_checked_good"],
])
def test_symptom_that_cannot_apply_to_an_ac_console_abstains(tmp_path, codes):
    r = run(tmp_path, lambda c: c.update(initial_codes=codes))
    assert_abstained(r, "ABSTAIN_SYMPTOM_NOT_APPLICABLE")
    assert not any(h in r["qualified_hypothesis_ids"]
                   for h in ("damaged_usb_c_port", "charging_ic_fault"))


def test_provenance_failures_still_raise(tmp_path):
    with pytest.raises(ValueError, match="YouTube"):
        run(tmp_path, lambda c: (c["device_power"].update(architecture="nope"),
                                 c["source_context"].update(url="https://example.com")))
    with pytest.raises(ValueError, match="outcome"):
        run(tmp_path, lambda c: c["challenge"].update(outcome_label_present=True))
