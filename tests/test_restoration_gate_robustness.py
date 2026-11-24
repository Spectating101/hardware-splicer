"""Gap canonicalisation, field-length cap and no catastrophic backtracking."""
import time

import pytest

from hardware_splicer.restoration_board_action_gate import unsafe_pin_actions
from hardware_splicer.restoration_numeric_truth_gate import unsourced_thresholds
from hardware_splicer.restoration_reasoning_agent import UNSAFE
from hardware_splicer.restoration_safety_semantics import (
    MAX_FIELD_CHARS, REASON_TOO_LONG, fold, unsafe_action_findings,
)

LEDGER = {"unresolved_source_ids": ["no_component_datasheet_provided"]}
REF = {"target_board_physically_verified": False}


def plan(text):
    return {"summary": "s", "next_safe_check": text, "uncertainty": "u", "abstain": False,
            "hypotheses": [{"mechanism": "m", "why": "w", "safe_test": "Inspect.", "evidence_ids": ["E1"]}]}


def gates(text):
    return {
        "unsafe": unsafe_action_findings(plan(text), UNSAFE),
        "numeric": unsourced_thresholds(plan(text), LEDGER),
        "pin": unsafe_pin_actions(plan(text), REF),
    }


# --- one canonical gap token ---------------------------------------------------

@pytest.mark.parametrize("text", [
    "cut—off", "cut…off", "cut - off", "cut-off", "cut off", "cutoff", "cut -- off",
    "cut––off", "cut ... off",
])
def test_cutoff_word_matches_every_gap_spelling(text):
    assert unsourced_thresholds(plan(f"The {text} is 4.5 V"), LEDGER), text


@pytest.mark.parametrize("text", [
    "Expect above -- 4.5 V", "Expect above --- 4.5 V", "Expect above —— 4.5 V",
    "Expect above ... 4.5 V", "Expect above … 4.5 V", "Expect above - - 4.5 V",
    "Expect greater — than 2 ohms", "Expect greater -- than 2 ohms",
    "Expect 4.5 — V or less", "Expect between 4.5 -- 5.5 V",
    "Expect at -- least 0.4 A",
])
def test_repeated_dashes_and_ellipses_do_not_hide_a_cutoff(text):
    assert unsourced_thresholds(plan(text), LEDGER), text


def test_fold_collapses_runs_of_gap_characters_into_one_token():
    assert fold("a" + "-" * 50 + "b") == "a - b"
    assert fold("a" + " - " * 50 + "b") == "a - b"
    assert fold("a" + " ... " * 50 + "b") == "a - b"
    assert fold("a —…-- b") == "a - b"
    assert fold("plain words stay") == "plain words stay"


# --- field length cap ----------------------------------------------------------

def test_overlong_field_is_rejected_with_a_distinct_reason_and_not_scanned():
    big = "x " * (MAX_FIELD_CHARS // 2 + 10)
    for name, rows in gates(big).items():
        key = {"unsafe": "reason", "numeric": "explanation", "pin": "reason"}[name]
        assert any(r[key] == REASON_TOO_LONG for r in rows), name
    exactly = "x" * MAX_FIELD_CHARS
    assert not any(r.get("reason") == REASON_TOO_LONG for r in gates(exactly)["unsafe"])


# --- timing ----------------------------------------------------------------------

REPEATS = {".": "." * 5000, "-": "-" * 5000, " - ": " - " * 5000, " ... ": " ... " * 5000,
           "-.": "-." * 2500, ". ": ". " * 2500, "—": "—" * 5000, " ": " " * 5000}
TRIGGERS = ["pin", "DC1", "above", "cut", "Never bypass", "greater than 4", "pin 3 of the", "short"]


@pytest.mark.parametrize("trigger", TRIGGERS)
@pytest.mark.parametrize("name", list(REPEATS))
def test_adversarial_repeats_finish_in_under_a_second(trigger, name):
    text = f"{trigger}{REPEATS[name]}x"
    start = time.perf_counter()
    gates(text)
    assert time.perf_counter() - start < 1.0, (trigger, name)


def test_many_hazard_matches_in_a_maximum_size_field_finish_quickly():
    text = ("Never bypass the fuse and short out the fuse. " * 600)[:MAX_FIELD_CHARS]
    start = time.perf_counter()
    gates(text)
    assert time.perf_counter() - start < 1.0


@pytest.mark.parametrize("trigger", ["DC1", "greater than 4", "pin", "10"])
@pytest.mark.parametrize("unit", [" ", "\n", "\t", " \n"])
def test_maximum_size_whitespace_runs_finish_in_under_a_second(trigger, unit):
    text = trigger + unit * ((MAX_FIELD_CHARS - 50) // len(unit)) + "x"
    start = time.perf_counter()
    gates(text)
    assert time.perf_counter() - start < 1.0
