"""Frontend source must not be hidden by a repository ignore rule.

The revision-artifacts proxy route lives in a directory called ``artifacts``,
which the generated-output rule ``artifacts/`` ignored. It existed on the
author's machine and in none of their commits, so a fresh clone had no route
to the saved copies and the comparison viewer, the evidence viewport and the
review packet all failed there.
"""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = "apps/circuit-ai/circuit-ai-frontend"
SOURCE_DIRS = ("app", "components", "lib", "e2e", "public", "scripts")
PROXY = f"{FRONTEND}/app/api/proxy/engineering/projects/p/revisions/1"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)


@pytest.fixture(scope="module", autouse=True)
def _inside_a_work_tree():
    if _git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        pytest.skip("not a git work tree")


@pytest.mark.parametrize("path", [f"{PROXY}/artifacts/route.ts", f"{PROXY}/artifacts/schematic/file/route.ts"])
def test_the_artifact_proxy_routes_are_not_ignored(path):
    # --no-index asks the rules alone, so this holds before the file exists too.
    result = _git("check-ignore", "--no-index", "-v", path)
    assert result.returncode == 1, f"{path} is ignored by {result.stdout.strip()}"


def test_no_present_frontend_source_file_is_ignored():
    existing = [f"{FRONTEND}/{name}" for name in SOURCE_DIRS if (ROOT / FRONTEND / name).is_dir()]
    result = _git("ls-files", "--others", "--ignored", "--exclude-standard", "--", *existing)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", "ignored frontend source files:\n" + result.stdout
