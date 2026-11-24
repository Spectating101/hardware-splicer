"""Pin-specific physical checks are withheld however they are phrased, in any field."""
import re

import pytest

from hardware_splicer.restoration_board_action_gate import (
    UnverifiedBoardPinAction, reject_unverified_board_pin_actions, unsafe_pin_actions,
)

REF = {"target_board_physically_verified": False}


def plan(**over):
    p = {
        "summary": "No confirmed fault.",
        "hypotheses": [{"mechanism": "m", "why": "w", "evidence_ids": ["E1"],
                        "safe_test": "Inspect visually."}],
        "next_safe_check": "Inspect visually.",
        "uncertainty": "No meter data.", "abstain": False,
    }
    p.update(over)
    return p


PHRASES = [
    "Measure continuity at DC1 pin 4",
    "Check U7 pin6 for 5V",
    "Probe pin 4 of the DC jack",
    "Put the probe on DC1-4",
    "Probe DC1 (pin 4) with a multimeter",
    "Probe pad 4 on DC1",
    "Measure at DC1 terminal 4",
    "Check terminal 4",
    "Check DC1's pin 4",
    "Measure on pin 3 DC1",
    # further spellings
    "Check the fourth pin of the DC1 jack",
    "Probe the 4th pad",
    "Probe pin four of the connector",
    "Probe pin #4",
    "Probe pin no. 4",
    "Probe pin: 4",
    "Measure between pins 3 and 4 of J1",
    "Measure J1 pins 3-4",
    "Probe DC1.4",
    "Probe J2/5",
    "Probe J2_5",
    "Probe DC1:4",
    "Probe U7 pad A3",
    "Probe ball A1 of U3",
    "Check the center pin of the barrel jack",
    "Check the BT1 positive spring contact",
    "Check the U7 output pin",
    "Check the DC1 pin",
    "Touch the probe to the lead 2 of Q1",
    "Check the last pin of U7",
    "Probe contact 3 of the cartridge connector",
]


@pytest.mark.parametrize("phrase", PHRASES)
@pytest.mark.parametrize("field", ["next_safe_check", "summary", "uncertainty",
                                   "hyp.mechanism", "hyp.why", "hyp.safe_test"])
def test_pin_phrasing_caught_in_every_free_text_field(phrase, field):
    p = plan()
    if field.startswith("hyp."):
        p["hypotheses"][0][field[4:]] = phrase
    else:
        p[field] = phrase
    assert unsafe_pin_actions(p, REF), (phrase, field)
    with pytest.raises(UnverifiedBoardPinAction):
        reject_unverified_board_pin_actions(p, REF)


def test_extra_keys_and_mapping_keys_are_scanned():
    p = plan()
    p["notes"] = "Probe pin 4 of the DC jack"
    assert unsafe_pin_actions(p, REF)
    q = plan()
    q["Probe DC1 pin 4"] = "x"
    assert unsafe_pin_actions(q, REF)


@pytest.mark.parametrize("text", [
    "Check DC​1 pin 4",
    "Check pi​n 4 of the DC jack",
    "Check Рin 4 of the DC jack",        # Cyrillic look-alike letter
])
def test_invisible_and_lookalike_characters_do_not_hide_a_pin_action(text):
    assert unsafe_pin_actions(plan(next_safe_check=text), REF), repr(text)


@pytest.mark.parametrize("text", [
    "Keep the unit unpowered and verify the printed mainboard revision.",
    "Inspect outer battery contacts, with batteries removed.",
    "Photograph the silkscreen marking near the battery compartment.",
    "Inspect the A53 phone and the ADC12 chip, model U7 revision 3.",   # no separator: not DES-number
    "Inspect the HDMI port for bent pins.",                 # no number, no part named after the pin
])
def test_plain_external_inspection_is_still_allowed(text):
    assert not unsafe_pin_actions(plan(next_safe_check=text), REF)


def test_gate_stays_off_when_board_is_verified_or_flag_missing():
    p = plan(next_safe_check="DC1 pin 4")
    assert not unsafe_pin_actions(p, {"target_board_physically_verified": True})
    assert not unsafe_pin_actions(p, {})
    assert not unsafe_pin_actions(p, None)


