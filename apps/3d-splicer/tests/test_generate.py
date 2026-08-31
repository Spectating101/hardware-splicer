import json
from pathlib import Path
import sys
import os
import re

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.template_loader import render_template
from core.cadquery_generator import script_to_stl
from core.validators import validate_stl


def test_mvp():
    """Test the complete MVP pipeline."""
    try:
        import cadquery  # type: ignore
        import trimesh  # type: ignore
    except Exception:
        pytest.skip("cadquery/trimesh not installed in this environment")

    # Load example description
    desc_path = Path(__file__).parent.parent / "examples" / "iphone7_desc.json"
    desc = json.loads(desc_path.read_text())

    # Render template
    code = render_template("phone_case.cq.j2", desc)
    assert "import cadquery" in code
    assert "result = case" in code

    # Generate STL
    out_path = Path("stl/test_case.stl")
    out_path.parent.mkdir(exist_ok=True)
    script_to_stl(code, out_path)

    # Validate STL exists
    assert out_path.exists()

    # Validate mesh properties
    report = validate_stl(str(out_path))
    assert report["faces"] > 0
    assert "bounds" in report

    # Clean up
    if out_path.exists():
        os.unlink(out_path)


def test_template_rendering():
    """Test template rendering with various inputs."""
    desc = {
        "pcb": {"width_mm": 50, "height_mm": 30, "thickness_mm": 1.0, "corner_radius_mm": 2.0},
        "enclosure": {"wall_mm": 1.5, "clearance_mm": 0.5, "lip_mm": 1.0, "fillet_mm": 0.8},
        "ports": [],
        "mounts": []
    }

    code = render_template("phone_case.cq.j2", desc)
    assert re.search(r"\bpcb_w\s*=\s*50\b", code)
    assert re.search(r"\bpcb_h\s*=\s*30\b", code)


def test_generated_code_runs_out_of_process_without_optional_cad_dependencies(tmp_path: Path) -> None:
    """The worker contract can be tested with a minimal result object."""

    output = tmp_path / "worker.stl"
    code = """
from pathlib import Path

class FakeShape:
    def val(self):
        return self

    def exportStl(self, path):
        Path(path).write_text('solid worker\\nendsolid worker\\n', encoding='utf-8')

result = FakeShape()
"""
    script_to_stl(code, output, timeout_s=5)
    assert output.read_text(encoding="utf-8").startswith("solid worker")


def test_generated_code_does_not_inherit_provider_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-worker")
    output = tmp_path / "no-secret.stl"
    code = """
import os
from pathlib import Path

if os.environ.get('OPENAI_API_KEY'):
    raise RuntimeError('provider credential leaked into CAD worker')

class FakeShape:
    def val(self):
        return self

    def exportStl(self, path):
        Path(path).write_text('solid isolated\\nendsolid isolated\\n', encoding='utf-8')

result = FakeShape()
"""
    script_to_stl(code, output, timeout_s=5)
    assert output.is_file()


def test_generated_code_timeout_terminates_worker(tmp_path: Path) -> None:
    output = tmp_path / "timeout.stl"
    with pytest.raises(TimeoutError, match="process tree terminated"):
        script_to_stl("while True:\n    pass\n", output, timeout_s=0.1)
    assert not output.exists()


def test_failed_worker_does_not_publish_partial_output(tmp_path: Path) -> None:
    output = tmp_path / "failed.stl"
    code = """
from pathlib import Path

class FakeShape:
    def val(self):
        return self

    def exportStl(self, path):
        Path(path).write_text('partial', encoding='utf-8')
        raise RuntimeError('intentional export failure')

result = FakeShape()
"""

    with pytest.raises(RuntimeError, match="CadQuery worker failed"):
        script_to_stl(code, output, timeout_s=5)
    assert not output.exists()


if __name__ == "__main__":
    test_mvp()
    test_template_rendering()
    print("All tests passed!")
