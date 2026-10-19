"""Check trusted, hash-bound archived ZIPs and run their offline replay tests."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import zipfile

base=Path(__file__).resolve().parent
data=json.loads((base/"VERIFICATION.json").read_text())
for row in data["downloads"]:
    name=row["candidate"]+"-review.zip"
    bundle=(base/name).read_bytes()
    assert len(bundle)==row["bytes"]
    assert hashlib.sha256(bundle).hexdigest()==row["sha256"]
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        assert archive.testzip() is None
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            for member in archive.namelist():
                assert "/" not in member and "\\" not in member and ".." not in member
                (dest/member).write_bytes(archive.read(member))
            contract=json.loads((dest/"contract.json").read_text())
            assert contract["physical_correctness"]=="UNPROVEN"
            assert contract["physical_authority_granted"] is False
            assert contract["fabrication_ready"] is False
            check=subprocess.run([sys.executable,"-I",str(dest/"test_adapter.py")],capture_output=True,text=True,timeout=15)
            assert check.returncode==0,check.stderr
            scenarios=json.loads(check.stdout)["scenarios"]
            assert len(scenarios)==7 and all(s["pass"] for s in scenarios)
            demo=subprocess.run([sys.executable,"-I",str(dest/"adapter.py")],input=(dest/"example-events.jsonl").read_text(),capture_output=True,text=True,timeout=15)
            assert demo.returncode==0,demo.stderr
            actions=[json.loads(x) for x in demo.stdout.splitlines()]
            assert len(actions)==1 and actions[0]["action"]=="activate"
    print(name, "verified", "7/7 synthetic replays", "1 symbolic action")
print("Physical correctness remains unproven.")
