"""A prohibition covers only its own clause; it never masks a later command."""
import pytest

from hardware_splicer.restoration_reasoning_agent import UNSAFE, validate_model_output
from hardware_splicer.restoration_safety_semantics import unsafe_action_findings


def plan(text, field="next_safe_check"):
    p = {
        "summary": "The exact cause is unknown.",
        "hypotheses": [{"mechanism": "m", "why": "w", "evidence_ids": ["E1"],
                        "safe_test": "Inspect the exterior with all power removed."}],
        "next_safe_check": "With the unit unplugged, inspect the connector.",
        "uncertainty": "No meter data.", "abstain": False,
    }
    if field.startswith("hyp."):
        p["hypotheses"][0][field[4:]] = text
    else:
        p[field] = text
    return p


MASKED = [
    "Do not bypass the fuse, but jumper the battery protection",
    "Never bypass the fuse. Then short out the thermal fuse.",
    "Do not bypass the fuse; short out the thermal fuse.",
    "Do not bypass the fuse and then short out the thermal fuse.",
    "Never bypass the fuse, then jumper the battery protection.",
    "Do not bypass the fuse, jumper the battery protection.",
    "Do not bypass the fuse: short out the thermal fuse.",
    "Do not probe live mains instead probe the energized PSU output.",
    "Instead of waiting, bypass the thermal fuse.",
    "Never touch the case\nbypass the thermal fuse",
    "Do not bypass the fuse. Jumper the battery protection. Do not do anything else.",
    "Jumper the battery protection; do not hesitate.",
    "Do not forget to bypass the fuse.",
    "Do not hesitate to bypass the fuse.",
    "Never fail to jumper the battery protection.",
    "Do not wait, bypass the fuse.",
    "Do not bypass the fuse unless you jumper the battery protection first.",
    "Do not bypass the fuse; however bridge the safety interlock.",
    "Do not bypass the fuse. Alternatively bridge the safety interlock.",
]


@pytest.mark.parametrize("text", MASKED)
def test_prohibition_does_not_mask_a_later_command(text):
    assert unsafe_action_findings(plan(text), UNSAFE), text
    with pytest.raises(ValueError, match="unsafe"):
        validate_model_output(plan(text), {"evidence": [{"id": "E1", "text": "x"}]})


@pytest.mark.parametrize("field", ["summary", "uncertainty", "hyp.mechanism", "hyp.why", "hyp.safe_test"])
def test_masked_command_found_in_every_field(field):
    assert unsafe_action_findings(plan("Never bypass the fuse. Then short out the thermal fuse.", field), UNSAFE)


@pytest.mark.parametrize("text", [
    "Do not bypass the fuse",
    "Never probe live mains voltage.",
    "Never probe, measure or touch live mains.",
    "Do not attempt to recharge a damaged battery cell.",
    "Avoid bridging the safety interlock.",
    "Do not bypass the fuse and do not jumper the battery protection.",
    "Do not bypass the fuse, and never short out the thermal fuse.",
    "Do not bypass the fuse. Never short out the thermal fuse.",
    "It is not safe to measure live AC power.",
])
def test_pure_prohibitions_still_pass(text):
    assert unsafe_action_findings(plan(text), UNSAFE) == [], text


# --- review findings: negation reach, walker coverage, normalisation ---------

NEGATION_TOO_GENEROUS = [
    "Do not bypass the fuse and jumper the battery protection.",
    "Never touch the case and bypass the fuse.",
    "Do not open the case, bypass the fuse.",
    "Never use a wire to bridge the interlock.",
    "Do not refrain from bypassing the fuse.",
    "Do not not bypass the fuse.",
    "Never wait or bypass the fuse.",
    "Do not bypass the fuse jumper the battery protection",
    "Do not bypass the fuse jumper the battery protection",
    "Do not bypass the fuse\u0085jumper the battery protection",
    "Do not bypass the fuse。jumper the battery protection",
    "Do not bypass the fuse… jumper the battery protection",
    "Do not bypass the fuse…bypass the thermal fuse",
    "Never probe the case or probe live mains.",
    "Do not turn it off and short out the thermal fuse.",
]


@pytest.mark.parametrize("text", NEGATION_TOO_GENEROUS)
def test_negation_reaches_only_the_directly_following_hazard_verb(text):
    assert unsafe_action_findings(plan(text), UNSAFE), repr(text)


