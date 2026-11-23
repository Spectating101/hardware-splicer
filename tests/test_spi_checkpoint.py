"""Fail-closed checkpoint-unit tests; native KiCad execution is a separate pilot."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hardware_splicer import spi_checkpoint as cp


def write(path: Path, payload: bytes = b"fixed native bytes") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


class SpiCheckpointUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "job"
        self.out.mkdir()
        self.data = self.out / "source_copy"
        self.data.mkdir()
        self.source_file = "verify_design.py"
        self.origin = write(self.data / self.source_file)
        self.point = {
            "schema": cp.SCHEMA,
            "source_files": {self.source_file: self.origin},
            "completed": ["source"],
            "artifacts_sha256": {
                "source": {"source_copy/" + self.source_file: self.origin}
            },
            "physical_authority": False,
        }

    def test_source_receipt_valid_prefix(self):
        cp._validate_completed(self.out, self.point)

    def test_digest_changed_fails_closed(self):
        write(self.data / self.source_file, b"substituted verifier")
        with self.assertRaisesRegex(cp.CheckpointError, "artifact hash mismatch"):
            cp._validate_completed(self.out, self.point)

    def test_missing_stage_source_fails(self):
        (self.data / self.source_file).unlink()
        with self.assertRaises(cp.CheckpointError):
            cp._validate_completed(self.out, self.point)

    def test_extra_stage_not_in_prefix_fails(self):
        self.point["completed"] = ["source", "drc"]
        with self.assertRaisesRegex(cp.CheckpointError, "non-prefix"):
            cp._validate_completed(self.out, self.point)

    def test_duplicate_completed_stage_fails(self):
        self.point["completed"] = ["source", "source"]
        with self.assertRaisesRegex(cp.CheckpointError, "non-prefix"):
            cp._validate_completed(self.out, self.point)

    def test_unexpected_stage_receipt_fails(self):
        self.point["artifacts_sha256"]["erc"] = {}
        with self.assertRaisesRegex(cp.CheckpointError, "stage/receipt"):
            cp._validate_completed(self.out, self.point)

    def test_erc_report_tampering_fails(self):
        native = self.out / "native_reports"
        first = write(native / "netlist.xml", b"<export/>")
        self.point["completed"].append("netlist")
        self.point["artifacts_sha256"]["netlist"] = {"native_reports/netlist.xml": first}
        a = write(native / "erc.json", b'{"violations":[]}')
        b = write(native / "erc.stdout.txt", b"0 total")
        self.point["completed"].append("erc")
        self.point["artifacts_sha256"]["erc"] = {
            "native_reports/erc.json": a,
            "native_reports/erc.stdout.txt": b,
        }
        cp._validate_completed(self.out, self.point)
        write(native / "erc.stdout.txt", b"forged green")
        with self.assertRaisesRegex(cp.CheckpointError, "artifact hash mismatch"):
            cp._validate_completed(self.out, self.point)

    def test_artifact_symlink_to_elsewhere_rejected(self):
        external = self.root / "outside.txt"
        external.write_text("EXTERNAL")
        (self.data / self.source_file).unlink()
        (self.data / self.source_file).symlink_to(external)
        with self.assertRaises(cp.CheckpointError):
            cp._validate_completed(self.out, self.point)

    def test_symlink_target_refused_before_native_launch(self):
        external = self.root / "target.json"
        write(external)
        report = self.out / "native_reports"
        report.mkdir()
        (report / "erc.json").symlink_to(external)
        with self.assertRaisesRegex(cp.CheckpointError, "linked or escaped"):
            cp._safe_target(self.out, "native_reports/erc.json")
        self.assertEqual(external.read_bytes(), b"fixed native bytes")

    def test_path_escape_rejected(self):
        for name in ("../../outside", "/tmp/external", ""):
            with self.subTest(name=name), self.assertRaises(cp.CheckpointError):
                cp._safe_target(self.out, name)

    def test_source_inventory_matches_unmodified_source(self):
        original = self.root / "source"
        original.mkdir()
        write(original / self.source_file)
        cp._validate_source(self.out, original, {self.source_file: self.origin})
        write(original / self.source_file, b"upstream changed")
        with self.assertRaisesRegex(cp.CheckpointError, "source bytes changed"):
            cp._validate_source(self.out, original, {self.source_file: self.origin})

    def test_checkpoint_is_atomic_and_private(self):
        p = self.out / "checkpoint.json"
        cp._atomic_json(p, {"a": 1})
        cp._atomic_json(p, {"a": 2})
        self.assertEqual(json.loads(p.read_text()), {"a": 2})
        self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_concurrent_lock_refused(self):
        with cp._exclusive(self.out):
            with self.assertRaises(BlockingIOError):
                with cp._exclusive(self.out):
                    pass

    def test_missing_kicad_fails_preflight(self):
        with patch.object(cp.shutil, "which", return_value=None):
            with self.assertRaisesRegex(cp.CheckpointError, "unavailable"):
                cp._toolchain()

    @unittest.skipUnless(__import__("importlib").util.find_spec("pcbnew") is not None,
                         "native pcbnew is not available on a generic CI runner")
    def test_report_hash_input_cannot_be_partial(self):
        # Used in the real native verifier: all five digests must match.
        checker = Path(__file__).resolve().parents[1] / (
            "hardware/reference_designs/spi_flash_adapter_v1/verify_design.py"
        )
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_hs_kicad_ref", checker)
        with patch.dict(os.environ, {"PYTHONDONTWRITEBYTECODE": "1"}):
            import sys
            sys.path.insert(0, str(checker.parent))
            try:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                sys.path.pop(0)
        reports = self.out / "reports"
        reports.mkdir()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            module.main(report_dir=reports, reused_native_report_hashes={"netlist.xml": "0"*64})

    def test_no_model_provider_required_for_native_spi(self):
        self.assertEqual(cp.STAGES, ("source", "netlist", "erc", "drc", "verification"))


if __name__ == "__main__":
    unittest.main()
