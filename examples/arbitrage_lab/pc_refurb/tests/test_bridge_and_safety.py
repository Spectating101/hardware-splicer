from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


br = _load("hs_pc_bridge", "bridge_salvage_engine.py")
cf = _load("hs_pc_casefile2", "casefile.py")
COLLECT = (ROOT / "bench_collect.py").read_text()


def test_bridge_refuses_control_host_and_unacquired_units():
    rep = cf.evaluate(ROOT / "control_host_optiplex/unit.json")
    with pytest.raises(br.BridgeRefused):
        br.ingest_partout(rep, Path("/nonexistent/inv.json"))
    with pytest.raises(br.BridgeRefused):
        br.ingest_partout({**rep, "role": "target", "acquired": False}, Path("/nonexistent/inv.json"))


def test_bridge_ingests_only_gate_passed_components_into_the_real_engine(tmp_path):
    rep = {"role": "target", "acquired": True, "decision": "REJECT_OR_REPAIR", "unit_id": "u9",
           "facts": {"bench_manifest_sha256": "ab" * 32},
           "partout_candidates": [{"asset_type": "ram_module", "name": "8 GB DDR4 2666", "evidence_gate": "memory_test"}]}
    out = br.ingest_partout(rep, tmp_path / "inv.json")
    assert len(out["ingested_assets"]) == 1
    inv = out["inventory"]
    assert inv["by_capability"] == {"ram_module": 1} and inv["by_test_status"] == {"bench_verified": 1}
    stored = json.loads((tmp_path / "inv.json").read_text())
    assert "ab" * 32 in json.dumps(stored)  # provenance bound to the bench manifest


# --- collector safety contract: it must be incapable of writing to a disk
BANNED = [r"\bmkfs", r"\bdd\b", r"--security-erase", r"blkdiscard", r"nvme\W+format",
                                    r"wipefs\W+(?:-a|--all)", r"\bshred\b", r"sgdisk", r"fdisk", r"parted",
                                    r"--hdd", r"--io\b", r"--sync-file", r"--seek", r"hdparm", r"\brm\s+-"]

def scan(source: str) -> list[str]:
    """Banned disk-write primitives found in real code (docstrings and comments excluded)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body \
                and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant) \
                and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:] or [ast.Pass()]
    code = ast.unparse(tree)
    return [pat for pat in BANNED if re.search(pat, code)]


def test_collector_source_has_no_disk_write_primitives():
    assert scan(COLLECT) == []


def test_the_scan_itself_can_fail():
    assert scan(COLLECT + "\nrun(['mkfs.ext4', '/dev/sda'])\n")
    assert scan(COLLECT + "\nrun(['stress-ng', '--hdd', '2'])\n")
    assert scan(COLLECT + "\nrun(['nvme', 'format', '/dev/nvme0n1'])\n")
    assert scan(COLLECT + "\nrun(['wipefs', '-a', '/dev/sda'])\n")
    assert open_modes(COLLECT + "\nopen('/dev/sda', 'wb')\n") != open_modes(COLLECT)


def open_modes(source: str) -> list[str]:
    """Mode argument of every builtin open() call ('?' when not a literal)."""
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open":
            m = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "mode"), None)
            out.append(m.value if isinstance(m, ast.Constant) else "?")
    return out


def test_every_open_is_read_only_and_wipefs_is_dry_run():
    assert open_modes(COLLECT) == ["rb"]  # exactly one: the sampled block read in verify_wipe
    assert '"--no-act"' in COLLECT


def test_redaction_removes_serials_macs_and_ips_from_text_and_json():
    bc = _load("hs_pc_collect_red", "bench_collect.py")
    t = bc.redact_text("Serial Number: ABC123XYZ\naddr 192.168.1.20 mac aa:bb:cc:dd:ee:ff\nUUID: 1234-5678\n")
    assert "ABC123XYZ" not in t and "192.168.1.20" not in t and "aa:bb:cc:dd:ee:ff" not in t and "1234-5678" not in t
    j = bc.redact_json({"serial_number": "S1", "wwn": {"id": 5}, "x": [{"address": "aa:bb:cc:dd:ee:ff", "local": "10.0.0.2"}]})
    s = json.dumps(j)
    assert "S1" not in s and "aa:bb:cc" not in s and "10.0.0.2" not in s


def test_committed_control_bundle_contains_no_identifiers():
    blob = "".join(p.read_text(errors="replace") for p in (ROOT / "control_host_optiplex/bundle").iterdir() if p.is_file())
    assert not re.search(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", blob, re.I)
    assert not re.search(r"\b(?:192\.168|10\.\d+|172\.(?:1[6-9]|2\d|3[01]))\.\d+\.\d+\b", blob)
    assert not re.search(r'"serial_number": "(?!redacted:)', blob)
    assert "/home/" not in blob and "/Users/" not in blob, "absolute local paths leaked into the bundle"
