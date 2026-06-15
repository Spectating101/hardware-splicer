from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hardware_splicer.catalog import CATALOG_BUILD_IDS


ROOT = Path(__file__).resolve().parents[1]
COMPILE_SCRIPT = ROOT / "scripts" / "compile_build_graph.cjs"


def test_python_catalog_is_sorted_unique() -> None:
    assert CATALOG_BUILD_IDS == sorted(CATALOG_BUILD_IDS)
    assert len(CATALOG_BUILD_IDS) == len(set(CATALOG_BUILD_IDS))


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_catalog_matches_typescript_supported_build_ids() -> None:
    proc = subprocess.run(
        ["node", str(COMPILE_SCRIPT), "--list-build-ids"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    ts_ids = set(json.loads(proc.stdout))
    python_ids = set(CATALOG_BUILD_IDS)
    assert python_ids == ts_ids, {
        "only_python": sorted(python_ids - ts_ids),
        "only_ts": sorted(ts_ids - python_ids),
    }
