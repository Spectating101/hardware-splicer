import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
rows = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / "store").rglob("*") if p.is_file()}
result = {"phase": 1, "tool_call_count": len(rows), "file_hashes": files,
          "note": "Frozen after phase-1 completion and before fresh-session continuation; no solution/report is supplied to phase 2."}
(root / "checkpoint.json").write_text(json.dumps(result, indent=2, sort_keys=True))
print(json.dumps({"calls": len(rows), "files": len(files)}))
