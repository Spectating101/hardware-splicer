"""A review packet: what a reviewer was shown for one revision, in one hash-bound document.

The packet reports. It is built only from what the project already holds (the revision, its findings and how each was
established, the files the revision retained and their hashes, proposals and who decided them, and the discussion), and it
changes nothing. It never opens fabrication, power-on or release, and it says in plain words what it does not establish.

It is deterministic: the same project state gives the same bytes, so two people holding the same packet can tell they hold
the same thing. No clock reading and no credential goes into it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from .artifact_retention import ARTIFACT_KINDS, ArtifactIntegrityError, load_artifact_pin
from .finding_provenance import project_findings_payload
from .project_candidates import list_candidates, review_state
from .project_review_store import ProjectReviewStore
from .project_store import ProjectStore, validate_project_id
from .project_thread_store import ProjectThreadStore

PACKET_SCHEMA = "hardware_splicer.review_packet.v1"
MAX_FINDINGS = 1000
MAX_THREADS = 100
MAX_EVENTS_PER_THREAD = 50
MAX_PROPOSALS = 100
MAX_TEXT = 500

NOT_ESTABLISHED: tuple[str, ...] = (
    "That the design has been fabricated, assembled, powered or physically measured.",
    "That physical correctness or production readiness is established.",
    "That an independent engineer, manufacturer or reviewer has validated the design. A comment or a decision recorded here "
    "is a record of who said what, not an endorsement.",
    "That a passing automated check, ERC or DRC result, simulation, model confidence or file integrity grants physical authority.",
    "That this packet, or accepting a proposal, approves fabrication, power-on or release.",
)

AUTHORITY_STATEMENT = (
    "This packet does not open, record or imply fabrication, power-on or release authority. Those stay closed until a "
    "person opens them through the project's own gates."
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _clip(value: Any, limit: int = MAX_TEXT) -> str:
    text = str(value if value is not None else "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _counts(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        name = str(row.get(key) or "unknown")
        out[name] = out.get(name, 0) + 1
    return dict(sorted(out.items()))


def _artifacts(store: ProjectStore, project_id: str, revision: int) -> dict[str, Any]:
    try:
        pin = load_artifact_pin(store, project_id, revision)
    except ArtifactIntegrityError:
        return {"status": "unreadable", "files": {kind: None for kind in ARTIFACT_KINDS}}
    if pin is None:
        return {"status": "not_retained", "files": {kind: None for kind in ARTIFACT_KINDS}}
    files: dict[str, Any] = {}
    for kind in ARTIFACT_KINDS:
        entry = pin.get("artifacts", {}).get(kind) if isinstance(pin.get("artifacts"), Mapping) else None
        files[kind] = (
            {"relative": entry.get("relative"), "sha256": entry.get("sha256"), "size_bytes": entry.get("size_bytes")}
            if isinstance(entry, Mapping)
            else None
        )
    return {"status": "retained", "retention_basis": pin.get("retention_basis"), "files": files}


def _findings(snapshot: Mapping[str, Any], revision: int) -> dict[str, Any]:
    rows = project_findings_payload(snapshot, revision)["findings"]
    listed = []
    for row in rows[:MAX_FINDINGS]:
        provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
        listed.append(
            {
                "finding_id": row.get("finding_id"),
                "category": row.get("category"),
                "object_id": row.get("object_id"),
                "text": _clip(row.get("text")),
                "provenance": {
                    "kind": provenance.get("kind"),
                    "basis": _clip(provenance.get("basis")),
                    "source_ref": provenance.get("source_ref"),
                    "authority_ceiling": provenance.get("authority_ceiling"),
                    "attested": bool(provenance.get("attested")),
                },
            }
        )
    flat = [{"category": row.get("category"), "kind": (row.get("provenance") or {}).get("kind"), "attested": bool((row.get("provenance") or {}).get("attested"))} for row in rows]
    return {
        "total": len(rows),
        "truncated": len(rows) > MAX_FINDINGS,
        "by_category": _counts(flat, "category"),
        "by_provenance": _counts(flat, "kind"),
        "attested": sum(1 for row in flat if row["attested"]),
        "items": listed,
    }


def _discussion(threads: ProjectThreadStore, project_id: str, revision: int) -> dict[str, Any]:
    rows = threads.list_threads(project_id)
    out = []
    for row in rows[:MAX_THREADS]:
        full = threads.get_thread(project_id, str(row.get("thread_id")))
        events = []
        for event in (full.get("events") or [])[:MAX_EVENTS_PER_THREAD]:
            author = event.get("author") if isinstance(event.get("author"), Mapping) else {}
            events.append(
                {
                    "seq": event.get("seq"),
                    "type": event.get("type"),
                    "created_at": event.get("created_at"),
                    "author": {"kind": author.get("kind"), "id": author.get("id")},
                    # Whether the server confirmed who this was, as against a name someone typed.
                    "author_verified": bool(event.get("author_verified")),
                    "body": _clip(event.get("body")) if event.get("body") else None,
                }
            )
        anchor = full.get("anchor") if isinstance(full.get("anchor"), Mapping) else {}
        out.append(
            {
                "thread_id": full.get("thread_id"),
                "status": full.get("status"),
                "anchor": {
                    "revision": anchor.get("revision"),
                    "object_id": anchor.get("object_id"),
                    "artifact": anchor.get("artifact"),
                    "position": anchor.get("position"),
                },
                "about_this_revision": anchor.get("revision") == revision,
                "comment_count": full.get("comment_count"),
                "events": events,
                "events_truncated": len(full.get("events") or []) > MAX_EVENTS_PER_THREAD,
            }
        )
    return {
        "total": len(rows),
        "truncated": len(rows) > MAX_THREADS,
        "open": sum(1 for row in rows if row.get("status") == "open"),
        "resolved": sum(1 for row in rows if row.get("status") == "resolved"),
        "threads": out,
    }


def _proposals(store: ProjectStore, reviews: ProjectReviewStore, project_id: str, revision: int) -> dict[str, Any]:
    mine = [row for row in list_candidates(store, project_id) if row.get("base_revision") == revision]
    out = []
    for row in mine[:MAX_PROPOSALS]:
        state = review_state(store, reviews, project_id, row)
        checks = row.get("checks") if isinstance(row.get("checks"), Mapping) else {}
        diff = row.get("diff") if isinstance(row.get("diff"), Mapping) else {}
        out.append(
            {
                "candidate_id": row.get("candidate_id"),
                "kind": row.get("kind"),
                "created_by": row.get("created_by"),
                "created_by_verified": bool(row.get("verified")),
                "note": _clip(row.get("note")) or None,
                "changes": diff.get("summary"),
                "operations": [
                    {"op": item.get("op"), "target": (item.get("target") or {}).get("ref") or (item.get("target") or {}).get("uuid"), "detail": _clip(item.get("detail"), 200)}
                    for item in (row.get("applied") or [])[:20]
                    if isinstance(item, Mapping)
                ],
                "checks": {
                    "ran": bool(checks.get("ran")),
                    "engine": checks.get("engine"),
                    "new_violations": checks.get("new_violations"),
                    "reason": checks.get("reason"),
                },
                "decision": {
                    "status": state.get("status"),
                    "decided_by": state.get("decided_by"),
                    "note": state.get("note"),
                    "accepted_revision": state.get("accepted_revision"),
                    "out_of_date": bool(state.get("stale")),
                },
            }
        )
    return {
        "total": len(mine),
        "truncated": len(mine) > MAX_PROPOSALS,
        "pending": sum(1 for item in out if item["decision"]["status"] == "pending" and not item["decision"]["out_of_date"]),
        "accepted": sum(1 for item in out if item["decision"]["status"] == "accepted"),
        "rejected": sum(1 for item in out if item["decision"]["status"] == "rejected"),
        "items": out,
    }


def build_review_packet(
    store: ProjectStore,
    project_id: str,
    *,
    revision: int | None = None,
    reviews: ProjectReviewStore | None = None,
    threads: ProjectThreadStore | None = None,
) -> dict[str, Any]:
    """The packet for one revision (the latest when none is given). Reads only; never repairs a damaged store."""

    safe_id = validate_project_id(project_id)
    # The plain loader: a packet must not rename a damaged revision or rewrite a manifest just to be read.
    envelope = store.load(safe_id, revision=revision) if revision is not None else store.load(safe_id)
    resolved = int(envelope["revision"])
    snapshot = envelope.get("snapshot") if isinstance(envelope.get("snapshot"), Mapping) else {}
    reviews = reviews or ProjectReviewStore(store)
    threads = threads or ProjectThreadStore(store)

    packet: dict[str, Any] = {
        "schema_version": PACKET_SCHEMA,
        "project": {
            "project_id": safe_id,
            "name": _clip(snapshot.get("projectName") or snapshot.get("name") or safe_id, 200),
            "revision": resolved,
            "saved_at": envelope.get("saved_at"),
            "snapshot_sha256": _sha256(_canonical(snapshot)),
        },
        "retained_files": _artifacts(store, safe_id, resolved),
        "findings": _findings(snapshot, resolved),
        "proposals": _proposals(store, reviews, safe_id, resolved),
        "discussion": _discussion(threads, safe_id, resolved),
        "not_established": list(NOT_ESTABLISHED),
        "authority": AUTHORITY_STATEMENT,
    }
    packet["integrity"] = {"algorithm": "sha256 of the canonical JSON of every other field", "packet_sha256": _sha256(_canonical(packet))}
    return packet


def verify_review_packet(packet: Mapping[str, Any]) -> bool:
    """True when the packet's own hash matches its contents."""

    body = {key: value for key, value in packet.items() if key != "integrity"}
    integrity = packet.get("integrity")
    return isinstance(integrity, Mapping) and integrity.get("packet_sha256") == _sha256(_canonical(body))