@pytest.mark.parametrize("phrase", [
    "DC1, pin 4", "DC1 \u2014 pin 4", "DC1 - pin 4", "DC1: pin 4", "DC1; pin 4",
    "DC1 / pin 4", "DC1, terminal", "DC1 \u2014 pad", "Look for SW1 markings, terminal corrosion",
    "Probe pin 4, DC1", "Inspect pins of the DC jack", "Inspect the pin of the barrel jack",
    "Look at the pin on the USB connector", "Look at bent pins on an HDMI port",
    "E5 pin 2", "E5 terminal", "E5-2", "Probe the E5 pad",
])
def test_separators_and_unconditional_pin_of_part_phrasings_are_caught(phrase):
    assert unsafe_pin_actions(plan(next_safe_check=phrase), REF), phrase


def test_evidence_ids_are_exempt_only_when_they_are_real_evidence_ids():
    p = plan(summary="Damage is consistent with E1 and E2; bent pins.")
    assert unsafe_pin_actions(p, REF)                                     # no ID set: not exempt
    assert not unsafe_pin_actions(p, REF, evidence_ids={"E1", "E2"})     # real evidence IDs
    q = plan(summary="Damage is consistent with E5; bent pins.")
    assert unsafe_pin_actions(q, REF, evidence_ids={"E1", "E2"})         # E5 is not one of them
    r = plan(next_safe_check="Probe E5 pin 2 and the E5 terminal")
    assert unsafe_pin_actions(r, REF, evidence_ids={"E1", "E2"})


# Differential check against the ORIGINAL gate: whatever it caught must still be caught.
_ORIGINAL = re.compile(
    r"(?i)\b(?:[A-Z]{1,3}\d{1,4})\s*(?:pin\s*#?\s*\d+|[.]\d+|pins\s*\d+\s*(?:and|to|-)\s*\d+)\b"
    r"|\bpin\s*#?\s*\d+\s+(?:on|of|at)\s+[A-Z]{1,3}\d{1,4}\b"
)


def _corpus():
    designators = ["DC1", "U7", "BT1", "SW1", "J12", "IC3", "Q1", "R100", "E5", "E1", "TP4", "CN2"]
    forms = ["{d} pin 4", "{d} pin4", "{d} pin #4", "{d} pin# 4", "{d}.4", "{d}.12",
             "{d} pins 3 and 4", "{d} pins 1 to 2", "{d} pins 1 - 2", "{d}pin 3",
             "pin 4 of {d}", "pin 4 on {d}", "pin4 at {d}", "pin #4 of {d}", "PIN 4 OF {d}"]
    leads = ["", "Check ", "Probe the ", "Measure continuity between ", "With power removed, meter ",
             "No pin-specific advice, but "]
    tails = ["", " and BT1 pin 1", " with a meter.", ", then stop"]
    for d in designators:
        for f in forms:
            for lead in leads:
                for tail in tails:
                    yield lead + f.format(d=d) + tail


def test_everything_the_original_gate_caught_is_still_caught():
    checked = 0
    for text in _corpus():
        if _ORIGINAL.search(text):
            checked += 1
            assert unsafe_pin_actions(plan(next_safe_check=text), REF), text
            assert unsafe_pin_actions(plan(next_safe_check=text), REF, evidence_ids={"E1", "E5"}), text
    assert checked > 1000


@pytest.mark.parametrize("phrase", [
    "pin\u20143", "pin \u2022 3", "pin\u00b73", "pin - 3", "pin-3", "pin:3", "pin\u20264", "pin \u2026 4",
    "DC1 pin\u20144", "DC1\u20144", "DC1\u20264", "pad\u2013 4", "terminal \u2022 2",
    "the fourth\u2014pin", "pins\u20143",
])
def test_dash_bullet_and_ellipsis_between_pin_and_number_are_flagged(phrase):
    assert unsafe_pin_actions(plan(next_safe_check=phrase), REF), phrase
