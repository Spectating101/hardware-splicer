"""The known amp routing gap is pinned exactly, and fails loudly when it changes or is fixed."""

from __future__ import annotations

import pytest
from known_router_gaps import KNOWN_MODULES, xfail_known_amp_gap

KNOWN_MESSAGE = 'Nets "+3V3-9" and "+5V" cross on F.Cu — electrical short.'
EXACT = sorted(KNOWN_MODULES)


def test_the_documented_failure_on_the_documented_configuration_is_an_xfail() -> None:
    with pytest.raises(pytest.xfail.Exception):
        xfail_known_amp_gap(EXACT, False, [KNOWN_MESSAGE], kicad_errors=1)


def test_the_gap_being_fixed_fails_loudly_instead_of_passing_quietly() -> None:
    with pytest.raises(pytest.fail.Exception, match="fixed"):
        xfail_known_amp_gap(EXACT, True, [])


@pytest.mark.parametrize(
    "messages",
    [
        ['Nets "SDA" and "SCL" cross on F.Cu — electrical short.'],
        ['Nets "+3V3-9" and "GND" cross on F.Cu — electrical short.'],
        [KNOWN_MESSAGE, 'Nets "SDA" and "SCL" cross on F.Cu — electrical short.'],
        [KNOWN_MESSAGE, KNOWN_MESSAGE],
        ['Nets "+3V3-9" and "+5V" cross on B.Cu — electrical short.'],
        [],
    ],
)
def test_any_other_failure_on_the_documented_configuration_fails(messages: list) -> None:
    with pytest.raises(pytest.fail.Exception):
        xfail_known_amp_gap(EXACT, False, messages)


def test_an_extra_kicad_drc_error_fails() -> None:
    with pytest.raises(pytest.fail.Exception):
        xfail_known_amp_gap(EXACT, False, [KNOWN_MESSAGE], kicad_errors=3)


@pytest.mark.parametrize(
    "modules",
    [
        EXACT + ["bme280"],
        ["usb-power-5v", "max98357a-i2s-amp"],
        ["max98357a-i2s-amp", "esp32-devkit", "usb-power-5v", "terminal-block-2p"],
        ["usb-power-5v", "esp32-devkit"],
    ],
)
def test_other_configurations_are_never_covered_by_the_known_gap(modules: list) -> None:
    # Returns normally: the caller goes on to its ordinary assertions, which will fail on a real crossing.
    assert xfail_known_amp_gap(modules, False, [KNOWN_MESSAGE]) is None
