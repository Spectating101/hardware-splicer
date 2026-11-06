"""Conservative, source-auditable opportunity triage from HS public acquisition.

This is not a demand forecaster. It separates GitHub problem mentions, marketplace
asking prices, ambiguous product identities, and HS engineering authorization.
Every observation stays attributable; absence from a bounded search is not market exit.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
from urllib.parse import urlparse
import json
import math

SCHEMA = "hs.market_opportunity_triage.v1"
RULE_SCHEMA = "hs.market_opportunity_rules.v1"


class OpportunityEvidenceError(ValueError):
    """Untrustworthy input cannot become a product opportunity."""


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _digest(data: Any) -> str:
    return _sha(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def _parse(raw: bytes, label: str) -> dict[str, Any]:
    try:
        val = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise OpportunityEvidenceError(f"{label}: invalid JSON") from exc
    if not isinstance(val, dict):
        raise OpportunityEvidenceError(f"{label}: expected object")
    return val


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise OpportunityEvidenceError("missing timestamp")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OpportunityEvidenceError("invalid timestamp") from exc
    if not t.tzinfo:
        raise OpportunityEvidenceError("timezone required")
    return t.astimezone(timezone.utc)


def _title_match(title: str, needles: list[str]) -> bool:
    return any(w.casefold() in title.casefold() for w in needles)


def _repo(url: str) -> str:
    parsed = urlparse(url)
    path = [x for x in parsed.path.split("/") if x]
    if parsed.scheme != "https" or parsed.hostname != "github.com" or len(path) != 4 or path[2] != "issues" or not path[3].isdigit():
        raise OpportunityEvidenceError("invalid GitHub issue URL")
    return "/".join(path[:2]).casefold()


def _listing_url(url: str) -> bool:
    u = urlparse(url)
    p = u.path.strip("/").split("/")
    return u.scheme == "https" and u.hostname == "www.ruten.com.tw" and len(p) == 2 and p[0] == "item" and p[1].isdigit()


def _validate_rules(plan: Mapping[str, Any], rules: Mapping[str, Any]) -> list[dict[str, Any]]:
    if rules.get("schema") != RULE_SCHEMA or rules.get("target_architecture") != plan.get("target_architecture"):
        raise OpportunityEvidenceError("rules schema or target architecture mismatch")
    lanes = rules.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        raise OpportunityEvidenceError("no opportunity lanes")
    ids = [j.get("id") for j in plan.get("jobs", [])]
    if len(ids) != len(set(ids)) or len(ids) != len(lanes) or set(ids) != {x.get("id") for x in lanes}:
        raise OpportunityEvidenceError("plan and opportunity lanes must match exactly")
    for key in ("global_issue_pain_terms", "global_listing_exclusions"):
        v = rules.get(key)
        if not isinstance(v, list) or not v or not all(isinstance(x, str) and x for x in v):
            raise OpportunityEvidenceError(f"invalid {key}")
    for lane in lanes:
        if not lane.get("candidate_product_id") or not lane.get("hypothesis") or not lane.get("required_validation"):
            raise OpportunityEvidenceError("lane missing product identity or test")
        terms = lane.get("problem_terms")
        if not isinstance(terms, list) or not terms:
            raise OpportunityEvidenceError("lane has no problem topic terms")
        models = lane.get("competitor_models")
        if not isinstance(models, list) or not all(isinstance(m, dict) and m.get("id") and isinstance(m.get("all_terms"), list) and m["all_terms"] for m in models):
            raise OpportunityEvidenceError("invalid model rules")
        model_ids = [m["id"] for m in models]
        if len(model_ids) != len(set(model_ids)):
            raise OpportunityEvidenceError("duplicated model identity")
    return lanes


def _check_source_pack(pack: Mapping[str, Any], handoff: Mapping[str, Any], source_bytes: bytes, plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    if pack.get("schema") != "hs.market_signals.v1" or pack.get("target_architecture") != plan.get("target_architecture"):
        raise OpportunityEvidenceError("source pack schema or target architecture mismatch")
    d = pack.get("discovery")
    if not isinstance(d, dict) or not isinstance(d.get("coverage"), list) or not isinstance(d.get("failures"), list):
        raise OpportunityEvidenceError("missing collection coverage")
    if pack.get("plan_sha256") != _digest(plan):
        raise OpportunityEvidenceError("source plan digest differs from current query plan")
    capture = _timestamp(pack.get("captured_at_utc"))
    live = handoff.get("live_acquisition")
    if not isinstance(live, dict) or live.get("signal_pack_sha256") != _sha(source_bytes):
        raise OpportunityEvidenceError("canonical bridge does not attest these exact source bytes")
    if _timestamp(live.get("captured_at_utc")) != capture:
        raise OpportunityEvidenceError("capture date differs from canonical bridge")
    if handoff.get("target_product") != pack.get("target_architecture"):
        raise OpportunityEvidenceError("target identity mismatch in bridge")
    if handoff.get("not_same_product") is not True or handoff.get("market_snapshot", {}).get("reference_only_not_target_cost") is not True:
        raise OpportunityEvidenceError("reference hardware cannot become target BOM")
    hs = handoff.get("hs_engineering", {})
    if type(hs.get("blocker_count")) is not int or hs["blocker_count"] < 0:
        raise OpportunityEvidenceError("missing canonical engineering blockers")
    if (handoff.get("safe_to_order_inventory") is not False
            or handoff.get("safe_to_claim_market_demand_for_exact_product") is not False
            or handoff.get("verified_exact_customer_orders") != 0):
        raise OpportunityEvidenceError("cannot use commercially authorized or fabricated demand input")
    signals = pack.get("signals")
    if not isinstance(signals, list):
        raise OpportunityEvidenceError("missing collected signals")
    ids: set[str] = set()
    jobs = {x["id"] for x in plan["jobs"]}
    bridge_ids = {x.get("id") for x in handoff.get("market_signals", [])}
    if len(bridge_ids) != len(handoff.get("market_signals", [])):
        raise OpportunityEvidenceError("duplicate observations in canonical bridge")
    for row in signals:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in ids:
            raise OpportunityEvidenceError("duplicate or invalid signal")
        ids.add(row["id"])
        if row["id"] not in bridge_ids:
            raise OpportunityEvidenceError("source record omitted by canonical bridge")
        if row.get("kind") not in {"anecdotal_problem", "marketplace_asking_price"}:
            raise OpportunityEvidenceError("unsupported acquired evidence category")
        if not isinstance(row.get("discovery_job_ids"), list) or not row["discovery_job_ids"] or not set(row["discovery_job_ids"]) <= jobs:
            raise OpportunityEvidenceError("unknown research lane")
        meta = row.get("source_metadata")
        if not isinstance(meta, dict) or not isinstance(meta.get("source_record"), dict) or meta.get("source_record_sha256") != _digest(meta["source_record"]):
            raise OpportunityEvidenceError("source record provenance mismatch")
        if _timestamp(row.get("observed_at_utc")) != capture:
            raise OpportunityEvidenceError("observation time differs from acquisition timestamp")
        if row["kind"] == "anecdotal_problem":
            _repo(row.get("source_url", ""))
        elif not _listing_url(row.get("source_url", "")):
            raise OpportunityEvidenceError("untrusted listing URL")
    if ids != bridge_ids:
        raise OpportunityEvidenceError("handoff market signals mismatch acquired pack")
    return signals


def _deltas(current: Mapping[str, Any], previous: Mapping[str, Any] | None) -> dict[str, Any]:
    if previous is None:
        return {"compared_to_prior": False, "new_observations": [], "changed_source_records": [],
                "not_seen_in_bounded_refresh": [], "interpretation": "No historical baseline supplied"}
    if previous.get("schema") != "hs.market_signals.v1" or previous.get("target_architecture") != current.get("target_architecture"):
        raise OpportunityEvidenceError("prior snapshot belongs to different product or schema")
    if _timestamp(previous.get("captured_at_utc")) >= _timestamp(current.get("captured_at_utc")):
        raise OpportunityEvidenceError("prior source must predate current source")
    prev = {x["id"]: x.get("source_metadata", {}).get("source_record_sha256") for x in previous.get("signals", [])}
    now = {x["id"]: x["source_metadata"]["source_record_sha256"] for x in current["signals"]}
    return {"compared_to_prior": True,
            "prior_capture": previous["captured_at_utc"],
            "new_observations": sorted(set(now) - set(prev)),
            "changed_source_records": sorted(x for x in (set(now) & set(prev)) if now[x] != prev[x]),
            "not_seen_in_bounded_refresh": sorted(set(prev) - set(now)),
            "interpretation": "Nonappearance is not market exit; marketplace counter changes are not verified sales velocity"}


def qualify(*, source_bytes: bytes, handoff: Mapping[str, Any], plan: Mapping[str, Any],
            rules: Mapping[str, Any], previous_bytes: bytes | None = None) -> dict[str, Any]:
    """Create defensible opportunity hypotheses, not commercial authorization."""
    pack = _parse(source_bytes, "signal pack")
    lanes = _validate_rules(plan, rules)
    signals = _check_source_pack(pack, handoff, source_bytes, plan)
    previous = _parse(previous_bytes, "previous pack") if previous_bytes is not None else None
    changes = _deltas(pack, previous)
    by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        for job in signal["discovery_job_ids"]:
            by_lane[job].append(signal)
    opportunities = []
    all_ambiguous = []
    all_unmatched = []
    for lane in lanes:
        reports = []
        mentions = []
        models: dict[str, list[dict[str, Any]]] = {m["id"]: [] for m in lane["competitor_models"]}
        ambiguous = []
        unmatched = []
        for signal in sorted(by_lane.get(lane["id"], []), key=lambda s: s["id"]):
            title = signal.get("summary", "")
            if not isinstance(title, str):
                raise OpportunityEvidenceError("invalid title")
            if signal["kind"] == "anecdotal_problem":
                if not _title_match(title, lane["problem_terms"]):
                    unmatched.append(signal["id"])
                    continue
                record = {"id": signal["id"], "url": signal["source_url"], "source_repo": _repo(signal["source_url"]),
                          "title": title}
                if _title_match(title, rules["global_issue_pain_terms"]):
                    reports.append(record)
                else:
                    mentions.append(record)
            else:
                if _title_match(title, rules["global_listing_exclusions"]):
                    ambiguous.append({"id": signal["id"], "reason": "likely_accessory_or_parts"})
                    continue
                matching = [m["id"] for m in lane["competitor_models"]
                            if all(term.casefold() in title.casefold() for term in m["all_terms"])]
                if len(matching) != 1:
                    ambiguous.append({"id": signal["id"], "reason": "multiple_model_titles" if matching else "model_not_resolved"})
                    continue
                value = signal["source_metadata"].get("asking_price_twd")
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value < 1e10:
                    raise OpportunityEvidenceError("invalid asking price")
                models[matching[0]].append({"id": signal["id"], "url": signal["source_url"],
                                            "listed_twd": value, "title": title})
        by_repos = sorted({_repo(x["url"]) for x in reports})
        matched_models = []
        for model_id, found in models.items():
            if not found:
                continue
            prices = [x["listed_twd"] for x in found]
            matched_models.append({
                "model_title_match": model_id,
                "listings": found, "listing_count": len(found),
                "asking_price_min_twd": min(prices), "asking_price_max_twd": max(prices),
                "sku_or_variant_verified": False, "sellers_independent_verified": False,
                "sold_units_verified": False, "comparable_to_hs_target_cost": False,
            })
        problem_status = ("MULTI_REPOSITORY_ISSUE_REPORTS_UNVERIFIED" if len(by_repos) >= 2
                          else "SINGLE_REPOSITORY_ISSUE_REPORT_UNVERIFIED" if by_repos
                          else "NO_QUALIFIED_PROBLEM_REPORTS")
        market_status = ("BOUNDED_REQUESTS_WITH_FAILURES" if pack["discovery"]["failures"]
                         else "BOUNDED_REQUESTS_NO_REPORTED_FAILURES")
        hsid = lane["candidate_product_id"] == pack["target_architecture"]
        opportunities.append({
            "research_lane_id": lane["id"], "candidate_product_id": lane["candidate_product_id"],
            "candidate_label": lane.get("candidate_label", lane["id"]),
            "unverified_hypothesis": lane["hypothesis"],
            "problem_reports": reports, "topic_mentions_not_problem_proof": mentions,
            "independent_github_repositories_with_problem_reports": len(by_repos),
            "problem_evidence_status": problem_status,
            "competing_model_title_matches": matched_models,
            "ambiguous_listing_ids": ambiguous, "unmatched_signal_ids": sorted(unmatched),
            "market_evidence_status": market_status,
            "hs_product_gates": {
                "release_assessment_applies_to_this_product": hsid,
                "target_release_state": handoff["hs_engineering"]["achieved_state"] if hsid else None,
                "unresolved_engineering_blockers": handoff["hs_engineering"]["blocker_count"] if hsid else None,
                "other_product_release_not_assessed": not hsid,
            },
            "buying_interest_evidence": "NONE_VERIFIED",
            "buyer_interviews": 0, "verified_exact_product_orders": 0,
            "manufacturing_or_inventory_authorized": False,
            "next_information_gain_experiment": lane["required_validation"],
            "triage_decision": "QUALIFIED_BUYER_RESEARCH_REQUIRED" if reports else "PROBLEM_VALIDATION_REQUIRED",
        })
        all_ambiguous += [{"lane": lane["id"], **x} for x in ambiguous]
        all_unmatched += [{"lane": lane["id"], "id": i} for i in unmatched]
    return {
        "schema": SCHEMA, "as_of_utc": pack["captured_at_utc"],
        "target_architecture": pack["target_architecture"],
        "signal_pack_sha256": _sha(source_bytes), "source_plan_sha256": pack["plan_sha256"],
        "rules_sha256": _digest(rules),
        "collection_coverage": pack["discovery"]["coverage"],
        "collection_failures": pack["discovery"]["failures"],
        "raw_observation_count": pack["discovery"].get("raw_candidate_count"),
        "selected_signal_count": len(signals),
        "opportunities": opportunities,
        "review_queue": {"ambiguous_listings": all_ambiguous, "unmatched_signals": all_unmatched},
        "changes_since_previous": changes,
        "verified_exact_product_customers": 0, "safe_to_order_inventory": False,
        "limitations": [
            "Only configured source queries and product lanes are covered, not autonomous discovery of all needs.",
            "Title phrases are weak problem evidence; repositories are not independent customers.",
            "Competitor identity is a title match only, not a confirmed exact SKU, inventory or price quote.",
            "Cross-source presence does not establish purchase demand, sales velocity or product-market fit.",
            "The cited HS release assessment applies only to the exact HS target architecture.",
        ],
    }
