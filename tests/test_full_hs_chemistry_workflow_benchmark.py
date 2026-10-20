from __future__ import annotations

from eval.practical_chemistry.full_hs_workflow_benchmark_v1 import run


def test_full_product_practical_chemistry_retention_and_review():
    report = run()
    assert report["cases"] == report["passed"] == 4, [
        row for row in report["results"] if not row["pass"]
    ]
    for row in report["results"]:
        assert row["preview_did_not_mutate_project"]
        assert row["pending_review_did_not_mutate_project"]
        assert row["accepted_review_created_revision"]
        assert row["baseline_review_packet_findings"] == 0
        assert row["new_chemistry_findings"] >= 2
        assert row["new_release_blockers"] >= 1
        assert row["review_packet_integrity_verified"]
        assert not row["physical_authority_opened"]
        assert row["indexed_source_claims_still_unverified"]
    assert "No measured time savings or repair economic uplift" in report["benefits_not_shown"]
