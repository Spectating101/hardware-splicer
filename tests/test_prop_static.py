from __future__ import annotations

import math
import zipfile

import pytest

from hardware_splicer.prop_static import G, RHO, hover


def _zip(tmp_path, ct=0.1, cp=0.05):
    path = tmp_path / "db.zip"
    rows = "\n".join(f"{rpm} {ct} {cp}" for rpm in (5000, 10000, 15000, 20000))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("UIUC-propDB/volume-2/data/test_3x2_static_0001rd.txt", "RPM CT CP\n" + rows + "\n")
    return path


def test_hover_rpm_and_power_follow_the_coefficients(tmp_path) -> None:
    d = 3 * 0.0254
    rpm = 12000
    thrust_g = 0.1 * RHO * (rpm / 60) ** 2 * d ** 4 / G * 1000
    result = hover(_zip(tmp_path), "test_3x2", thrust_g)
    assert result["rpm"] == pytest.approx(rpm, rel=0.02)  # linear interpolation of thrust between rows
    assert result["shaft_power_w"] == pytest.approx(0.05 * RHO * (result["rpm"] / 60) ** 3 * d ** 5, rel=1e-3)
    ideal = (thrust_g / 1000 * G) ** 1.5 / math.sqrt(2 * RHO * math.pi * d ** 2 / 4)
    assert result["figure_of_merit"] == pytest.approx(ideal / result["shaft_power_w"], abs=1e-3)


def test_outside_the_measured_range_is_refused(tmp_path) -> None:
    with pytest.raises(ValueError, match="not extrapolated"):
        hover(_zip(tmp_path), "test_3x2", 500)
