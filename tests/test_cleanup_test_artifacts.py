"""Exercise the manual scratch cleanup exclusively against pytest directories."""

import json
import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cleanup_test_artifacts.sh"


def cleanup(scratch, shared):
    env = dict(os.environ, HARDWARE_SPLICER_TMP_ROOT=str(scratch), TMPDIR=str(shared))
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)


def test_only_completed_hs_outputs_in_the_dedicated_root_are_removed(tmp_path):
    shared = tmp_path / "shared"
    scratch = shared / "exploration-project"
    scratch.mkdir(parents=True)
    exploration = scratch / "exploration"
    exploration.mkdir()
    report = {"schema_version": "hardware_splicer.exploration_test.v1"}
    (exploration / "EXPLORATION_REPORT.json").write_text(json.dumps(report))
    unrelated = shared / "exploration-team"
    unrelated.mkdir()
    sibling = scratch / "exploration-notes"
    sibling.mkdir()
    audit = scratch / "functional_audit"
    audit.mkdir()
    (audit / "FUNCTIONAL_DELIVERY_AUDIT.json").write_text(json.dumps(
        {"notes": "hardware_splicer.functional_delivery_audit.v1"}
    ))
    (scratch / "backend_benchmark").symlink_to(unrelated, target_is_directory=True)

    result = cleanup(scratch, shared)

    assert result.returncode == 0, result.stderr
    assert not exploration.exists()
    assert scratch.is_dir() and sibling.is_dir() and unrelated.is_dir() and audit.is_dir()
    assert (scratch / "backend_benchmark").is_symlink()
    assert cleanup(scratch, shared).returncode == 0


def test_shared_temp_roots_are_refused_including_symlink_aliases(tmp_path):
    shared = tmp_path / "shared"
    artifact = shared / "exploration"
    artifact.mkdir(parents=True)
    (artifact / "EXPLORATION_REPORT.json").write_text(json.dumps(
        {"schema_version": "hardware_splicer.exploration_test.v1"}
    ))
    alias = tmp_path / "looks-dedicated"
    alias.symlink_to(shared, target_is_directory=True)

    for scratch in [shared, alias]:
        result = cleanup(scratch, shared)
        assert result.returncode != 0
        assert artifact.is_dir()
