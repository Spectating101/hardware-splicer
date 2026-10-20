from __future__ import annotations

import importlib.util
import pytest

from eval.chemical_science.reference_benchmark_v1 import run


def test_independent_chemistry_reference_smoke_suite():
    if any(importlib.util.find_spec(name) is None
           for name in ("thermo", "CoolProp", "cantera")):
        pytest.skip("Optional chemistry reference engines absent")
    report = run()
    assert report["authored_cases"] >= 15
    assert report["passed"] == report["authored_cases"], [
        row for row in report["cases"] if not row["passed"]
    ]
    assert report["bench_validation"] is False
    assert report["physical_action_authorized"] is False
    crosscheck = next(row for row in report["cases"]
                      if row["case"] == "cross_model_water_374K")
    assert "reference_models_disagree_on_phase" in crosscheck["observations"]["blockers"]
