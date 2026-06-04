from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Nema17Pattern:
    hole_spacing_mm: float = 31.0
    bore_d_mm: float = 22.0
    mount_hole_d_mm: float = 3.4  # M3 clearance-ish

    def bolt_xy(self) -> dict[str, tuple[float, float]]:
        """
        Bolt hole centers in the motor face frame, relative to motor center:
          - ne, nw, se, sw (north/east, etc.)
        """
        s = self.hole_spacing_mm / 2.0
        return {"ne": (s, s), "nw": (-s, s), "se": (s, -s), "sw": (-s, -s)}


NEMA17 = Nema17Pattern()