@pytest.mark.parametrize("text", [
    "Do not ever try to bypass the fuse.",
    "Never attempt to recharge a swollen battery.",
    "Do not probe, measure or touch live mains.",
    "Never probe or measure live mains voltage.",
])
def test_fixed_fillers_and_pure_verb_lists_remain_prohibitions(text):
    assert unsafe_action_findings(plan(text), UNSAFE) == [], text


def test_walker_scans_keys_and_stray_evidence_ids():
    base = plan("Inspect the exterior.")
    extra_key = dict(base, **{"Bypass the thermal fuse": "ok"})
    assert unsafe_action_findings(extra_key, UNSAFE)
    top = dict(base, evidence_ids=["Bypass the thermal fuse"])
    assert unsafe_action_findings(top, UNSAFE)
    hyp = plan("Inspect the exterior.")
    hyp["hypotheses"][0]["evidence_ids"] = ["Bypass the thermal fuse"]
    assert unsafe_action_findings(hyp, UNSAFE)
    nested = plan("Inspect the exterior.")
    nested["hypotheses"][0]["extra"] = {"evidence_ids": ["bypass the thermal fuse"]}
    assert unsafe_action_findings(nested, UNSAFE)
    not_a_list = plan("Inspect the exterior.")
    not_a_list["hypotheses"][0]["evidence_ids"] = "bypass the thermal fuse"
    assert unsafe_action_findings(not_a_list, UNSAFE)
    clean = plan("Inspect the exterior.")
    assert unsafe_action_findings(clean, UNSAFE) == []
    clean["hypotheses"][0]["evidence_ids"] = ["E1", "E12"]
    assert unsafe_action_findings(clean, UNSAFE) == []


INVISIBLE = [
    "Do not bypass the fuse, bu​t jumper the battery protection.",
    "Do not bypass the fuse, b­ut jumper the battery protection.",
    "Never bypass the fuse. Th‍en short out the thermal fuse.",
    "Never bypass the fuse. T⁠hen short out the thermal fuse.",
    "By​pass the thermal fuse.",
    "Jum⁠per the battery protection.",
    "Pro﻿be live mains voltage.",
    "Byp‮ass the thermal fuse.",
    "Byp\x01ass the thermal fuse.",
    "Býpass the thermal fuse.",
    "Sh​ort out the thermal fuse.",
    "Fa‍ctory reset the phone.",
    "Ｂypass the thermal fuse.",
    # Cyrillic look-alike letters inside a hazardous verb
    "Bуpass the thermal fuse.",
    "Bypaѕs the thermal fuse.",
    "Prоbе live mains voltage.",
    "Do not bypass the fuse, but jуmper the battery protection.",
]


@pytest.mark.parametrize("text", INVISIBLE)
def test_invisible_and_lookalike_characters_do_not_hide_a_command(text):
    assert unsafe_action_findings(plan(text), UNSAFE), repr(text)


def test_unit_symbols_are_allowed_but_accents_are_not():
    # Known limitation: any letter outside ASCII plus the unit symbols
    # (omega, mu, degree) is rejected, so legitimately accented text fails.
    ok = plan("A 10 k\u03a9 resistor, a 5 \u00b5A draw and 45 \u00b0C are all plain units.")
    assert unsafe_action_findings(ok, UNSAFE) == []
    accented = unsafe_action_findings(plan("Inspect the caf\u00e9 area."), UNSAFE)
    assert [f["reason"] for f in accented] == [REASON_LETTER]


# --- second review: reject rather than repair ---------------------------------

REASON_CONTROL = "disallowed_control_or_format_character"
REASON_LETTER = "disallowed_non_ascii_letter"


def reasons(text):
    return {f["reason"] for f in unsafe_action_findings(plan(text), UNSAFE)}


@pytest.mark.parametrize("text", [
    "Never bypass the fuse.\x00Then do nothing.",
    "Do not bypass the fuse.\x01 Inspect.",
    "Do not bypass the fuse.\x7f Inspect.",
    "Do not byp\x1bass the fuse.",
    "Do not bypass the fuse.\u200b Inspect.",
    "Do not bypass the fuse.\u202e Inspect.",
    "Do not bypass the fuse.\u0301 Inspect.",
    "Do not bypass the fuse.\u20dd Inspect.",
    "Do not bypass the fuse.\ufeff Inspect.",
    "Do not bypass the fuse.\u00ad Inspect.",
    "Do not bypass the fuse.\ud800 Inspect.".encode("utf-16", "surrogatepass").decode("utf-16", "surrogatepass"),
    "Do not bypass the fuse.\ue000 Inspect.",
])
def test_control_format_and_combining_characters_fail_the_gate_outright(text):
    assert REASON_CONTROL in reasons(text), repr(text)
    with pytest.raises(ValueError, match="unsafe"):
        validate_model_output(plan(text), {"evidence": [{"id": "E1", "text": "x"}]})


