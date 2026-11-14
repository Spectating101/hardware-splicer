"""Pin-specific physical checks are withheld however they are phrased, in any field."""
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
])
def test_plain_external_inspection_is_still_allowed(text):
    assert not unsafe_pin_actions(plan(next_safe_check=text), REF)


def test_gate_stays_off_when_board_is_verified_or_flag_missing():
    p = plan(next_safe_check="DC1 pin 4")
    assert not unsafe_pin_actions(p, {"target_board_physically_verified": True})
    assert not unsafe_pin_actions(p, {})
    assert not unsafe_pin_actions(p, None)
