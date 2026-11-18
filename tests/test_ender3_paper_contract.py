"""Paper/input boundary regressions; the full native study runs separately."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path

import pytest

from hardware_splicer import digital_cases as cases


SCRIPTS = cases.PLOTTER.root / 'scripts'
spec = importlib.util.spec_from_file_location('ender3_paper_common_test', SCRIPTS / 'common.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
LEGACY = {'drawing_width_mm': 100, 'drawing_height_mm': 80,
          'pen_diameter_mm': 10, 'pen_lift_mm': 3}
A5 = {**LEGACY, 'drawing_width_mm': 190, 'drawing_height_mm': 128,
      'pen_diameter_mm': 12, 'paper_width_mm': 210, 'paper_height_mm': 148}


def test_old_four_setting_file_keeps_square_sheet(tmp_path, monkeypatch):
    (tmp_path / 'sources').mkdir()
    (tmp_path / 'sources/interface.json').write_text(json.dumps({'pen_offset_from_nozzle_xy_mm': [0, -19.2]}))
    (tmp_path / 'requirements.json').write_text(json.dumps(LEGACY))
    monkeypatch.setattr(common, 'ROOT', tmp_path)
    req = common.read_requirements()
    assert req == {**LEGACY, 'paper_width_mm': 180., 'paper_height_mm': 180.}
    archived = replace(cases.PLOTTER, requirements={key: cases.PLOTTER.requirements[key] for key in LEGACY})
    assert archived.validate(LEGACY) == LEGACY


def test_a5_has_real_ten_mm_margins_with_unchanged_source_travel():
    req = common.validate_requirements(A5)
    assert cases.PLOTTER.validate(A5) == req
    assert (req['paper_width_mm'] - req['drawing_width_mm']) / 2 == 10
    assert (req['paper_height_mm'] - req['drawing_height_mm']) / 2 == 10
    x = (117.5 - 190 / 2, 117.5 + 190 / 2)
    y = (117.5 - 128 / 2 + 19.2, 117.5 + 128 / 2 + 19.2)
    assert x == (22.5, 212.5)
    assert y == pytest.approx((72.7, 200.7))
    assert min(*x, *y) >= 0 and max(*x, *y) <= 235


@pytest.mark.parametrize('updates', [
    {'paper_width_mm': 209.9}, {'paper_height_mm': 147.9},
    {'paper_width_mm': 221}, {'paper_height_mm': 99},
    {'drawing_width_mm': 190.1, 'paper_width_mm': 220},
    {'drawing_height_mm': 140.1, 'paper_height_mm': 180},
    {'paper_width_mm': float('nan')}, {'paper_height_mm': float('inf')},
    {'paper_width_mm': True}, {'paper_height_mm': 10**400},
    {'paper_width_mm': '210'}, {'unregistered_paper_x': 0},
])
def test_invalid_or_coupled_invalid_paper_never_enters_native_build(updates):
    req = {**A5, **updates}
    with pytest.raises(ValueError):
        common.validate_requirements(req)
    with pytest.raises(ValueError):
        cases.PLOTTER.validate(req)


def test_wider_viewport_requires_explicit_larger_sheet():
    with pytest.raises(ValueError, match='10 mm'):
        cases.PLOTTER.validate({**LEGACY, 'drawing_width_mm': 190})
    with pytest.raises(ValueError, match='10 mm'):
        common.validate_requirements({**LEGACY, 'drawing_width_mm': 190})


def test_native_guard_checks_compensated_whole_viewport_not_only_ink():
    with pytest.raises(ValueError, match='controller travel'):
        common.validate_requirements(A5, tool_offset_xy_mm=(0, -60))


def test_registered_and_native_bounds_stay_in_agreement():
    assert {key: value[1:] for key, value in cases.PLOTTER.requirements.items()} == common.BOUNDS
