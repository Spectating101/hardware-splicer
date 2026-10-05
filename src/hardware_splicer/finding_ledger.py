"""Write-time ledger of deterministic findings on a project snapshot.

Only deterministic producers may record entries. Provenance is captured at write
time and is never guessed later. A finding is an observed report: it never
upgrades authority, and ``authority_ceiling`` stays ``observed``.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .engineering_review_identity import AUTHORITY_CEILING
from .finding_provenance import finding_id

ENGINEERING_FINDINGS_KEY = "engineeringFindings"
DETERMINISTIC_PRODUCERS = frozenset({"design_quality_gate", "release_assessment"})
FINDING_CATEGORIES = frozenset({"failed_check", "object_blocker", "release_blocker"})
MAX_FINDING_TEXT = 1000
LEDGER_ENTRY_KEYS = frozenset(
    {
        "finding_id",
        "category",
        "object_id",
        "text",
        "producer",
        "producer_run",
        "provenance",
        "recorded_at",
    }
)
PROVENANCE_KEYS = frozenset({"kind", "basis", "source_ref", "authority_ceiling"})
_AUTHORITY_ISH_KEYS = frozenset(
    {
        "achieved_state",
        "authority",
        "authority_state",
        "authorized_operations",
        "fabrication_authorized",
        "fabrication_ready",
        "firmware_flash_authorized",
        "flash_authorized",
        "motion_authorized",
        "operational_authorized",
        "physical_authority_granted",
        "power_on_authorized",
        "power_on_ready",
        "release_authorized",
        "requested_state",
    }
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bound_finding_text(text: Any) -> tuple[str, bool]:
    """Bound blocker text to ``MAX_FINDING_TEXT`` without silent clipping.

    Over-long text is cut to ``MAX_FINDING_TEXT - 1`` characters plus ``…``.
    """

    raw = "" if text is None else str(text)
    if len(raw) <= MAX_FINDING_TEXT:
        return raw, False
    return raw[: MAX_FINDING_TEXT - 1] + "…", True


def _is_authority_ish(key: str) -> bool:
    token = str(key)
    if token == "authority_ceiling":
        return False
    if token in _AUTHORITY_ISH_KEYS:
        return True
    lowered = token.lower()
    return "authoriz" in lowered or lowered.endswith("_authority")


def _assert_no_authority_ish(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            token = str(key)
            if token == "authority_ceiling":
                if _text(item) != AUTHORITY_CEILING:
                    raise ValueError(
                        "finding authority_ceiling must remain "
                        f"{AUTHORITY_CEILING!r}; authority is never upgraded"
                    )
                continue
            if _is_authority_ish(token):
                raise ValueError(
                    f"authority-ish key {token!r} is not allowed on a finding entry"
                )
            _assert_no_authority_ish(item)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _assert_no_authority_ish(item)


def validate_recorded_at(value: Any) -> str:
    """Accept only ISO timestamps that are explicitly UTC (``Z`` or ``+00:00``)."""

    token = _text(value)
    if not token:
        raise ValueError("recorded_at must be a non-empty ISO UTC timestamp")
    if token.endswith("Z"):
        parseable = token[:-1] + "+00:00"
    elif token.endswith("+00:00"):
        parseable = token
    else:
        raise ValueError("recorded_at must be UTC ending in Z or +00:00")
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError as exc:
        raise ValueError("recorded_at must be a valid ISO UTC timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("recorded_at must include a UTC timezone")
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError("recorded_at must be UTC ending in Z or +00:00")
    return token


def validate_ledger_entry(entry: Any) -> dict[str, Any]:
    """Validate one persisted ledger row. Raises ``ValueError`` on any defect."""

    if not isinstance(entry, Mapping):
        raise ValueError("finding entry must be a mapping")
    extra = sorted(str(key) for key in entry if str(key) not in LEDGER_ENTRY_KEYS)
    if extra:
        raise ValueError(f"unknown extra keys: {extra}")
    category = _text(entry.get("category"))
    if category not in FINDING_CATEGORIES:
        raise ValueError(
            "finding category must be failed_check, object_blocker, or release_blocker"
        )
    text = entry.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("finding text must be non-empty")
    if len(text) > MAX_FINDING_TEXT:
        raise ValueError(f"finding text must be at most {MAX_FINDING_TEXT} characters")
    object_id = entry.get("object_id")
    if object_id is not None and not isinstance(object_id, str):
        raise ValueError("object_id must be a string or null")
    object_id = _text(object_id) or None
    producer = _text(entry.get("producer"))
    if producer not in DETERMINISTIC_PRODUCERS:
        raise ValueError("producer is not in the deterministic allowlist")
    producer_run = _text(entry.get("producer_run"))
    if not producer_run:
        raise ValueError("producer_run must be non-empty")
    provenance = entry.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("finding provenance must be a mapping")
    provenance_extra = sorted(
        str(key) for key in provenance if str(key) not in PROVENANCE_KEYS
    )
    if provenance_extra:
        raise ValueError(f"unknown extra provenance keys: {provenance_extra}")
    if _text(provenance.get("kind")) != "deterministic":
        raise ValueError("finding provenance kind must be exactly 'deterministic'")
    basis = _text(provenance.get("basis"))
    if not basis:
        raise ValueError("finding provenance basis must be non-empty")
    source_ref = provenance.get("source_ref")
    if source_ref is not None and not isinstance(source_ref, str):
        raise ValueError("source_ref must be a string or null")
    source_ref = _text(source_ref) or None
    if _text(provenance.get("authority_ceiling")) != AUTHORITY_CEILING:
        raise ValueError(
            "finding authority_ceiling must remain "
            f"{AUTHORITY_CEILING!r}; authority is never upgraded"
        )
    recorded_at = validate_recorded_at(entry.get("recorded_at"))
    expected_id = finding_id(category, object_id, text, source_ref)
    if _text(entry.get("finding_id")) != expected_id:
        raise ValueError("finding_id does not match the recomputed id")
    return {
        "finding_id": expected_id,
        "category": category,
        "object_id": object_id,
        "text": text,
        "producer": producer,
        "producer_run": producer_run,
        "provenance": {
            "kind": "deterministic",
            "basis": basis,
            "source_ref": source_ref,
            "authority_ceiling": AUTHORITY_CEILING,
        },
        "recorded_at": recorded_at,
    }


def _normalize_entry(
    raw: Mapping[str, Any],
    *,
    producer: str,
    producer_run: str,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("each finding entry must be a mapping")
    _assert_no_authority_ish(raw)
    body: dict[str, Any] = dict(raw)
    provenance_raw = body.get("provenance")
    if isinstance(provenance_raw, Mapping):
        body["provenance"] = dict(provenance_raw)
    category = _text(body.get("category"))
    text = _text(body.get("text"))
    object_id = _text(body.get("object_id")) or None
    source_ref = None
    if isinstance(body.get("provenance"), Mapping):
        source_ref = _text(body["provenance"].get("source_ref")) or None
    if isinstance(body.get("text"), str):
        body["text"] = text
    if "object_id" in body:
        body["object_id"] = object_id
    body["finding_id"] = finding_id(category, object_id, text, source_ref)
    body["producer"] = producer
    body["producer_run"] = producer_run
    if not body.get("recorded_at"):
        body["recorded_at"] = _utc_now()
    return validate_ledger_entry(body)


def replace_producer_findings(
    snapshot: Mapping[str, Any],
    producer: str,
    producer_run: str,
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Replace one producer's latest-run findings on a deep-copied snapshot.

    Producer and ``producer_run`` are validated before the snapshot is
    touched, including when ``findings`` is empty. Only allowlisted
    deterministic producers may write or clear ledger rows.

    Entries from other producers are kept only when the existing ledger is a
    well-formed list. A non-list value (``None``, string, dict, …) is a
    malformed ledger: this run replaces it entirely (self-healing). The
    malformed value remains on the earlier immutable revision. This producer's
    previous list entries are replaced by ``findings`` (including an empty
    list, which clears a fixed design).
    """

    producer_name = _text(producer)
    if producer_name not in DETERMINISTIC_PRODUCERS:
        raise ValueError("producer is not in the deterministic allowlist")
    if not isinstance(producer_run, str) or not producer_run.strip():
        raise ValueError("producer_run must be non-empty")
    run_label = producer_run.strip()
    if not isinstance(snapshot, Mapping):
        raise TypeError("snapshot must be a mapping")
    if not isinstance(findings, Sequence) or isinstance(findings, (str, bytes, bytearray)):
        raise TypeError("findings must be a sequence of mappings")

    body = deepcopy(dict(snapshot))
    existing = body.get(ENGINEERING_FINDINGS_KEY)
    kept: list[Any] = []
    # Well-formed list: keep other producers. Any other existing value is a
    # malformed ledger and is replaced by this run (self-healing).
    if isinstance(existing, list):
        for row in existing:
            if isinstance(row, Mapping) and _text(row.get("producer")) == producer_name:
                continue
            kept.append(deepcopy(row))

    replacement = [
        _normalize_entry(row, producer=producer_name, producer_run=run_label)
        for row in findings
    ]
    body[ENGINEERING_FINDINGS_KEY] = kept + replacement
    return body
