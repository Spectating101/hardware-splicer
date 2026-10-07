"""A review packet: what a reviewer was shown for one revision, in one hash-bound document.

The packet reports. It is built only from what the project already holds (the revision, its findings and how each was
established, the files the revision retained and their hashes, proposals and who decided them, and the discussion), and it
changes nothing. It never opens fabrication, power-on or release, and it says in plain words what it does not establish.

It is deterministic: the same project state gives the same bytes, so two people holding the same packet can tell they hold
the same thing. No clock reading and no credential goes into it.

Everything people wrote (names, notes, comments, finding text) is treated as untrusted. In the document it is escaped so it
can only ever read as text, never as a heading or a link that could pass for part of the packet. Credentials and absolute
paths are removed on a best-effort basis, before the hash is taken, and the packet says how many were. Nothing is dropped
silently: every list says when it was cut short and how many there were.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .artifact_retention import ARTIFACT_KINDS, ArtifactIntegrityError, load_artifact_pin
from .finding_provenance import project_findings_payload
from .project_candidates import list_candidates, review_state
from .project_review_store import ProjectReviewStore
from .project_store import ProjectStore, validate_project_id
from .project_thread_store import ProjectThreadStore

PACKET_SCHEMA = "hardware_splicer.review_packet.v1"
INTEGRITY_ALGORITHM = "sha256 of the canonical JSON of every other field, with integrity.packet_sha256 left out"
MAX_FINDINGS = 1000
MAX_THREADS = 100
MAX_EVENTS_PER_THREAD = 50
MAX_PROPOSALS = 100
MAX_OPERATIONS = 20
MAX_TEXT = 500
# The thread store walks every event file of every thread each time it is asked, so a project with a very large
# discussion is not read at all: the packet says how big it is and that it was left out.
READ_BUDGET_THREADS = 100
READ_BUDGET_EVENTS = 2000

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

_REDACTIONS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?:.*?-----END [A-Z ]*PRIVATE KEY-----)?", re.S), "[redacted credential]"),
    ("credential", re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"), "[redacted credential]"),
    ("credential", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"), "[redacted credential]"),
    ("credential", re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{8,}|\bgh[pousr]_[A-Za-z0-9]{16,}|\bAKIA[0-9A-Z]{12,}|\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[redacted credential]"),
    # Credential names and their values are handled by _redact_assignments below, which decides by the words a name is made of.
    ("path", re.compile(r"(?<![\w.:/-])(?:/(?:home|Users|root|tmp|var|etc|opt|mnt|srv|private|media)/[^\s\"'<>)]+|[A-Za-z]:\\[^\s\"'<>)]+)"), "[redacted path]"),
)


# A name is credential-like when it is made of words that include a secret word, however it is written (API_TOKEN_V2,
# clientAPIKey, db-password), unless its last word says it is about the secret rather than being one (token_count,
# password_policy). Names are split into words at delimiters and at lower-to-upper and acronym boundaries.
_SECRET_WORDS = frozenset({"secret", "secrets", "token", "tokens", "password", "passwords", "passwd", "passphrase", "credential", "credentials", "authorization", "apikey", "apikeys"})
_SECRET_PAIRS = frozenset({("api", "key"), ("api", "keys"), ("private", "key"), ("private", "keys"), ("access", "key"), ("secret", "key")})
_ABOUT_A_SECRET = frozenset({"count", "counts", "length", "len", "size", "limit", "limits", "max", "min", "ttl", "expiry", "expires", "lifetime", "policy", "policies", "enabled", "required", "interval", "timeout", "rate", "budget", "usage", "cost"})
_WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")
_ASSIGNMENT = re.compile(
    r"""(?x)
    (?P<name>["']?(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9_-]{0,63}(?![A-Za-z0-9_-])["']?\s*[:=]\s*)
    (?!\[redacted)
    (?P<value>"(?:[^"\\]|\\.)*(?:"|\Z)|'(?:[^'\\]|\\.)*(?:'|\Z)|\S+)
    """
)


def _looks_like_a_credential_name(name: str) -> bool:
    words = [word.lower() for word in _WORD.findall(name.strip("\"'"))]
    if not words:
        return False
    if words[-1] in _ABOUT_A_SECRET:
        return False
    if any(word in _SECRET_WORDS for word in words):
        return True
    return any(pair in _SECRET_PAIRS for pair in zip(words, words[1:]))



class _Scrub:
    """Removes credentials and absolute paths from free text and counts what it removed. Best effort, and said to be."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def text(self, value: Any, limit: int = MAX_TEXT) -> str:
        # Only the part that can survive the final clip is scanned, so the work does not grow with the size of the input. A
        # secret that starts inside the kept part and runs past this window is still caught up to the window's end, and what
        # lies beyond the final limit is never shown.
        text = str(value if value is not None else "")[: limit * 4]
        for kind, pattern, replacement in _REDACTIONS:
            text, hits = pattern.subn(replacement, text)
            if hits:
                self.counts[kind] = self.counts.get(kind, 0) + hits
        hidden = 0
        pieces: list[str] = []
        position = 0
        while True:
            match = _ASSIGNMENT.search(text, position)
            if match is None:
                break
            name = match.group("name").split(":")[0].split("=")[0].strip()
            if _looks_like_a_credential_name(name):
                pieces.append(text[position : match.start()])
                pieces.append(match.group("name") + "[redacted credential]")
                position = match.end()
                hidden += 1
            else:
                # Not a credential. Move on from the end of the *name*, so an assignment that sits inside this one's value
                # (mode=ok;password=x, url=https://h/?token=x) is still looked at.
                pieces.append(text[position : match.end("name")])
                position = match.end("name")
        pieces.append(text[position:])
        text = "".join(pieces)
        if hidden:
            self.counts["credential"] = self.counts.get("credential", 0) + hidden
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def optional(self, value: Any, limit: int = MAX_TEXT) -> str | None:
        return self.text(value, limit) or None

    def summary(self) -> dict[str, Any]:
        return {"count": sum(self.counts.values()), "by_kind": dict(sorted(self.counts.items())), "note": "Credentials and absolute paths are removed on a best-effort basis. Do not rely on this to make a secret safe to write down."}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _counts(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        name = str(row.get(key) or "unknown")
        out[name] = out.get(name, 0) + 1
    return dict(sorted(out.items()))


def _artifacts(store: ProjectStore, project_id: str, revision: int, scrub: _Scrub) -> dict[str, Any]:
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
            {"relative": scrub.text(entry.get("relative"), 300), "sha256": entry.get("sha256"), "size_bytes": entry.get("size_bytes")}
            if isinstance(entry, Mapping)
            else None
        )
    return {"status": "retained", "retention_basis": pin.get("retention_basis"), "files": files}


def _findings(snapshot: Mapping[str, Any], revision: int, scrub: _Scrub) -> dict[str, Any]:
    rows = project_findings_payload(snapshot, revision)["findings"]
    listed = []
    for row in rows[:MAX_FINDINGS]:
        provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
        listed.append(
            {
                "finding_id": row.get("finding_id"),
                "category": scrub.text(row.get("category"), 80),
                "object_id": scrub.optional(row.get("object_id"), 200),
                "text": scrub.text(row.get("text")),
                "provenance": {
                    "kind": provenance.get("kind"),
                    "basis": scrub.text(provenance.get("basis")),
                    "source_ref": scrub.optional(provenance.get("source_ref"), 200),
                    "authority_ceiling": provenance.get("authority_ceiling"),
                    "attested": bool(provenance.get("attested")),
                },
            }
        )
    flat = [{"category": row.get("category"), "kind": (row.get("provenance") or {}).get("kind"), "attested": bool((row.get("provenance") or {}).get("attested"))} for row in rows]
    return {
        "total": len(rows),
        "listed": len(listed),
        "truncated": len(rows) > MAX_FINDINGS,
        "by_category": _counts(flat, "category"),
        "by_provenance": _counts(flat, "kind"),
        "attested": sum(1 for row in flat if row["attested"]),
        "items": listed,
    }


# Counting stops here and says "more than", so the answer is the same however the filesystem happens to list names.
THREAD_COUNT_CEILING = 1000
EVENT_COUNT_CEILING = 20000


ENTRY_SCAN_CEILING = 20000


def _scan(path: str, ceiling: int) -> tuple[list[tuple[str, bool, bool]], bool]:
    """The entries of a directory as (name, is_symlink, is_dir), and whether there were more than `ceiling` of them. The
    listing is complete unless that is true, so what is concluded from it does not depend on the order names came in."""

    entries: list[tuple[str, bool, bool]] = []
    with os.scandir(path) as listing:
        for entry in listing:
            entries.append((entry.name, entry.is_symlink(), entry.is_dir(follow_symlinks=False)))
            if len(entries) > ceiling:
                return entries, True
    return entries, False


def _discussion_size(store: ProjectStore, project_id: str) -> dict[str, Any] | None:
    """How many threads and event files the project has, counted by name only and never read.

    Each figure is exact or, past a ceiling, absent with an `*_over` bound. The answer does not depend on the order the
    filesystem lists names. One ceiling applies to the whole listing of a directory, and conclusions (directories over a
    limit, a symbolic link) are drawn only from a complete listing; a listing too long to complete is simply "uncounted".
    Directories are taken in sorted order. None means a symbolic link was found where there should not be one, and the
    discussion is not read.
    """

    root = str(store.root / project_id / "threads")
    if os.path.islink(root):
        return None
    if not os.path.isdir(root):
        return {"threads": 0, "threads_over": None, "events": 0, "events_over": None}
    try:
        top, incomplete = _scan(root, ENTRY_SCAN_CEILING)
        if incomplete:
            return {"threads": None, "threads_over": None, "events": None, "events_over": None, "uncounted": True}
        dirs = sorted(name for name, _link, is_dir in top if is_dir)
        if len(dirs) > THREAD_COUNT_CEILING:
            return {"threads": None, "threads_over": THREAD_COUNT_CEILING, "events": None, "events_over": None}
        if any(is_link for _name, is_link, _is_dir in top):
            return None
        if len(dirs) > READ_BUDGET_THREADS:
            return {"threads": len(dirs), "threads_over": None, "events": None, "events_over": None}
        events = 0
        for name in dirs:
            folder = os.path.join(root, name, "events")
            if os.path.islink(folder):
                return None
            if not os.path.isdir(folder):
                continue
            entries, incomplete = _scan(folder, EVENT_COUNT_CEILING - events)
            if incomplete:
                return {"threads": len(dirs), "threads_over": None, "events": None, "events_over": EVENT_COUNT_CEILING}
            if any(is_link for _name, is_link, _is_dir in entries):
                return None
            events += len(entries)
    except OSError:
        return None
    return {"threads": len(dirs), "threads_over": None, "events": events, "events_over": None}


def _discussion(store: ProjectStore, threads: ProjectThreadStore, project_id: str, revision: int, scrub: _Scrub) -> dict[str, Any]:
    size = _discussion_size(store, project_id)
    if size is None or (size["threads"] or 0) > READ_BUDGET_THREADS or size["threads"] is None or size["events"] is None or size["events"] > READ_BUDGET_EVENTS:
        return {
            "status": "not_read",
            "reason": "unreadable" if size is None else "too large to include",
            "total": size["threads"] if size else None,
            "total_over": size["threads_over"] if size else None,
            "total_events": size["events"] if size else None,
            "total_events_over": size["events_over"] if size else None,
            "limits": {"threads": READ_BUDGET_THREADS, "events": READ_BUDGET_EVENTS},
            "open": None,
            "resolved": None,
            "threads": [],
        }
    rows = threads.list_threads(project_id)
    out = []
    for row in rows[:MAX_THREADS]:
        full = threads.get_thread(project_id, str(row.get("thread_id")))
        all_events = full.get("events") or []
        events = []
        for event in all_events[:MAX_EVENTS_PER_THREAD]:
            author = event.get("author") if isinstance(event.get("author"), Mapping) else {}
            events.append(
                {
                    "seq": event.get("seq"),
                    "type": event.get("type"),
                    "created_at": event.get("created_at"),
                    "author": {"kind": author.get("kind"), "id": scrub.text(author.get("id"), 120)},
                    # Whether the server confirmed who this was, as against a name someone typed.
                    "author_verified": bool(event.get("author_verified")),
                    "body": scrub.optional(event.get("body")),
                }
            )
        anchor = full.get("anchor") if isinstance(full.get("anchor"), Mapping) else {}
        artifact = anchor.get("artifact") if isinstance(anchor.get("artifact"), Mapping) else None
        out.append(
            {
                "thread_id": full.get("thread_id"),
                "status": full.get("status"),
                "anchor": {
                    "revision": anchor.get("revision"),
                    "object_id": scrub.optional(anchor.get("object_id"), 200),
                    "artifact": {"relative": scrub.text(artifact.get("relative"), 300), "kind": artifact.get("kind")} if artifact else None,
                    "position": anchor.get("position"),
                },
                "about_this_revision": anchor.get("revision") == revision,
                "comment_count": full.get("comment_count"),
                "events_total": len(all_events),
                "events_listed": len(events),
                "events_truncated": len(all_events) > MAX_EVENTS_PER_THREAD,
                "events": events,
            }
        )
    return {
        "status": "listed",
        "total": len(rows),
        "listed": len(out),
        "truncated": len(rows) > MAX_THREADS,
        "open": sum(1 for row in rows if row.get("status") == "open"),
        "resolved": sum(1 for row in rows if row.get("status") == "resolved"),
        "threads": out,
    }


def _proposals(store: ProjectStore, reviews: ProjectReviewStore, project_id: str, revision: int, scrub: _Scrub) -> dict[str, Any]:
    mine = [row for row in list_candidates(store, project_id) if row.get("base_revision") == revision]
    out = []
    for row in mine[:MAX_PROPOSALS]:
        state = review_state(store, reviews, project_id, row)
        checks = row.get("checks") if isinstance(row.get("checks"), Mapping) else {}
        diff = row.get("diff") if isinstance(row.get("diff"), Mapping) else {}
        applied = [item for item in (row.get("applied") or []) if isinstance(item, Mapping)]
        out.append(
            {
                "candidate_id": row.get("candidate_id"),
                "kind": row.get("kind"),
                "created_by": scrub.text(row.get("created_by"), 120),
                "created_by_verified": bool(row.get("verified")),
                "note": scrub.optional(row.get("note")),
                "changes": diff.get("summary"),
                "operations_total": len(applied),
                "operations_truncated": len(applied) > MAX_OPERATIONS,
                "operations": [
                    {"op": scrub.text(item.get("op"), 60), "target": scrub.optional((item.get("target") or {}).get("ref") or (item.get("target") or {}).get("uuid"), 120), "detail": scrub.optional(item.get("detail"), 200)}
                    for item in applied[:MAX_OPERATIONS]
                ],
                "checks": {
                    "ran": bool(checks.get("ran")),
                    "engine": checks.get("engine"),
                    "new_violations": checks.get("new_violations"),
                    "reason": scrub.optional(checks.get("reason"), 200),
                },
                "decision": {
                    "status": state.get("status"),
                    "decided_by": scrub.optional(state.get("decided_by"), 120),
                    "note": scrub.optional(state.get("note")),
                    "accepted_revision": state.get("accepted_revision"),
                    "out_of_date": bool(state.get("stale")),
                },
            }
        )
    return {
        "total": len(mine),
        "listed": len(out),
        "truncated": len(mine) > MAX_PROPOSALS,
        "pending": sum(1 for item in out if item["decision"]["status"] == "pending" and not item["decision"]["out_of_date"]),
        "accepted": sum(1 for item in out if item["decision"]["status"] == "accepted"),
        "rejected": sum(1 for item in out if item["decision"]["status"] == "rejected"),
        "items": out,
    }


def _integrity(packet: Mapping[str, Any]) -> dict[str, str]:
    """The hash covers everything, including the algorithm statement; only the digest itself is left out."""

    body = {key: value for key, value in packet.items() if key != "integrity"}
    body["integrity"] = {"algorithm": INTEGRITY_ALGORITHM}
    return {"algorithm": INTEGRITY_ALGORITHM, "packet_sha256": _sha256(_canonical(body))}


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
    scrub = _Scrub()

    packet: dict[str, Any] = {
        "schema_version": PACKET_SCHEMA,
        "project": {
            "project_id": safe_id,
            "name": scrub.text(snapshot.get("projectName") or snapshot.get("name") or safe_id, 200),
            "revision": resolved,
            "saved_at": envelope.get("saved_at"),
            "snapshot_sha256": _sha256(_canonical(snapshot)),
        },
        "retained_files": _artifacts(store, safe_id, resolved, scrub),
        "findings": _findings(snapshot, resolved, scrub),
        "proposals": _proposals(store, reviews, safe_id, resolved, scrub),
        "discussion": _discussion(store, threads, safe_id, resolved, scrub),
        "not_established": list(NOT_ESTABLISHED),
        "authority": AUTHORITY_STATEMENT,
    }
    packet["redactions"] = scrub.summary()
    packet["integrity"] = _integrity(packet)
    return packet


def verify_review_packet(packet: Mapping[str, Any]) -> bool:
    """True when the packet's hash matches its contents and its integrity block holds exactly what it should."""

    integrity = packet.get("integrity")
    if not isinstance(integrity, Mapping) or set(integrity) != {"algorithm", "packet_sha256"}:
        return False
    if integrity.get("algorithm") != INTEGRITY_ALGORITHM:
        return False
    return integrity.get("packet_sha256") == _integrity(packet)["packet_sha256"]


_MD_SPECIAL = re.compile(r"([\\`*_\[\]()#|~!{}<>&])")


def _md(value: Any) -> str:
    """Text a person wrote, made safe to put in a document: one line, with everything that could mean markup escaped, so it
    can only read as the words it is."""

    text = re.sub(r"\s+", " ", str(value if value is not None else "")).strip()
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_\[\]()#|~!{}])", r"\\\1", text)


def _code(value: Any) -> str:
    """A value shown in a code span; nothing in it can close the span or start a line."""

    text = re.sub(r"[\s`]+", " ", str(value if value is not None else "")).strip()
    return f"`{text}`"


def _shown(noun: str, listed: int, total: int) -> str:
    return "" if listed >= total else f" Showing {listed} of {total} {noun}; the rest are not in this packet."


def _size_words(discussion: Mapping[str, Any]) -> str:
    """How big the left-out discussion is, as exactly as it was counted, without implying more than was."""

    if discussion.get("reason") == "unreadable":
        return ""
    limits = discussion["limits"]
    if discussion["total"] is not None:
        threads = f"{int(discussion['total'])} thread" + ("" if discussion["total"] == 1 else "s")
    elif discussion.get("total_over") is not None:
        threads = f"more than {int(discussion['total_over'])} threads"
    else:
        threads = "threads not counted"
    if discussion["total_events"] is not None:
        events = f"{int(discussion['total_events'])} events"
    elif discussion["total_events_over"] is not None:
        events = f"more than {int(discussion['total_events_over'])} events"
    else:
        events = "events not counted"
    return f" ({threads}, {events}; this packet reads at most {int(limits['threads'])} threads and {int(limits['events'])} events)"


def render_review_packet_markdown(packet: Mapping[str, Any]) -> str:
    """The same packet for a person to read. Everything in it is also in the JSON. All text people wrote is escaped, so
    nothing in a name, note or comment can pass for a section, a decision or a hash of this document."""

    project = packet["project"]
    files = packet["retained_files"]
    findings = packet["findings"]
    proposals = packet["proposals"]
    discussion = packet["discussion"]
    lines: list[str] = [
        f"# Review packet: {_md(project['name'])}",
        "",
        f"Project {_code(project['project_id'])} · revision {int(project['revision'])} · saved {_md(project.get('saved_at') or 'unknown')}",
        "",
        f"Snapshot {_code(project['snapshot_sha256'])}",
        "",
        "## What this packet does not establish",
        "",
        *[f"- {_md(item)}" for item in packet["not_established"]],
        "",
        _md(packet["authority"]),
        "",
        "## Files kept with this revision",
        "",
    ]
    if files["status"] != "retained":
        lines += [f"No KiCad files are retained for this revision ({_md(str(files['status']).replace('_', ' '))}).", ""]
    else:
        lines += ["| Kind | File | SHA-256 |", "| --- | --- | --- |"]
        for kind in ARTIFACT_KINDS:
            entry = files["files"].get(kind)
            lines.append(f"| {kind} | {_md(entry['relative']) if entry else 'none'} | {_code(entry['sha256']) if entry else ''} |")
        lines.append("")
    lines += [f"## Findings ({int(findings['total'])})", ""]
    if not findings["items"]:
        lines += ["None recorded.", ""]
    else:
        lines += [
            "By how they were established: " + ", ".join(f"{_md(name)} {int(count)}" for name, count in findings["by_provenance"].items()) + f". Attested by the server: {int(findings['attested'])}.",
            "",
            "| Category | Object | Finding | Established by | Attested |",
            "| --- | --- | --- | --- | --- |",
        ]
        for item in findings["items"]:
            prov = item["provenance"]
            lines.append(f"| {_md(item['category'])} | {_md(item['object_id']) or 'the design as a whole'} | {_md(item['text'])} | {_md(prov['kind'])}: {_md(prov['basis'])} | {'yes' if prov['attested'] else 'no'} |")
        notice = _shown("findings", int(findings["listed"]), int(findings["total"]))
        if notice:
            lines += ["", notice.strip()]
        lines.append("")
    lines += [f"## Proposals based on this revision ({int(proposals['total'])})", ""]
    if not proposals["items"]:
        lines += ["None.", ""]
    for item in proposals["items"]:
        decision = item["decision"]
        who = f"{_md(item['created_by'])}{' (identity confirmed)' if item['created_by_verified'] else ' (name as typed)'}"
        status = _md(decision["status"]) + (" and out of date" if decision["out_of_date"] else "")
        lines += [f"### {_code(item['candidate_id'])} · {_md(item['kind'])} · {status}", "", f"Proposed by {who}." + (f" Reason: {_md(item['note'])}" if item["note"] else ""), ""]
        for op in item["operations"]:
            lines.append(f"- {_md(op['op'])} {_md(op['target'])}" + (f" · {_md(op['detail'])}" if op["detail"] else ""))
        if item["operations_truncated"]:
            lines.append(f"- Showing {len(item['operations'])} of {int(item['operations_total'])} operations; the rest are not in this packet.")
        checks = item["checks"]
        ran = f"ran, {int(checks['new_violations'] or 0)} new violations" if checks["ran"] else "did not run" + (f" ({_md(checks['reason'])})" if checks["reason"] else "")
        lines += ["", f"Design-rule check: {ran}. Reported for the reviewer; it is not a decision."]
        if decision["status"] in {"accepted", "rejected"}:
            lines += ["", f"{_md(str(decision['status']).capitalize())} by {_md(decision['decided_by'] or 'an operator')}" + (f" as revision {int(decision['accepted_revision'])}" if decision["accepted_revision"] else "") + (f". “{_md(decision['note'])}”" if decision["note"] else ".")]
        lines.append("")
    if proposals["truncated"]:
        lines += [_shown("proposals", int(proposals["listed"]), int(proposals["total"])).strip(), ""]

    if discussion["status"] != "listed":
        lines += [
            "## Discussion",
            "",
            f"Not included: the discussion is {_md(discussion['reason'])}" + _size_words(discussion) + ".",
            "",
        ]
    else:
        noun = "thread" if discussion["total"] == 1 else "threads"
        lines += [f"## Discussion ({int(discussion['total'])} {noun}: {int(discussion['open'])} open, {int(discussion['resolved'])} resolved)", ""]
        if not discussion["threads"]:
            lines += ["None.", ""]
        for thread in discussion["threads"]:
            anchor = thread["anchor"]
            where = anchor.get("object_id") or (anchor.get("artifact") or {}).get("relative") or "the design"
            lines += [f"### {_code(thread['thread_id'])} · {_md(thread['status'])} · {_md(where)}" + ("" if thread["about_this_revision"] else f" · written on revision {int(anchor.get('revision') or 0)}"), ""]
            for event in thread["events"]:
                author = event["author"]
                tag = "identity confirmed" if event["author_verified"] else "name as typed"
                lines.append(f"- {_md(event['type'])} by {_md(author['id'])} ({tag})" + (f": {_md(event['body'])}" if event["body"] else ""))
            if thread["events_truncated"]:
                lines.append(f"- Showing {int(thread['events_listed'])} of {int(thread['events_total'])} entries; the rest are not in this packet.")
            lines.append("")
        if discussion["truncated"]:
            lines += [_shown("threads", int(discussion["listed"]), int(discussion["total"])).strip(), ""]

    redactions = packet.get("redactions") or {}
    lines += ["## Removed from this packet", ""]
    if redactions.get("count"):
        lines += [f"{int(redactions['count'])} credential-like or file-path-like strings in text people wrote were replaced with a marker (" + ", ".join(f"{_md(kind)} {int(count)}" for kind, count in (redactions.get("by_kind") or {}).items()) + "). This is best-effort."]
    else:
        lines += ["Nothing was replaced. This is a best-effort check, not a guarantee."]
    lines += ["", "## Integrity", "", _code(packet["integrity"]["packet_sha256"]), "", _md(INTEGRITY_ALGORITHM) + ".", ""]
    return "\n".join(lines)
