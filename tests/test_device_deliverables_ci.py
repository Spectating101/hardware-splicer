"""Keep the CLI that renders 3D fixtures installed in the mock browser lane."""
from pathlib import Path

def test_mock_browser_ci_installs_kicad_cli_as_well_as_lookup_libraries():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/device-plan-deliverables.yml"
    # Inspect the specific setup block without adding a YAML runtime dependency.
    setup = path.read_text().split("- name: Install KiCad", 1)[1].split("- uses:", 1)[0]
    assert "if: matrix.backend == 'mock'" in setup
    assert "kicad kicad-symbols kicad-footprints" in setup
    assert "kicad-cli --version" in setup
    assert "kicad-cli pcb export glb --help" in setup


def test_ci_runs_the_fail_closed_verifier_and_transcript_regressions():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/device-plan-deliverables.yml"
    text = path.read_text()
    assert "tests/test_device_application_verifier.py" in text
    assert "tests/test_device_observations.py" in text
    # The application, its part descriptors and the benchmark that scores its tests run in this workflow too.
    for name in ("test_device_application.py", "test_device_application_vendor.py", "test_device_parts.py",
                 "test_device_bh1750.py", "test_device_vendor_profiles.py", "test_device_case.py", "test_device_engineering.py", "test_device_fault_matrix_benchmark.py"):
        assert f"tests/{name}" in text


def test_ci_runs_the_bh1750_vendor_host_lane_through_the_same_verifier():
    text = (Path(__file__).resolve().parents[1] / ".github/workflows/device-plan-deliverables.yml").read_text()
    assert "scripts/verify_device_application.py --part bh1750 --platformio" in text
