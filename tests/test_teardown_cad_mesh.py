"""Fail-closed CAD renderer boundary contract tests."""
from pathlib import Path
import pytest
from hardware_splicer.teardown_cad_mesh import assemble_mesh

def test_reject_missing_native_inputs(tmp_path):
    with pytest.raises((OSError,ValueError)):
        assemble_mesh(tmp_path/"missing",tmp_path/"missing2",tmp_path/"out")
