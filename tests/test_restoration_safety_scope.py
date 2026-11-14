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
