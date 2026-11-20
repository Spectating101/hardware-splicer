"""The cross-project boundary uses actual saved engine artifacts and remains read-only."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from hardware_splicer import digital_project as digital
from hardware_splicer.digital_engine import DigitalStudyEngine
from hardware_splicer.policy_layer import (
    EVIDENCE_SCHEMA, REVIEW_SCHEMA, VERIFICATION_SCHEMA, PolicyLayerError, canonical_json_bytes,
    export_policy_evidence, read_json_bytes, validate_policy_evidence, validate_policy_feedback,
)
from hardware_splicer.policy_layer_cli import run as cli_run, write_new
from hardware_splicer.project_store import CorruptProject, RevisionConflict


class PolicyLayerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.engine = DigitalStudyEngine(project_root=self.root / "projects", job_db=self.root / "jobs.db")
        self.project = self.engine.create()["project"]["project_id"]
        self.evidence = export_policy_evidence(self.engine, self.project)
        self.evidence_bytes = canonical_json_bytes(self.evidence)

    def tearDown(self):
        self.engine.close()
        self.directory.cleanup()

    def binding(self):
        return {"evidence_sha256": hashlib.sha256(self.evidence_bytes).hexdigest(),
                "project_id": self.project, "revision": 1, "run_id": self.evidence["run_id"]}

    def review(self, overrides=None):
        return {"schema": REVIEW_SCHEMA, "decision": "ADMIT_WITH_LIMIT", "unmet_constraints": [],
                "target_results": [{"id": "mass", "passed": True}],
                "source_binding": self.binding(),
                "revision_requirements": {"payload_mass_g": 10} if overrides is None else overrides,
                "physical_authority_granted": False}

    def receipt(self, review, review_bytes=None):
        review_bytes = canonical_json_bytes(review) if review_bytes is None else review_bytes
        return canonical_json_bytes({"schema": VERIFICATION_SCHEMA, "verified": True, "source_binding": review["source_binding"],
                                     "decision": review["decision"], "physical_authority_granted": False,
                                     "review_sha256": hashlib.sha256(review_bytes).hexdigest()})

    def feedback(self, review, **kwargs):
        kwargs.setdefault("replay_receipt_bytes", self.receipt(review))
        return validate_policy_feedback(self.engine, self.evidence_bytes, canonical_json_bytes(review), **kwargs)

    def test_export_preserves_real_study_units_and_full_artifact_inventory(self):
        before = self.engine.projects.load(self.project)
        self.assertEqual(self.evidence["schema"], EVIDENCE_SCHEMA)
        self.assertEqual(self.evidence["study"], self.engine.study(self.project))
        self.assertFalse(self.evidence["physical_authority_granted"])
        self.assertEqual(self.evidence["integrity_audit"]["native_verification"], {"requested": False, "performed": False})
        facts = {row["id"]: row for row in self.evidence["facts"]}
        self.assertAlmostEqual(facts["metric.mass_g"]["value"], 234.9)
        self.assertEqual(facts["metric.mass_g"]["unit"], "g")
        self.assertEqual(facts["requirement.gust_scale"]["unit"], "1")
        self.assertEqual(facts["metric.peak_current_a_est"]["basis"], "modeled")
        self.assertEqual(self.evidence["package"]["sha256"], self.evidence["study"]["artifact_manifest"]["STUDY.zip"]["sha256"])
        self.assertEqual(self.engine.projects.load(self.project), before)
        self.assertEqual(self.engine.backend.store.list_digital_jobs(self.project), [])

    def test_feedback_validates_real_resolver_without_applying_or_queuing(self):
        before = self.engine.projects.load(self.project)
        proposal = self.feedback(self.review())
        self.assertEqual(proposal["status"], "validated_proposal")
        self.assertEqual(proposal["resolved_requirements"]["payload_mass_g"], 10)
        self.assertEqual(proposal["requirement_changes"]["payload_mass_g"], {"before": 0, "after": 10})
        self.assertIn("not replayed here", proposal["policy_review_verification"])
        self.assertEqual(proposal["policy_decision"], "ADMIT_WITH_LIMIT")
        self.assertEqual(proposal["candidate_overrides"], {})
        self.assertFalse(proposal["automatic_execution"])
        self.assertFalse(proposal["physical_authority_granted"])
        self.assertEqual(self.engine.projects.load(self.project), before)
        self.assertEqual(self.engine.backend.store.list_digital_jobs(self.project), [])

    def test_corrupted_artifact_cannot_be_exported(self):
        _, directory, _ = digital.load_run(self.engine.projects, self.project)
        with (directory / "nominal.csv").open("ab") as handle:
            handle.write(b"corruption")
        with self.assertRaises((CorruptProject, PolicyLayerError)):
            export_policy_evidence(self.engine, self.project)

    def test_resealed_zip_with_new_member_still_fails_inventory_audit(self):
        _, directory, seal = digital.load_run(self.engine.projects, self.project)
        with zipfile.ZipFile(directory / "STUDY.zip", "a") as archive:
            archive.writestr("unverified-extra.txt", "not a verified artifact")
        seal["artifact_sha256"]["STUDY.zip"] = digital.digest(directory / "STUDY.zip")
        digital.write_json(directory / "sealed-run.json", seal)
        with self.assertRaisesRegex(PolicyLayerError, "integrity audit"):
            export_policy_evidence(self.engine, self.project)

    def test_feedback_binds_exact_bytes_not_just_equal_json(self):
        different_bytes = json.dumps(self.evidence, indent=2).encode()
        self.assertEqual(json.loads(different_bytes), self.evidence)
        with self.assertRaisesRegex(PolicyLayerError, "exact evidence bytes"):
            validate_policy_feedback(self.engine, different_bytes, canonical_json_bytes(self.review()),
                                     replay_receipt_bytes=self.receipt(self.review()))  # binds the review bytes

    def test_feedback_rejects_project_revision_run_and_hash_substitution(self):
        for field, value in (("project_id", "another-project"), ("revision", 2),
                             ("run_id", "f" * 32), ("evidence_sha256", "f" * 64), ("revision", True)):
            with self.subTest(field=field, value=value):
                review = self.review()
                review["source_binding"][field] = value
                with self.assertRaisesRegex(PolicyLayerError, "exact evidence bytes"):
                    self.feedback(review)

    def test_feedback_requires_current_saved_revision(self):
        current = self.engine.projects.load(self.project)
        self.engine.projects.save(self.project, current["snapshot"], expected_revision=1)
        with self.assertRaisesRegex(RevisionConflict, "project changed"):
            self.feedback(self.review())

    def test_feedback_rejects_resealed_changes_to_the_original_study(self):
        changed = deepcopy(self.evidence)
        # A source URI is still bound even if it is not part of numeric policy checks.
        changed["study"]["summary"]["source_sha256"]["invented.py"] = "f" * 64
        changed_bytes = canonical_json_bytes(changed)
        review = self.review()
        review["source_binding"]["evidence_sha256"] = hashlib.sha256(changed_bytes).hexdigest()
        with self.assertRaisesRegex(PolicyLayerError, "verified stored study"):
            validate_policy_feedback(self.engine, changed_bytes, canonical_json_bytes(review),
                                     replay_receipt_bytes=self.receipt(review))

    def test_nonfinite_boolean_unknown_and_out_of_bounds_overrides_are_rejected(self):
        for overrides in ({"payload_mass_g": True}, {"payload_mass_g": 51}, {"unknown": 1}):
            with self.subTest(overrides=overrides), self.assertRaises(PolicyLayerError):
                self.feedback(self.review(overrides))
        for token in ("NaN", "Infinity", "-Infinity", "1e400"):
            raw = json.dumps(self.review()).replace('"payload_mass_g": 10', '"payload_mass_g": ' + token).encode()
            with self.subTest(token=token), self.assertRaisesRegex(PolicyLayerError, "finite"):
                validate_policy_feedback(self.engine, self.evidence_bytes, raw,
                                         replay_receipt_bytes=self.receipt(self.review(), raw))

    def test_physical_promotion_is_rejected_at_any_depth(self):
        for location in ("root", "nested"):
            review = self.review()
            if location == "root":
                review["physical_authority_granted"] = True
            else:
                review["new_result"] = {"fabrication_authorized": True}
            with self.subTest(location=location), self.assertRaisesRegex(PolicyLayerError, "cannot assert"):
                self.feedback(review)
        changed = deepcopy(self.evidence)
        changed["study"]["summary"]["physical_work_requested"] = True
        with self.assertRaisesRegex(PolicyLayerError, "cannot assert"):
            validate_policy_evidence(changed)

    def test_fact_units_values_and_boolean_numeric_aliases_are_rejected(self):
        for field, value in (("unit", "kg"), ("value", 123456), ("value", True)):
            changed = deepcopy(self.evidence)
            row = next(row for row in changed["facts"] if row["id"] == "requirement.gust_scale")
            row[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(PolicyLayerError, "Numeric facts"):
                validate_policy_evidence(changed)

    def test_duplicate_keys_and_extra_schema_fields_are_rejected(self):
        with self.assertRaisesRegex(PolicyLayerError, "Duplicate JSON key"):
            read_json_bytes(b'{"schema":"one","schema":"two"}')
        changed = deepcopy(self.evidence)
        changed["automatic_execution"] = True
        with self.assertRaisesRegex(PolicyLayerError, "Unexpected policy evidence fields"):
            validate_policy_evidence(changed)

    def test_failed_engineering_verdict_remains_exportable_as_failed(self):
        # A unit-level engine facade models the existing invariant that intact
        # engineering failures remain saved/exportable, independently of native CAD.
        study = deepcopy(self.evidence["study"])
        study["summary"]["requirements_met"] = False
        study["summary"]["constraints"][0]["passed"] = False
        audit = deepcopy(self.evidence["integrity_audit"])
        audit["requirements_met"] = False
        with patch.object(self.engine, "study", return_value=study), patch.object(self.engine, "audit", return_value=audit):
            result = export_policy_evidence(self.engine, self.project)
        self.assertFalse(result["study"]["summary"]["requirements_met"])
        self.assertFalse(result["study"]["summary"]["constraints"][0]["passed"])
        self.assertTrue(result["integrity_audit"]["ok"])

    def test_cli_writes_exact_bytes_and_refuses_overwrite(self):
        evidence_file = self.root / "evidence.json"
        args = ["--project-root", str(self.engine.projects.root), "--jobs-db", str(self.root / "jobs.db"),
                "export", self.project, str(evidence_file)]
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            code = cli_run(args)
        self.assertEqual(code, 0)
        receipt = json.loads(output.getvalue())
        original = evidence_file.read_bytes()
        self.assertEqual(receipt["artifact"]["sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(original, canonical_json_bytes(read_json_bytes(original)))
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(cli_run(args), 1)
        self.assertEqual(evidence_file.read_bytes(), original)
        with self.assertRaises(FileExistsError):
            write_new(evidence_file, {"replacement": True})

    # Decision, replay and candidate enforcement.
    def blocked(self, **extra):
        review = self.review({"payload_mass_g": 10})
        review.update(decision="BLOCKED", target_results=[{"id": "mass", "passed": False}],
                      unmet_constraints=[{"id": "mass", "reason": "TARGET_NOT_MET"}], **extra)
        return review

    def candidate(self, **fields):
        return {"id": "lighter-payload", "kind": "modelled_candidate_design_change", "status": "PROPOSED",
                "requirement_overrides": {"payload_mass_g": 5}, **fields}

    def test_unknown_or_missing_decision_is_refused(self):
        for decision in ("PASS", "ALLOW", "", None):
            review = self.review()
            review["decision"] = decision
            with self.subTest(decision=decision), self.assertRaisesRegex(PolicyLayerError, "Unsupported policy review decision"):
                self.feedback(review)

    def test_admit_with_unmet_rows_or_failed_target_contradicts_itself(self):
        review = self.review()
        review["unmet_constraints"] = [{"id": "mass", "reason": "TARGET_NOT_MET"}]
        with self.assertRaisesRegex(PolicyLayerError, "contradicts"):
            self.feedback(review)
        review = self.review()
        review["target_results"] = [{"id": "mass", "passed": False}]
        with self.assertRaisesRegex(PolicyLayerError, "contradicts"):
            self.feedback(review)

    def test_admit_contradicted_by_a_failed_study_check_is_refused(self):
        failed = deepcopy(self.evidence["study"])
        failed["summary"]["constraints"][0]["passed"] = False
        with patch("hardware_splicer.policy_layer.validate_policy_evidence", return_value={**self.evidence, "study": failed}):
            with self.assertRaisesRegex(PolicyLayerError, "contradicts"):
                self.feedback(self.review())

    def test_blocked_without_unmet_rows_or_omitting_a_failed_target_is_refused(self):
        review = self.blocked()
        review["unmet_constraints"] = []
        with self.assertRaisesRegex(PolicyLayerError, "states no unmet rows"):
            self.feedback(review)
        review = self.blocked()
        review["target_results"].append({"id": "speed", "passed": False})
        with self.assertRaisesRegex(PolicyLayerError, "omits a failed target"):
            self.feedback(review)

    def test_missing_or_mismatched_replay_is_refused(self):
        review = self.review()
        with self.assertRaisesRegex(PolicyLayerError, "replay not verified"):
            self.feedback(review, replay_receipt_bytes=None)
        for field, value in (("verified", False), ("decision", "BLOCKED"), ("schema", "other"),
                             ("source_binding", {**review["source_binding"], "revision": 2})):
            receipt = json.loads(self.receipt(review))
            receipt[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(PolicyLayerError, "replay not verified"):
                self.feedback(review, replay_receipt_bytes=canonical_json_bytes(receipt))

    def test_configured_verifier_is_run_and_its_failure_refuses(self):
        script = self.root / "fake-run.mjs"
        script.write_text("process.stderr.write('Hardware policy review does not reproduce.'); process.exit(1);\n")
        with self.assertRaisesRegex(PolicyLayerError, "replay not verified: Hardware policy review does not reproduce"):
            self.feedback(self.review(), replay_receipt_bytes=None, policy_lab_run=script)
        review = self.review()
        script.write_text("process.stdout.write(" + json.dumps(self.receipt(review).decode()) + ");\n")
        proposal = self.feedback(review, replay_receipt_bytes=None, policy_lab_run=script)
        self.assertEqual(proposal["policy_review_verification"], "replayed by Policy Lab verify here")

    def test_admitting_review_never_carries_an_unstated_change(self):
        review = self.review({})
        review["candidate_design_changes"] = [self.candidate()]
        proposal = self.feedback(review)
        self.assertEqual(proposal["requirement_changes"], {})
        self.assertEqual(proposal["applied_candidates"], [])
        with self.assertRaisesRegex(PolicyLayerError, "admits the design"):
            self.feedback(review, candidates=("lighter-payload",))

    def test_selected_candidate_of_a_blocked_review_becomes_a_stated_change(self):
        review = self.blocked(candidate_design_changes=[self.candidate(requirement_overrides={"gust_scale": 0.5})])
        proposal = self.feedback(review, candidates=("lighter-payload",))
        self.assertEqual(proposal["candidate_overrides"], {"gust_scale": 0.5})
        self.assertEqual(set(proposal["requirement_changes"]), {"payload_mass_g", "gust_scale"})
        self.assertEqual(proposal["policy_decision"], "BLOCKED")
        unselected = self.feedback(review)
        self.assertEqual(set(unselected["requirement_changes"]), {"payload_mass_g"})

    def test_unknown_unproposed_or_clashing_candidates_are_refused(self):
        for row, match in ((self.candidate(status="NOT_NEEDED"), "not a proposed"),
                           (self.candidate(kind="fix"), "not a proposed"),
                           (self.candidate(), "already stated")):
            review = self.blocked(candidate_design_changes=[row])
            with self.subTest(row=row), self.assertRaisesRegex(PolicyLayerError, match):
                self.feedback(review, candidates=("lighter-payload",))
        with self.assertRaisesRegex(PolicyLayerError, "not a proposed"):
            self.feedback(self.blocked(candidate_design_changes=[]), candidates=("missing",))


    def test_receipt_must_bind_the_exact_review_bytes(self):
        review = self.review()
        legacy = json.loads(self.receipt(review))
        del legacy["review_sha256"]
        with self.assertRaisesRegex(PolicyLayerError, "receipt does not bind the review"):
            self.feedback(review, replay_receipt_bytes=canonical_json_bytes(legacy))
        # A forged review with the same decision and binding but invented requirements.
        honest_receipt = self.receipt(review)
        forged = self.review({"payload_mass_g": 40})
        forged["candidate_design_changes"] = [self.candidate()]
        with self.assertRaisesRegex(PolicyLayerError, "receipt does not bind the review"):
            self.feedback(forged, replay_receipt_bytes=honest_receipt)

    def test_admit_for_a_study_that_failed_its_requirements_is_refused(self):
        failed = deepcopy(self.evidence["study"])
        failed["summary"]["requirements_met"] = False
        with patch("hardware_splicer.policy_layer.validate_policy_evidence", return_value={**self.evidence, "study": failed}):
            with self.assertRaisesRegex(PolicyLayerError, "contradicts"):
                self.feedback(self.review())


if __name__ == "__main__":
    unittest.main()
