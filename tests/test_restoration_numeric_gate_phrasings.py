"""The numeric cutoff gate must catch unit words, symbols, comparators and ranges."""
import pytest

from hardware_splicer.restoration_numeric_truth_gate import (
    UnsupportedQuantitativeThreshold, reject_unsourced_thresholds, unsourced_thresholds,
)

LEDGER = {"unresolved_source_ids": ["no_component_datasheet_provided",
                                    "no_verified_meter_observations"]}


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
    "greater than 0.4 amps", "under 4.5 volts", "<= 4.5V", "~4.5 V",
    "between 0.05 and 0.4 A", "above 1.5k ohm", "400 mA or more", "lower than 5V",
    "exceed 45 C", "more than 2 ohms", "2 Ω or less",
    # further spellings of the same idea
    ">= 3.3 V", "≥ 3.3V", "≤ 10 mA", "about 4.5 volts", "roughly 12 V",
    "approximately 0.4 A", "no more than 2 A", "not to exceed 60 °C",
    "up to 15 W", "maximum of 20 W", "4.5 V minimum", "4.5 V max", "5 V and above",
    "2.2 kOhm or less", "10 kΩ or lower", "from 4.5 to 5.5 V", "4.5-5.5 V",
    "4.5 to 5.5 volts", "greater than about 2 ohms", "above the 4.5 V mark",
    "higher than 100 kHz", "below 1 MHz", "at least 2.5 milliamps",
    "over 45 degrees C", "exceeds 45 degrees Celsius", "1.5 kilohms or more",
    "0.4 A+", "a 4.5 V cutoff", "4.5 V is the pass/fail threshold",
    "threshold of 4.5 V", "under 4,5 V", "under .5 A", "less than 4.7 µF".replace("µF", "µA"),
    "fewer than 3 ohms", "above 12 V",
]


@pytest.mark.parametrize("phrase", PHRASES)
@pytest.mark.parametrize("field", ["next_safe_check", "summary", "uncertainty",
                                   "hyp.mechanism", "hyp.why", "hyp.safe_test"])
def test_phrasing_caught_in_every_free_text_field(phrase, field):
    text = f"A healthy unit shows {phrase} on the rail."
    p = plan()
    if field.startswith("hyp."):
        p["hypotheses"][0][field[4:]] = text
    else:
        p[field] = text
    assert unsourced_thresholds(p, LEDGER), (phrase, field)
    with pytest.raises(UnsupportedQuantitativeThreshold):
        reject_unsourced_thresholds(p, LEDGER)


@pytest.mark.parametrize("text", [
    "Inspect external certified 5V USB power meter; record the reading without assuming a healthy threshold.",
    "Inspect the connector visually.",
    "Use a USB charger rated 5V and note whether the screen reacts.",
    "Compare cable 1 with cable 2 and check pin 3.",
    "Photograph the board within 2 minutes.",
])
def test_nominal_values_and_plain_text_still_allowed(text):
    assert not unsourced_thresholds(plan(next_safe_check=text), LEDGER)


def test_no_sourced_number_allow_path_is_documented_by_behaviour():
    # The gate reads only the ledger's unresolved ids; source claims are not
    # consulted, so a figure present in a cited source is still banned.
    ledger = dict(LEDGER, claims=[{"value": 4.5, "unit": "V"}])
    assert unsourced_thresholds(plan(next_safe_check="Failure below 4.5 V per the guide"), ledger)


@pytest.mark.parametrize("text", [
    "Expect gre​ater than 2 ohms.",
    "Expect greater th­an 2 ohms.",
    "Expect more than 2 oh⁠ms.",
    "Expect more than 2 оhms.",          # Cyrillic o inside a unit word
    "Expect mоre than 2 ohms.",          # Cyrillic o inside a comparator
    "Expect above ４.5 V.",               # fullwidth digit
    "Expect above 4.5 V and fine.",
])
def test_invisible_and_lookalike_characters_do_not_hide_a_cutoff(text):
    assert unsourced_thresholds(plan(next_safe_check=text), LEDGER), repr(text)


def test_extra_keys_and_mapping_keys_are_scanned():
    p = plan()
    p["notes"] = {"above 12 V": "x"}
    assert unsourced_thresholds(p, LEDGER)
    q = plan()
    q["extra"] = "reading below 4.5 volts"
    assert unsourced_thresholds(q, LEDGER)


@pytest.mark.parametrize("text,folded", [
    ("A healthy unit shows \u2265 4.5 V.", ">= 4.5 V"),
    ("A healthy unit shows \u2264 10 mA.", "<= 10 mA"),
    ("A healthy unit shows 4.5\u20135.5 V.", "4.5 - 5.5 V"),
    ("A healthy unit shows below\u00a04.5\u202fV.", "below 4.5 V"),
])
def test_typographic_comparators_fold_to_ascii_and_are_caught(text, folded):
    rows = unsourced_thresholds(plan(next_safe_check=text), LEDGER)
    assert rows and any(folded in r["limit"] for r in rows), rows
    assert not any(r["explanation"].startswith("disallowed") for r in rows)


def test_accents_and_cyrillic_are_still_rejected_by_the_numeric_gate():
    for text in ("Check the caf\u00e9 rail", "Check the \u0431\u0443\u043c rail"):
        rows = unsourced_thresholds(plan(next_safe_check=text), LEDGER)
        assert rows and rows[0]["explanation"] == "disallowed_non_ascii_letter"


@pytest.mark.parametrize("text", [
    "A healthy unit shows greater\u2026than 2 ohms",
    "A healthy unit shows at\u2026least 0.4 A",
    "A healthy unit shows more than\u2026 2 ohms",
    "A healthy unit shows below \u2026 4.5 V",
    "A healthy unit shows 4.5\u2026V or less",
    "A healthy unit shows up\u2026to 15 W",
    "A healthy unit shows 4.5 V or\u2026more",
    "A healthy unit shows 45 degrees\u2026C or more",
    "Anything above 5\u2014V is fine",
])
def test_ellipsis_and_dash_gaps_do_not_hide_a_cutoff(text):
    assert unsourced_thresholds(plan(next_safe_check=text), LEDGER), repr(text)


def test_not_equal_sign_stays_rejected_rather_than_folded():
    rows = unsourced_thresholds(plan(next_safe_check="Reading \u2260 4.5 V"), LEDGER)
    assert rows and rows[0]["explanation"] == "disallowed_non_ascii_letter"
