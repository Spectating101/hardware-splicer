from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class BearingDims:
    id_mm: float
    od_mm: float
    width_mm: float


def get_bearing_dims(bearing: Literal["608zz", "625zz"]) -> BearingDims:
    """
    Common deep-groove ball bearing sizes:
      - 608: 8×22×7 mm (ID×OD×W)
      - 625: 5×16×5 mm
    """
    if bearing == "625zz":
        return BearingDims(id_mm=5.0, od_mm=16.0, width_mm=5.0)
    return BearingDims(id_mm=8.0, od_mm=22.0, width_mm=7.0)

