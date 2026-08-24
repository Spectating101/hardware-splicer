"""Citation Engine bridge for Hardware-Splicer's externally evaluated bench authority.

Hardware-Splicer remains authoritative for electrical contracts, DRC, bench gates,
firmware authorization, and physical power-on. This bridge records the already
computed golden-real result as a neutral evidence/decision/receipt graph.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Mapping


def _env_on(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "off", "no", "disabled"}


def _store():
    from citation_engine import JsonlStore, MemoryStore

    configured = str(os.getenv("HARDWARE_SPLICER_CITATION_ENGINE_STORE") or "").strip()
    if not configured:
        return MemoryStore(), "memory"
    path = Path(configured).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return JsonlStore(path), str(path)


def record_golden_real_report(
    report: Mapping[str, Any],
    *,
    namespace: str = "hardware-splicer",
) -> Dict[str, Any]:
    """Record a completed golden-real report without re-evaluating domain logic."""
    if not _env_on("HARDWARE_SPLICER_CITATION_ENGINE", default=True):
        return {"enabled": False, "status": "disabled"}

    strict = _env_on("HARDWARE_SPLICER_CITATION_ENGINE_STRICT", default=False)
    try:
        from citation_engine import (
            Artifact,
            AuthorityState,
            CitationEngine,
            Decision,
            GateResult,
            Provenance,
            Receipt,
            canonical_hash,
            export_bundle,
        )

        store, store_label = _store()
        engine = CitationEngine(store)

        run_identity = {
            "schema_version": report.get("schema_version"),
            "build_id": report.get("build_id"),
            "out_dir": report.get("out_dir"),
            "golden_capture_path": report.get("golden_capture_path"),
        }
        run_key = canonical_hash(run_identity)[:24]
        run_ref = f"{namespace}:golden-real:{run_key}"
        engine.record_artifact(Artifact(
            id=run_ref,
            kind="hardware.golden_real_run",
            payload=run_identity,
            provenance=Provenance(
                source="hardware-splicer",
                method="golden-real-run",
                locator=str(report.get("report_path") or report.get("out_dir") or "") or None,
            ),
        ))

        checks = [
            ("drc_pass", bool(report.get("drc_pass")), "design-rule check passed"),
            ("contract_updates_ok", bool(report.get("contract_updates_ok")), "typed donor contract updates persisted"),
            ("firmware_authorized", bool(report.get("firmware_authorized")), "firmware authority granted by Hardware-Splicer"),
            ("bench_submission_ok", bool(report.get("bench_submission_ok")), "physical bench submission accepted"),
            (
                "power_on_authorized",
                bool((report.get("bench_after") or {}).get("power_on_authorized")),
                "physical measurements authorized power-on",
            ),
            ("not_simulated", not bool(report.get("simulated")), "evidence capture is marked non-simulated"),
        ]

        basis_refs = []
        gate_results = []
        for gate_id, passed, reason in checks:
            evidence_payload = {
                "gate_id": gate_id,
                "passed": passed,
                "reason": reason,
                "build_id": report.get("build_id"),
            }
            if gate_id == "power_on_authorized":
                evidence_payload["bench_after"] = dict(report.get("bench_after") or {})
            elif gate_id == "firmware_authorized":
                evidence_payload["authority"] = dict(report.get("authority") or {})
            elif gate_id == "contract_updates_ok":
                evidence_payload["contract_update_count"] = report.get("contract_update_count")
            elif gate_id == "bench_submission_ok":
                evidence_payload["bench_submission_error"] = report.get("bench_submission_error")

            evidence_key = canonical_hash(evidence_payload)[:24]
            evidence_ref = f"{namespace}:evidence:{gate_id}:{evidence_key}"
            engine.record_artifact(Artifact(
                id=evidence_ref,
                kind="hardware.authorization_evidence",
                payload=evidence_payload,
                provenance=Provenance(
                    source="hardware-splicer",
                    method="golden-real-report",
                    parent_refs=(run_ref,),
                ),
            ))
            basis_refs.append(evidence_ref)
            gate_results.append(GateResult(
                gate_id=gate_id,
                passed=passed,
                basis_refs=(evidence_ref,),
                reason=reason,
            ))

        declared_passed = bool(report.get("passed"))
        computed_passed = all(gate.passed for gate in gate_results)
        if declared_passed != computed_passed:
            raise ValueError("golden-real report.passed conflicts with declared authority checks")

        decision_key = canonical_hash({
            "run_ref": run_ref,
            "gates": gate_results,
            "outcome": "authorized" if declared_passed else "blocked",
        })[:24]
        decision = engine.record_decision(Decision(
            id=f"{namespace}:decision:{decision_key}",
            subject_ref=run_ref,
            outcome="authorized" if declared_passed else "blocked",
            rule_id="hardware-splicer.golden-real.v2",
            gate_results=tuple(gate_results),
            basis_refs=tuple(basis_refs),
        ))

        authority_ref = None
        if decision.authorized:
            transition = engine.transition_authority(
                transition_id=f"{namespace}:authority:{decision_key}",
                subject_ref=run_ref,
                current=AuthorityState.REVIEWABLE,
                target=AuthorityState.AUTHORIZED,
                decision_ref=decision.id,
                actor="hardware-splicer.golden-real",
            )
            authority_ref = transition.id

        receipt_key = canonical_hash({
            "run_ref": run_ref,
            "decision_ref": decision.id,
            "authority_ref": authority_ref,
        })[:24]
        output_refs = (authority_ref,) if authority_ref else (run_ref,)
        receipt = engine.issue_receipt(Receipt(
            id=f"{namespace}:receipt:{receipt_key}",
            workflow="hardware-splicer.golden-real",
            input_refs=tuple([run_ref, *basis_refs]),
            assertion_refs=(),
            decision_refs=(decision.id,),
            output_refs=output_refs,
            metadata={
                "declared_passed": declared_passed,
                "source_schema": report.get("schema_version"),
                "build_id": report.get("build_id"),
            },
        ))
        bundle = export_bundle(store, [receipt.id])
        return {
            "enabled": True,
            "status": "recorded",
            "runRef": run_ref,
            "decisionRef": decision.id,
            "decisionDigest": decision.digest,
            "authorityRef": authority_ref,
            "receiptRef": receipt.id,
            "receiptDigest": receipt.digest,
            "bundleSchema": bundle["schema"],
            "bundleFingerprint": bundle["fingerprint"],
            "bundleObjectCount": len(bundle["objects"]),
            "store": store_label,
        }
    except Exception as exc:
        if strict:
            raise
        return {
            "enabled": True,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
