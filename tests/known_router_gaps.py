"""The one composed build the cosmetic preview router does not yet route cleanly.

The MAX98357A footprint has its separate speaker-terminal row (a real board plugs in header-first,
terminal elsewhere). With a USB supply and an ESP32 DevKitC V4 the preview router crosses the +5V
track with a 3V3-named signal track. Padding, shrinking or merging the rows to hide that would put
the footprint back to a layout the real board cannot plug into, so this exact build reports the
DRC error instead.

The expectation is pinned to exactly that failure and is strict: on this configuration the build
must fail with exactly one internal DRC error of this net pair (and at most one KiCad DRC error).
If the router ever routes it cleanly the callers fail ("gap fixed"), and any different failure
fails too. Every other build, including the same modules plus anything else, gets no allowance.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

import pytest

KNOWN_MODULES = frozenset({"usb-power-5v", "esp32-devkit", "max98357a-i2s-amp"})

_KNOWN_MESSAGE = re.compile(r'Nets "\+3V3-\d+" and "\+5V" cross on F\.Cu — electrical short\.')

REASON = (
    "known gap: the preview router crosses the +5V track with a 3V3-named signal track around the "
    "MAX98357A's separate speaker-terminal row; the footprint is not compressed to hide it"
)


def xfail_known_amp_gap(
    module_ids: Iterable[str],
    ok: bool,
    messages: Iterable[str],
    *,
    kicad_errors: Optional[int] = None,
) -> None:
    """Callers run every DRC-independent assertion first, then call this with the DRC outcome.

    Returns normally when the board is not the known configuration (ordinary assertions follow).
    On the known configuration: xfails only for exactly the documented failure, and fails loudly
    when the build now passes or fails any other way.
    """

    if frozenset(module_ids) != KNOWN_MODULES:
        return
    if ok:
        pytest.fail("the known amp routing gap is fixed: remove tests/known_router_gaps.py and its callers")
    errors = [str(m) for m in messages if m]
    if len(errors) != 1 or not _KNOWN_MESSAGE.fullmatch(errors[0]):
        pytest.fail(f"the amp build failed differently from the documented gap: {errors}")
    if kicad_errors is not None and kicad_errors > 1:
        pytest.fail(f"the amp build has {kicad_errors} KiCad DRC errors; the documented gap has one")
    pytest.xfail(REASON)
