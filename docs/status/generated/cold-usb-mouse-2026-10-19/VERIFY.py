"""Read-only proof checks: python VERIFY.py [bundle-directory].

This checks recorded state and byte identities, not electrical correctness,
independent source adjudication, raw-document comprehension or LLM reliability.
"""
import hashlib
import json
from pathlib import Path
import sys


def main():
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
    manifest = json.loads((root / "PROOF_BUNDLE.json").read_text())
    for item in manifest["artifacts"]:
        path = (root / item["path"]).resolve()
        assert path.is_relative_to(root), "artifact path escapes bundle"
        data = path.read_bytes()
        assert len(data) == item["published_bytes"], item["path"]
        assert hashlib.sha256(data).hexdigest() == item["published_sha256"], item["path"]
    rows = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
    metrics = json.loads((root / "METRICS.json").read_text())
    checkpoint = json.loads((root / "checkpoint.json").read_text())
    assert len(rows) == metrics["tool_calls"] == 48
    assert checkpoint["tool_call_count"] == metrics["phase_1"]["tool_calls"] == 32
    assert metrics["phase_2"]["tool_calls"] == 16
    errors = sum((r.get("http_status") or 0) >= 400 or r["response"].get("is_error", False) for r in rows)
    assert errors == metrics["error_calls"] == 3
    assert sum(r["response_bytes"] for r in rows) == metrics["response_bytes"] == 606268
    project = root / "store/cold-usb-mouse-document-study"
    mission = project / "missions/mission-8851a9f8860a4337"
    events = [json.loads(p.read_text()) for p in sorted((mission / "events").glob("*.json"))]
    assert [e["seq"] for e in events] == list(range(1, 9))
    candidates = [e["candidate"]["id"] for e in events if e["type"] == "candidate_proposed"]
    assert sorted(candidates) == ["intact_pedal", "remote_contact"]
    assert events[-1]["type"] == "evidence_required"
    assert not any(e["type"] == "terminal_proposed" for e in events)
    for path, expected in checkpoint["file_hashes"].items():
        if "/events/" in path:
            assert hashlib.sha256((root / path).read_bytes()).hexdigest() == expected
    evaluations = [e for e in events if e["type"] == "evaluation_recorded"]
    assert len(evaluations) == 1
    evaluation = evaluations[0]
    artifact = mission / evaluation["artifact"]
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == evaluation["result"]["result_sha256"]
    assert json.loads(artifact.read_text()) == {"refused": "modules must be a list of 1 to 8"}
    revision = json.loads((project / "revisions/00000004.json").read_text())
    assert revision["revision"] == 4
    plan = revision["snapshot"]["preFabricationPlan"]
    for field in ("fabrication_ready", "power_on_ready", "physical_authority_granted"):
        assert plan[field] is False
    assert plan["physical_correctness"] == "UNPROVEN"
    assert plan["assessment"]["blockers"]
    assert plan["assessment"]["behavioral_contract"]
    assert plan["assessment"]["pedal_parameterization"]
    assert plan["assessment"]["handoff"]
    sources = revision["snapshot"]["engineeringSources"]
    assert len(sources) == 1
    source_hash = "b98f9a76a04dc4a97addf69fb25d3e54255c03d5a6b01052ef2f5c2c8d4057c5"
    source = project / "sources/sha256/b9" / source_hash
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    print(json.dumps({"proof_integrity": "pass", "hash_mapped_files": len(manifest["artifacts"]),
                      "calls": len(rows), "backend_rejections": errors, "revision": 4,
                      "original_event_prefix_preserved": True,
                      "product_end_to_end_pass": False, "physical_correctness": "UNPROVEN"}, indent=2))


if __name__ == "__main__":
    main()