def test_carriage_returns_become_line_breaks_not_deletions():
    assert REASON_CONTROL not in reasons("Never probe live mains.\r\nInspect the exterior.")
    assert REASON_CONTROL not in reasons("Never probe live mains.\rInspect the exterior.")
    assert unsafe_action_findings(plan("Never probe live mains.\r\nInspect the exterior."), UNSAFE) == []
    # a deleted \r would have glued these into one benign-looking word
    assert unsafe_action_findings(plan("Do not wait\rBypass the thermal fuse"), UNSAFE)
    assert unsafe_action_findings(plan("Do not bypass the fuse\r\njumper the battery protection"), UNSAFE)


@pytest.mark.parametrize("text", [
    "\u0432\u0443\u0440\u0430\u0455\u0455 the thermal fuse",   # whole word in Cyrillic
    "\u03c1\u03c1\u03bf\u03b2\u03b5 live mains",                 # whole word in Greek
    "Bypass the thermal fuse \u0430",                               # stray Cyrillic letter anywhere
    "Inspect \u00fc the unit",
    "Inspect the unit \u00df",
    "Inspect the \u0131 unit",                                      # dotless i
    "Inspect the unit \u0661",                                      # Arabic-indic digit
])
def test_any_letter_outside_ascii_and_unit_symbols_is_rejected(text):
    assert REASON_LETTER in reasons(text), repr(text)
    with pytest.raises(ValueError, match="unsafe"):
        validate_model_output(plan(text), {"evidence": [{"id": "E1", "text": "x"}]})


def test_non_ascii_mapping_key_is_rejected():
    p = plan("Inspect the exterior.")
    p["\u0432\u0443\u0440\u0430\u0455\u0455"] = "x"
    assert REASON_LETTER in {f["reason"] for f in unsafe_action_findings(p, UNSAFE)}


@pytest.mark.parametrize("text", [
    "Do not\nbypass the fuse.",
    "Never\r\nbypass the fuse.",
    "Never probe,\nmeasure or touch live mains.",
    "Do not attempt to\nbypass the fuse.",
    "Avoid\u2028bridging the interlock.",
    "Never\u0085probe live mains.",
])
def test_negation_never_reaches_across_a_line_break(text):
    assert unsafe_action_findings(plan(text), UNSAFE), repr(text)


def test_lists_on_one_line_are_still_prohibitions():
    assert unsafe_action_findings(plan("Never probe, measure or touch live mains."), UNSAFE) == []


# --- third review: unit symbols only in unit position; deny non-ASCII by default

@pytest.mark.parametrize("text", [
    "jµmper the thermal fuse",           # micro sign inside a verb
    "jμmper the thermal fuse",           # Greek mu inside a verb
    "shΩrt out the thermal fuse",        # omega inside a verb
    "shΩrt out the thermal fuse",        # ohm sign inside a verb
    "Bypass the thermal fuse µ",         # stray mu
    "Bypass the thermal fuse 5 µ here",  # mu not followed by a unit letter
    "Bypass the thermal fuse 5 µAx",     # unit letter not at a word boundary
    "Bypass the thermal fuse Ω",          # omega without a digit before it
    "Bypass the thermal fuse 5 kΩx",      # omega not at a word boundary
    "Bypass the thermal fuse 5 xΩ",       # wrong prefix before omega
    "Inspect the unit⠀then bypass the thermal fuse",   # Braille blank
    "Inspect the unit then bypass the thermal fuse",   # Ogham space mark
    "Inspect the unit then wait",         # em space is folded by NFKC and is fine, see below
])
def test_unit_symbols_are_accepted_only_in_unit_position(text):
    if " " in text:
        assert REASON_LETTER not in reasons(text)
        return
    assert REASON_LETTER in reasons(text), repr(text)
    with pytest.raises(ValueError, match="unsafe"):
        validate_model_output(plan(text), {"evidence": [{"id": "E1", "text": "x"}]})


