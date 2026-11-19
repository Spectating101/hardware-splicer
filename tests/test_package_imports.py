"""Public SDK exports and direct module imports in a fresh interpreter."""

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest


@pytest.mark.parametrize("source", [
    """
    import sys
    import hardware_splicer as hs
    assert "hardware_splicer" in sys.modules
    assert "pydantic" not in sys.modules
    assert "hardware_splicer.compiler" not in sys.modules
    assert set(hs.__all__).issubset(dir(hs))
    from hardware_splicer import *
    from hardware_splicer.schemas import HardwareCompileSpec as spec
    assert HardwareCompileSpec is spec
    assert hs.sdk.compose_design is compose_design
    assert not hasattr(hs, "nonexistent_export")
    """,
    """
    from hardware_splicer.integrations.schematic_export import write_schematic_for_netlist
    from hardware_splicer.netlist import compile_netlist_to_artifacts
    from hardware_splicer.netlist.compile import compile_netlist_to_artifacts as compile_impl
    from hardware_splicer.pcb import compile_graph_to_artifacts
    from hardware_splicer.pcb.geometry_compile import compile_graph_to_artifacts as geometry_impl
    assert compile_netlist_to_artifacts is compile_impl
    assert compile_graph_to_artifacts is geometry_impl
    """,
    """
    from hardware_splicer import physical_evidence_ledger as ledger
    from hardware_splicer import engineering_action as action
    from hardware_splicer import engineering_status as status
    assert ledger._chronology_validation_installed
    assert status._containment_deduplication_installed
    assert status._physical_revalidation_installed
    assert action.build_engineering_status is status.build_engineering_status
    """,
])
def test_cold_import(source):
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    result = subprocess.run(
        [sys.executable, "-c", dedent(source)], cwd=root, env=env,
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
