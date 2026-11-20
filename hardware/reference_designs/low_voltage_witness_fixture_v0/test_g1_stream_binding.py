"""Cross-stream G1 structural binding tests; all data fabricated and nonphysical."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

import g1_commissioning_gate as combined


class CrossStreamBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hs-stream-bind-only-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.first = datetime(2026, 11, 20, tzinfo=timezone.utc)
        self.primary = self.root / "primary.csv"
        self.reference = self.root / "reference.csv"
        self.packet_path = self.root / "packet.json"
        self.reference_session = self.root / "reference-session.json"
        self.write_streams()
        self.write_metadata()

    def at(self, i, offset_ms=0):
        return (self.first + timedelta(seconds=i, milliseconds=offset_ms)).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z")

    def write_streams(self, count=183, offset_ms=136):
        with self.primary.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(("timestamp_utc", "voltage_v", "current_a"))
            for i in range(count):
                writer.writerow((self.at(i), "4.96", "0.414"))
        with self.reference.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(("timestamp_utc", "voltage_v", "shunt_voltage_v"))
            for i in range(count):
                writer.writerow((self.at(i, offset_ms), "4.96", ".00414"))

    def write_metadata(self, *, claimed_offset=200, claimed_serial="REF_SN_A",
                       sha_override=None, start=None, end=None):
        ref_sha = combined.sha256(self.reference)
        manifest = {
            "schema": "hardware_splicer.witness_g1_bench_packet.v1",
            "capture_kind": "DECLARED_BENCH_CAPTURE",
            "reference_meter_serial": claimed_serial,
            "measured_max_clock_offset_ms": claimed_offset,
            "start_utc": start or self.at(0),
            "end_utc": end or self.at(183),
            "files": [
                {"role": "primary_native_capture", "path": self.primary.name,
                 "sha256": combined.sha256(self.primary)},
                {"role": "reference_native_export", "path": self.reference.name,
                 "sha256": sha_override or ref_sha},
            ],
        }
        self.packet_path.write_text(json.dumps(manifest))
        receipt = {
            "files": {"reference-preview.csv": {"sha256": ref_sha}},
            "identifiers": {
                "shunt_idn": "EXAMPLE,DCV,REF_SN_A,1.0",
                "bus_idn": "EXAMPLE,DCV,REF_SN_B,1.0",
            },
        }
        self.reference_session.write_text(json.dumps(receipt))

    def link(self):
        return combined.crosscheck_primary_reference(self.packet_path,
                                                     self.reference_session)

    def test_aligned_hash_bound_183_samples_pass_only_structural(self):
        result = self.link()
        self.assertEqual(result["status"],
                         "PAIRED_HOST_TIMESTAMPS_ONLY_UNVERIFIED_APERTURE",
                         result["problems"])
        self.assertEqual(result["paired_samples"], 183)
        self.assertAlmostEqual(result["max_observed_host_timestamp_delta_ms"],
                               136, places=6)
        self.assertTrue(result["reference_bytes_bound_to_g1_manifest"])
        self.assertFalse(result["physical_measurement_independence_verified"])
        self.assertFalse(result["absolute_clock_alignment_verified"])
        self.assertFalse(result["physical_ready"])

    def test_reference_hash_from_unrelated_capture_is_rejected(self):
        self.write_metadata(sha_override="0"*64)
        result = self.link()
        self.assertEqual(result["status"], "CROSS_STREAM_BINDING_HOLD")
        self.assertTrue(any("SHA differs" in p for p in result["problems"]))

    def test_claimed_reference_serial_must_match_scpi_identity(self):
        self.write_metadata(claimed_serial="UNRELATED_METER")
        result = self.link()
        self.assertTrue(any("serial not present" in p for p in result["problems"]))

    def test_reference_samples_shifted_more_than_screening_budget(self):
        self.write_streams(offset_ms=500)
        self.write_metadata()
        result = self.link()
        self.assertTrue(any("cannot be paired" in p for p in result["problems"]))

    def test_asserted_clock_budget_stricter_than_observed(self):
        self.write_metadata(claimed_offset=100)
        result = self.link()
        self.assertTrue(any("cannot be paired" in p for p in result["problems"]))

    def test_clock_budget_over_policy_is_rejected(self):
        self.write_metadata(claimed_offset=300)
        result = self.link()
        self.assertTrue(any("exceeds 200 ms" in p for p in result["problems"]))

    def test_sample_count_mismatch_is_rejected(self):
        self.write_streams(count=182)
        self.write_metadata()
        result = self.link()
        self.assertTrue(any("pair count" in p for p in result["problems"]))

    def test_insufficient_duration_with_183_duplicates_is_rejected(self):
        with self.primary.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(("timestamp_utc", "voltage_v", "current_a"))
            for i in range(183):
                w.writerow((self.at(i//2), "4.96", "0.414"))
        self.write_metadata()
        result = self.link()
        self.assertEqual(result["status"], "CROSS_STREAM_BINDING_HOLD")
        self.assertTrue(any("Non-monotonic" in p or "unreadable" in p for p in result["problems"]))

    def test_packet_window_must_cover_both_original_exports(self):
        self.write_metadata(start=self.at(5))
        result = self.link()
        self.assertTrue(any("outside" in p for p in result["problems"]))

    def test_missing_reference_file_fails_closed(self):
        self.reference.unlink()
        result = self.link()
        self.assertEqual(result["status"], "CROSS_STREAM_BINDING_HOLD")
        self.assertTrue(result["problems"])


if __name__ == "__main__":
    unittest.main()