@pytest.mark.parametrize("text", [
    "Inspect the unit \u2192 then wait",       # arrow
    "Inspect the unit \u00a9",                 # copyright sign
    "Inspect the unit \u2248 5",               # approximately-equal sign (not in the fold table)
    "Inspect the caf\u00e9",                   # accented letter
    "Inspect the unit \u0431\u0443\u043c",   # Cyrillic word
])
def test_every_other_non_ascii_character_fails_whatever_its_category(text):
    assert REASON_LETTER in reasons(text), repr(text)


@pytest.mark.parametrize("text", [
    "A 10 µA draw, 10µA, 10 μF, 5 µs and 2 µg.",
    "A 4.7 kΩ resistor, 10Ω, 2 MΩ and 5 Ω.",
    "About 45 °C, ± 5 and 3 × 4.",
])
def test_unit_position_symbols_remain_allowed(text):
    assert unsafe_action_findings(plan(text), UNSAFE) == [], text


# --- typography is folded to ASCII, never rejected, and then matched normally --

@pytest.mark.parametrize("dash", ["\u2013", "\u2014", "\u2012", "\u2015", "\u2212"])
def test_dash_between_negator_and_verb_breaks_the_negation(dash):
    assert unsafe_action_findings(plan(f"Never bypass the fuse {dash} jumper the battery protection"), UNSAFE)
    assert unsafe_action_findings(plan(f"Do not wait{dash}bypass the thermal fuse"), UNSAFE)


@pytest.mark.parametrize("text", [
    "Never bypass the fuse\u2026 jumper the battery protection",
    "Never bypass the fuse \u2022 jumper the battery protection",
    "Never bypass the fuse \u00b7 jumper the battery protection",
    "Never\u00a0bypass the fuse. Then\u202fshort out the thermal fuse.",
    "Do not bypass the fuse, \u201cbut\u201d jumper the battery protection",
])
def test_folded_typography_still_hits_the_hazard_matchers(text):
    assert unsafe_action_findings(plan(text), UNSAFE), repr(text)


@pytest.mark.parametrize("text", [
    "Don\u2019t bypass the fuse. \u201cInspect\u201d the unit\u2026 then wait \u2014 carefully.",
    "Never probe live mains\u2009voltage; check the \u2018label\u2019 \u2013 externally only.",
    "Never probe\u00a0live mains.",
    "Inspect \u2022 photograph \u00b7 note the \u2033 mark and the \u201a case",
    "A 10 \u00b5A draw is not a fault \u2264 \u2265 are only symbols.",
])
def test_ordinary_typography_is_not_rejected(text):
    assert unsafe_action_findings(plan(text), UNSAFE) == [], repr(text)


def test_fold_table_adds_or_keeps_a_word_boundary():
    from hardware_splicer.restoration_safety_semantics import fold
    assert fold("a\u2014b") == "a - b"
    assert fold("\u2018x\u2019") == "'x'"
    assert fold("x\u2026y") == "x - y"   # CHANGED: runs of dashes/ellipses collapse to one gap token
    assert fold("a\u2022b") == "a - b"
    assert fold("a\u00b7b") == "a - b"
    assert fold("a\u00a0b\u202fc\u2009d\u2007e") == "a b c d e"
    assert fold("1\u22652") == "1>=2" and fold("1\u22642") == "1<=2"
    assert fold("1\u22602") == "1\u22602"      # not folded: stays a rejected non-ASCII character


# --- folded forms must be read by every downstream matcher ----------------------

@pytest.mark.parametrize("text", [
    "Never probe\u2014short the fuse",
    "Never\u2014bypass the fuse",
    "Never probe\u2013short the fuse",
    "Never\u2212bypass the fuse",
    "Do not\u2015jumper the battery protection",
])
def test_dash_between_words_is_a_negation_breaker_not_a_joiner(text):
    assert unsafe_action_findings(plan(text), UNSAFE), repr(text)


@pytest.mark.parametrize("text", [
    "Short\u2026out the thermal fuse",
    "Short \u2026 out the thermal fuse",
    "Short\u2014out the thermal fuse",
    "Jump\u2026start the swollen battery",
    "Factory\u2026reset the phone",
    "Probe live\u2026mains voltage",
    "Charge the damaged\u2026battery",
    "Short\u2026circuit the fuse",
])
def test_multiword_hazards_accept_any_non_word_gap(text):
    assert unsafe_action_findings(plan(text), UNSAFE), repr(text)


def test_not_equal_sign_is_not_folded_and_stays_rejected():
    assert REASON_LETTER in reasons("Reading \u2260 4.5 V is fine")
