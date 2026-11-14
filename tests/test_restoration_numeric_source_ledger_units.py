"""The ledger must match the unit at the source anchor and refuse negated statements."""
import copy
import hashlib

import pytest

from hardware_splicer.restoration_source_numeric_ledger import register_source_numeric_claims
from test_restoration_numeric_source_ledger import synthetic


def with_sources(tmp_path, vtt_extra="", html_extra=""):
    d, p = synthetic(tmp_path)
    if vtt_extra:
        text = p["ps5pro_early_captions"].read_text().replace(
            "00:08:10.000 --> 00:08:10.010", vtt_extra + "\n00:08:10.000 --> 00:08:10.010")
        p["ps5pro_early_captions"].write_text(text)
        d["sources"][0]["artifact_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    if html_extra:
        text = p["dmg_published_expectations"].read_text().replace("</html>", html_extra + "</html>")
        p["dmg_published_expectations"].write_text(text)
        d["sources"][1]["artifact_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    return d, p


def test_control_still_registers(tmp_path):
    d, p = with_sources(tmp_path)
    assert register_source_numeric_claims(d, local_artifacts=p)["claim_count"] == 6


@pytest.mark.parametrize("claim_fix", [
    # anchor says volts, claim says ohms
    dict(quantity="resistance", unit="ohm"),
    # anchor says volts, claim says amps
    dict(quantity="current", unit="A"),
])
def test_unit_of_claim_must_match_unit_at_anchor(tmp_path, claim_fix):
    d, p = with_sources(tmp_path)
    d["sources"][0]["claims"][1].update(claim_fix)  # "we have 12 volts"
    with pytest.raises(ValueError, match="unit"):
        register_source_numeric_claims(d, local_artifacts=p)


def test_ohms_anchor_cannot_become_volts(tmp_path):
    d, p = with_sources(tmp_path)
    d["sources"][0]["claims"][2].update(quantity="voltage", unit="V")  # "That is 2 ohms"
    with pytest.raises(ValueError, match="unit"):
        register_source_numeric_claims(d, local_artifacts=p)


def test_amps_anchor_cannot_become_volts(tmp_path):
    d, p = with_sources(tmp_path, vtt_extra="00:06:10.000 --> 00:06:10.010\nThe supply is rated 9 amps in total.\n")
    d["sources"][0]["claims"][1].update(
        value=9, anchor="rated 9 amps", window_start_s=370, window_end_s=375)
    with pytest.raises(ValueError, match="unit"):
        register_source_numeric_claims(d, local_artifacts=p)


def test_unitless_number_in_anchor_is_rejected(tmp_path):
    d, p = with_sources(tmp_path, vtt_extra="00:06:10.000 --> 00:06:10.010\nWe have 12 of them here.\n")
    d["sources"][0]["claims"][1].update(
        value=12, anchor="We have 12 of them", window_start_s=370, window_end_s=375)
    with pytest.raises(ValueError, match="unit"):
        register_source_numeric_claims(d, local_artifacts=p)


def test_prefix_is_normalised_not_ignored(tmp_path):
    base_extra = "00:06:10.000 --> 00:06:10.010\nThe meter shows 400 mA on the lead.\n"
    d, p = with_sources(tmp_path, vtt_extra=base_extra)
    c = d["sources"][0]["claims"][1]
    c.update(quantity="current", unit="A", anchor="shows 400 mA",
             window_start_s=370, window_end_s=375, value=400)
    with pytest.raises(ValueError, match="source passage|unit"):
        register_source_numeric_claims(d, local_artifacts=p)       # 400 A is wrong
    c["value"] = 0.4
    out = register_source_numeric_claims(d, local_artifacts=p)    # 0.4 A is right
    assert {x["claim_id"]: x for x in out["claims"]}["M2"]["value"] == 0.4


def test_range_inherits_the_trailing_unit_only(tmp_path):
    d, p = with_sources(tmp_path)
    d["sources"][1]["claims"][0].update(quantity="resistance", unit="ohm")  # "6.0 to 6.4 V"
    with pytest.raises(ValueError, match="unit"):
        register_source_numeric_claims(d, local_artifacts=p)


NEGATED_PUBLISHER = [
    ("should never expect 3 V on this pin", 3),
    ("do not rely on at least 7 V", 7),
    ("Do not expect below 2 V", 2),
    ("you cannot expect at least 8 V", 8),
    ("shouldn't expect above 9 V", 9),
]


@pytest.mark.parametrize("anchor,value", NEGATED_PUBLISHER)
def test_negated_publisher_statement_is_not_an_expectation(tmp_path, anchor, value):
    html = f"<p>You {anchor}.</p>" if not anchor.startswith(("Do ", "you ")) else f"<p>{anchor}.</p>"
    d, p = with_sources(tmp_path, html_extra=html)
    d["sources"][1]["claims"][1].update(value=value, upper_value=None, anchor=anchor)
    with pytest.raises(ValueError, match="negat"):
        register_source_numeric_claims(d, local_artifacts=p)


def test_negation_outside_the_anchor_is_found_in_the_source_sentence(tmp_path):
    d, p = with_sources(tmp_path, html_extra="<p>You should never expect at least 7 V on this pin.</p>")
    d["sources"][1]["claims"][1].update(value=7, upper_value=None, anchor="at least 7 V")
    with pytest.raises(ValueError, match="negat"):
        register_source_numeric_claims(d, local_artifacts=p)


def test_negated_creator_reading_is_not_a_reading(tmp_path):
    d, p = with_sources(tmp_path, vtt_extra="00:06:10.000 --> 00:06:10.010\nI would not expect 9 volts here.\n")
    d["sources"][0]["claims"][1].update(
        value=9, anchor="I would not expect 9 volts", window_start_s=370, window_end_s=375)
    with pytest.raises(ValueError, match="negat"):
        register_source_numeric_claims(d, local_artifacts=p)


def test_negation_in_a_neighbouring_sentence_does_not_block(tmp_path):
    d, p = with_sources(tmp_path, html_extra="<p>Do not open the case.</p><p>Expect at least 7 V.</p>")
    d["sources"][1]["claims"][1].update(value=7, upper_value=None, anchor="Expect at least 7 V")
    assert register_source_numeric_claims(d, local_artifacts=p)["claim_count"] == 6
