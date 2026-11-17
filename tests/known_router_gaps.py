"""Builds whose real footprints the cosmetic preview router does not yet route cleanly.

The MAX98357A footprint now has its separate speaker-terminal row (a real board plugs in
header-first, terminal elsewhere). With a USB supply and an ESP32 DevKitC V4 the preview router
crosses the +5V track with a 3V3-named signal track. Padding, shrinking or merging the rows to hide
that would put the footprint back to a layout the real board cannot plug into, so these composed
builds report the DRC error instead and are expected to fail until the router can route them.
"""

from __future__ import annotations

from typing import Iterable

import pytest

AMP = "max98357a-i2s-amp"

REASON = (
    "known gap: the preview router crosses tracks around the MAX98357A's separate speaker-terminal "
    "row; the footprint is not compressed to hide it"
)


def xfail_if_amp_tracks_cross(module_ids: Iterable[str], messages: Iterable[str]) -> None:
    """xfail only for exactly this failure: the amp is on the board and every DRC error is a crossing."""
    errors = [m for m in messages if m]
    if AMP in set(module_ids) and errors and all(" cross on " in m for m in errors):
        pytest.xfail(REASON)
