"""Read-only proof checks plus isolated replay of the delivered software."""
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

root = Path(__file__).resolve().parent
result = json.loads((root / "RESULT.json").read_text())
data = (root / "intact-input-review.zip").read_bytes()
assert hashlib.sha256(data).hexdigest() == result["package_sha256"]
assert len(data) == result["package_bytes"]
assert result["kind"] == "scripted_real_mcp_control_not_live_agent"
assert result["project_revision_unchanged_by_checks"] is True
trace = result["trace"]
assert len(trace) == result["mcp_calls"] == 9
assert all(row["response"].get("ok") is not False for row in trace)
recorded = next(row["response"]["body"]["run"] for row in trace if "run" in row["response"].get("body", {}))
evaluation = next(row["response"]["body"]["evaluation"] for row in trace if "evaluation" in row["response"].get("body", {}))
assert evaluation["artifact"] == result["recorded_artifact"]
original_run = json.dumps(recorded, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
assert hashlib.sha256(original_run.encode()).hexdigest() == evaluation["result"]["result_sha256"]
download = next(row["response"] for row in trace if "body_base64" in row["response"])
assert base64.b64decode(download["body_base64"], validate=True) == data
assert recorded["package_sha256"] == result["package_sha256"]
assert recorded["contract"]["sources"][0]["content_hash"] == "sha256:" + result["source_packet_sha256"]
assert recorded["contract"]["physical_correctness"] == "UNPROVEN"
assert recorded["contract"]["physical_authority_granted"] is False
assert recorded["contract"]["fabrication_ready"] is False
expected = {row["name"] for row in recorded["files"]}
assert expected == {"README.md", "adapter.py", "contract.json", "example-events.jsonl", "offline-checks.json", "test_adapter.py"}
with tempfile.TemporaryDirectory(prefix="hs-intact-proof-") as temp:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert set(archive.namelist()) == expected and archive.testzip() is None
        for row in recorded["files"]:
            assert hashlib.sha256(archive.read(row["name"])).hexdigest() == row["sha256"]
        archive.extractall(temp)
    replay = subprocess.run([sys.executable, "-I", str(Path(temp) / "test_adapter.py")], capture_output=True, text=True, timeout=10, check=True)
    checks = json.loads(replay.stdout)
    assert checks == recorded["offline_checks"]
    assert len(checks["scenarios"]) == 7 and all(row["pass"] for row in checks["scenarios"])
print(json.dumps({"artifact_integrity": "pass", "delivered_replay": "7/7",
                  "mcp_calls": len(trace), "live_agent_trial": False,
                  "physical_correctness": "UNPROVEN"}, indent=2))