def _cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def render_review_packet_markdown(packet: Mapping[str, Any]) -> str:
    """The same packet for a person to read. Everything in it is also in the JSON."""

    project = packet["project"]
    files = packet["retained_files"]
    findings = packet["findings"]
    proposals = packet["proposals"]
    discussion = packet["discussion"]
    lines: list[str] = [
        f"# Review packet: {project['name']}",
        "",
        f"Project `{project['project_id']}` · revision {project['revision']} · saved {project.get('saved_at') or 'unknown'}",
        "",
        f"Snapshot `{project['snapshot_sha256']}`",
        "",
        "## What this packet does not establish",
        "",
        *[f"- {item}" for item in packet["not_established"]],
        "",
        packet["authority"],
        "",
        "## Files kept with this revision",
        "",
    ]
    if files["status"] != "retained":
        lines += [f"No KiCad files are retained for this revision ({files['status'].replace('_', ' ')}).", ""]
    else:
        lines += ["| Kind | File | SHA-256 |", "| --- | --- | --- |"]
        for kind in ARTIFACT_KINDS:
            entry = files["files"].get(kind)
            lines.append(f"| {kind} | {_cell(entry['relative']) if entry else 'none'} | {_cell(entry['sha256']) if entry else ''} |")
        lines.append("")
    lines += [f"## Findings ({findings['total']})", ""]
    if not findings["items"]:
        lines += ["None recorded.", ""]
    else:
        lines += [
            f"By how they were established: " + ", ".join(f"{name} {count}" for name, count in findings["by_provenance"].items()) + f". Attested by the server: {findings['attested']}.",
            "",
            "| Category | Object | Finding | Established by | Attested |",
            "| --- | --- | --- | --- | --- |",
        ]
        for item in findings["items"]:
            prov = item["provenance"]
            lines.append(f"| {_cell(item['category'])} | {_cell(item['object_id']) or 'the design as a whole'} | {_cell(item['text'])} | {_cell(prov['kind'])}: {_cell(prov['basis'])} | {'yes' if prov['attested'] else 'no'} |")
        if findings["truncated"]:
            lines.append(f"\nOnly the first {MAX_FINDINGS} of {findings['total']} findings are listed.")
        lines.append("")
    lines += [f"## Proposals based on this revision ({proposals['total']})", ""]
    if not proposals["items"]:
        lines += ["None.", ""]
    for item in proposals["items"]:
        decision = item["decision"]
        who = f"{item['created_by']}{' (identity confirmed)' if item['created_by_verified'] else ' (name as typed)'}"
        status = decision["status"] + (" and out of date" if decision["out_of_date"] else "")
        lines += [f"### {item['candidate_id']} · {item['kind']} · {status}", "", f"Proposed by {who}." + (f" Reason: {item['note']}" if item["note"] else ""), ""]
        for op in item["operations"]:
            lines.append(f"- {op['op']} {op['target'] or ''} {('· ' + op['detail']) if op['detail'] else ''}".rstrip())
        checks = item["checks"]
        lines.append("")
        lines.append(f"Design-rule check: {'ran, ' + str(checks['new_violations']) + ' new violations' if checks['ran'] else 'did not run' + (' (' + str(checks['reason']) + ')' if checks['reason'] else '')}. Reported for the reviewer; it is not a decision.")
        if decision["status"] in {"accepted", "rejected"}:
            lines.append("")
            lines.append(f"{decision['status'].capitalize()} by {decision['decided_by']}" + (f" as revision {decision['accepted_revision']}" if decision["accepted_revision"] else "") + (f". “{decision['note']}”" if decision["note"] else "."))
        lines.append("")
    noun = "thread" if discussion["total"] == 1 else "threads"
    lines += [f"## Discussion ({discussion['total']} {noun}: {discussion['open']} open, {discussion['resolved']} resolved)", ""]
    if not discussion["threads"]:
        lines += ["None.", ""]
    for thread in discussion["threads"]:
        anchor = thread["anchor"]
        where = anchor.get("object_id") or (anchor.get("artifact") or {}).get("relative") or "the design"
        lines += [f"### {thread['thread_id']} · {thread['status']} · {where}" + ("" if thread["about_this_revision"] else f" · written on revision {anchor.get('revision')}"), ""]
        for event in thread["events"]:
            author = event["author"]
            tag = "identity confirmed" if event["author_verified"] else "name as typed"
            lines.append(f"- {event['type']} by {author['id']} ({tag})" + (f": {_cell(event['body'])}" if event["body"] else ""))
        lines.append("")
    lines += ["## Integrity", "", f"`{packet['integrity']['packet_sha256']}`", "", packet["integrity"]["algorithm"] + ".", ""]
    return "\n".join(lines)
