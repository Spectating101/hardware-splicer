"""Offline, fast integrity and verdict tests for the held-out HS benchmark."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import freeze
import run


LOCK = Path(__file__).with_name("cases.lock.json")


class FrozenCohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads(LOCK.read_text())

    def test_is_eight_with_four_strata(self):
        cases = self.lock["cases"]
        self.assertEqual(len(cases), 8)
        strata = [row["stratum"] for row in cases]
        self.assertEqual(sorted(set(strata)), [
            "2layer-clean", "2layer-inherited-drc",
            "4layer-clean", "4layer-inherited-drc",
        ])
        for item in set(strata):
            self.assertEqual(strata.count(item), 2)

    def test_independent_original_projects(self):
        cases = self.lock["cases"]
        self.assertEqual(len(set(x["metadata"]["repo"] for x in cases)), 8)
        self.assertEqual(self.lock["corpus_commit"], freeze.CORPUS_REV)
        self.assertEqual(self.lock["seed"], freeze.SEED)

    def test_immutable_hashes_and_original_pcb(self):
        for case in self.lock["cases"]:
            files = case["files_sha256"]
            for required in ("board.kicad_pcb", "board.kicad_pro", "SOURCE.json"):
                self.assertRegex(files[required], r"^[a-f0-9]{64}$")

    def test_no_opportunistic_clean_only_selection(self):
        self.assertEqual(
            sum(x["metadata"]["ref_drv"] == 0 for x in self.lock["cases"]), 4
        )
        self.assertEqual(
            sum(x["metadata"]["ref_drv"] > 0 for x in self.lock["cases"]), 4
        )

    def test_preflight_rejects_hash_substitution(self):
        with mock.patch.object(freeze, "blob", return_value=b"altered source"):
            with self.assertRaisesRegex(ValueError, "CORPUS_SOURCE_HASH_MISMATCH"):
                run.checked_bytes(Path("/unused"), self.lock, self.lock["cases"][0],
                                  "board.kicad_pcb")

    def test_preflight_rejects_unlocked_filename(self):
        with self.assertRaisesRegex(ValueError, "unlocked or unsafe"):
            run.checked_bytes(Path("/unused"), self.lock, self.lock["cases"][0],
                              "../../secrets")

    def test_selection_is_stable_under_input_order(self):
        # Synthetic manifest: reverse the order; stable ordering must not change.
        manifest = [x["metadata"] for x in self.lock["cases"]]
        self.assertEqual(
            [x["id"] for x in freeze.choose(manifest)],
            [x["id"] for x in freeze.choose(list(reversed(manifest)))],
        )

    def test_semantic_digests_ignore_key_order(self):
        self.assertEqual(run.canonical({"z": 3, "a": {"c": 1, "b": 2}}),
                         run.canonical({"a": {"b": 2, "c": 1}, "z": 3}))

    def test_no_checker_does_not_count_as_pass(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(run.run_kiskill(Path(d), None)["status"],
                             "NOT_CONFIGURED")


class NativeDrcTests(unittest.TestCase):
    def fake_cli(self, work: Path, data, exit_code: int) -> Path:
        script = work / "fake-kicad"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import json,sys\n"
            "from pathlib import Path\n"
            "Path(sys.argv[sys.argv.index('--output')+1]).write_text(" +
            repr(json.dumps(data)) + ")\n"
            "sys.exit(" + str(exit_code) + ")\n"
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        (work / "board.kicad_pcb").write_text("placeholder")
        return script

    def test_error_level_outcomes_do_not_require_zero_exit(self):
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            cli = self.fake_cli(work, {
                "violations": [{"type": "shorting_items"}],
                "unconnected_items": [], "schematic_parity": []
            }, 5)
            result = run.drc(work, native_cli=str(cli))
            self.assertEqual(result["status"], "PROCESSED")
            self.assertEqual(result["error_count"], 1)
            self.assertEqual(result["finding_types"], {"shorting_items": 1})

    def test_missing_report_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            cli = work / "fake-kicad"
            cli.write_text("#!/bin/sh\nexit 0\n")
            cli.chmod(0o700)
            (work / "board.kicad_pcb").write_text("placeholder")
            self.assertEqual(run.drc(work, native_cli=str(cli))["status"],
                             "TOOL_FAILURE")

    def test_fabrication_never_authorized(self):
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            cli = self.fake_cli(work, {
                "violations": [], "unconnected_items": [], "schematic_parity": []
            }, 0)
            result = run.drc(work, native_cli=str(cli))
            self.assertEqual(result["status"], "PROCESSED")
            self.assertEqual(result["error_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
