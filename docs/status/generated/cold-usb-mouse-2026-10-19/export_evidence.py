"""Export a sanitized, hash-mapped cold-trial proof bundle, not source HTML."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
CHECKOUT = Path("$REPOSITORY_ROOT")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decoded(row):
    blocks = (row.get("response") or {}).get("content", [])
    text = "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text")
    try:
        return json.loads(text)
    except ValueError:
        return {}


def metrics(rows):
    errors = []
    discovery = []
    mutations = []
    for r in rows:
        payload = decoded(r)
        status = r.get("http_status")
        failed = (r.get("response") or {}).get("is_error", False) or r.get("ok") is False or isinstance(status, int) and status >= 400
        if failed:
            errors.append({"seq": r["seq"], "tool": r["tool"], "operation_id": r["arguments"].get("operation_id"), "status": status, "error": payload})
        if r["tool"] != "hs_backend_call":
            discovery.append(r["seq"])
        if r["tool"] == "hs_backend_call" and "json_body" in r["arguments"] and not failed:
            mutations.append(r["seq"])
    first = mutations[0] if mutations else None
    return {
        "tool_calls": len(rows), "response_bytes": sum(r.get("response_bytes", 0) for r in rows),
        "elapsed_tool_seconds": round(sum(r["elapsed_seconds"] for r in rows), 3),
        "wall_seconds_first_to_last_call": round(rows[-1]["started_at_unix"] + rows[-1]["elapsed_seconds"] - rows[0]["started_at_unix"], 3) if rows else None,
        "error_calls": len(errors), "successful_calls": len(rows) - len(errors), "errors": errors,
        "discovery_calls": len(discovery), "first_successful_mutating_call_seq": first,
        "discovery_calls_before_first_successful_mutation": len([seq for seq in discovery if first is not None and seq < first]),
        "successful_body_carrying_calls": mutations,
        "model_input_tokens": None, "model_output_tokens": None,
        "token_metrics_note": "Orchestrator did not expose per-child model token usage; response bytes are NOT token estimates.",
        "metric_note": "Body-carrying calls include non-persistent software checks; persistence is independently checked against exported canonical records. MCP is_error is read from raw SDK result, not the bridge's fallback ok field.",
    }


def main():
    target = Path(sys.argv[1]).resolve()
    if not target.is_relative_to(CHECKOUT / ".cache" / "hardware-splicer"):
        raise SystemExit("Export target must be under task-owned cache worktree")
    if target.exists():
        raise SystemExit("Refusing to overwrite an existing proof bundle")
    target.mkdir(parents=True)
    names = ["preregistration.json", "PHASE1_PROMPT.md", "PHASE2_PROMPT.md", "SOURCES.md", "QUICKSTART.md", "trace.jsonl", "host-prepared-mission.json", "PHASE1_REPORT.md", "PHASE2_REPORT.md", "HOST_INTERVENTIONS.md", "checkpoint.json", "checkpoint.py", "host.py", "bridge.py", "export_evidence.py"]
    sources = [ROOT / name for name in names if (ROOT / name).is_file()]
    sources += sorted(path for path in (ROOT / "store").rglob("*") if path.is_file())
    artifacts = []
    for source in sources:
        raw = source.read_bytes()
        sanitized = raw.replace(str(ROOT).encode(), b"$TRIAL_ROOT").replace(str(CHECKOUT).encode(), b"$REPOSITORY_ROOT")
        relative = source.relative_to(ROOT)
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(sanitized)
        artifacts.append({"path": str(relative), "original_sha256": sha(raw), "published_sha256": sha(sanitized), "original_bytes": len(raw), "published_bytes": len(sanitized), "sanitized": raw != sanitized})
    rows = [json.loads(line) for line in (ROOT / "trace.jsonl").read_text().splitlines()]
    summary = metrics(rows)
    checkpoint = json.loads((ROOT / "checkpoint.json").read_text())
    boundary = checkpoint["tool_call_count"]
    summary["phase_1"] = metrics(rows[:boundary])
    summary["phase_2"] = metrics(rows[boundary:])
    (target / "METRICS.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (target / "PROOF_BUNDLE.json").write_text(json.dumps({"run_id": "cold-usb-mouse-2026-10-19-a0530015", "artifacts": artifacts, "raw_manufacturer_html_published": False, "note": "HTML bytes retained privately with frozen hashes; source paraphrases published. Paths sanitized, each artifact binds original and published bytes. Raw payload-internal artifact hashes refer to original producer bytes, not sanitized export bytes."}, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"files": len(artifacts), "calls": len(rows), "bytes": summary["response_bytes"], "errors": summary["error_calls"]}))


if __name__ == "__main__":
    main()
