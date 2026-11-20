"""Deterministic KiCad 9 serialization identifiers without rewriting source IDs.

Earlier global "new UUID" enumeration was order-dependent when loading older
third-party boards: KiCad synthesizes many IDs, and shuffles new-footprint
serialization order. Bind generated UUIDs to each top-level native source
object's *semantic serialized content* instead, preserving existing IDs.

This does NOT validate electrical design; native KiCad DRC remains authority.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from collections import Counter
from pathlib import Path

# KiCad 9 uses uuid; older inputs can use tstamp. UUIDs in quotes or bare.
ID_RE = re.compile(r'\((?:uuid|tstamp)\s+"?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"?\)',re.I)


def top_level_ranges(s: str) -> list[tuple[int,int]]:
    """Locate direct children of the root S-expression, ignoring quoted text."""
    stack=[]
    children=[]
    inside=False
    escaped=False
    for i,ch in enumerate(s):
        if inside:
            if escaped:
                escaped=False
            elif ch=="\\":
                escaped=True
            elif ch=='"':
                inside=False
            continue
        if ch=='"':
            inside=True
        elif ch=="(":
            if len(stack)==1:
                start=i
            stack.append(i)
        elif ch==")":
            if not stack:
                raise ValueError("UNBALANCED_KICAD_PARENS")
            if len(stack)==2:
                children.append((start,i+1))
            stack.pop()
    if inside or stack:
        raise ValueError("UNCLOSED_KICAD_SOURCE")
    if not children:
        raise ValueError("NO_KICAD_TOP_LEVEL_OBJECTS")
    return children


def semantic_parent_key(chunk: str) -> str:
    """Ignore KiCad identity tokens but not net/geometry or other attributes."""
    noid=ID_RE.sub('(uuid "__ID__")',chunk)
    return hashlib.sha256(noid.encode()).hexdigest()


def stabilize_ids(source: Path, edited: Path) -> dict:
    original=source.read_text(errors="replace")
    s=edited.read_text(errors="replace")
    source_uuids={m.group(1).lower() for m in ID_RE.finditer(original)}
    source_digest=hashlib.sha256(source.read_bytes()).hexdigest()
    replacements=[]
    by_parent=Counter()
    kept_original=0
    generated=0
    for start,end in top_level_ranges(s):
        chunk=s[start:end]
        parent=semantic_parent_key(chunk)
        count=by_parent[parent]
        by_parent[parent]+=1
        local_index=0
        for m in ID_RE.finditer(chunk):
            old=m.group(1).lower()
            if old in source_uuids:
                kept_original+=1
                continue
            key="hs-kicad-source-identity-v2|"+source_digest+"|"+parent+"|"+str(count)+"|"+str(local_index)
            stable=str(uuid.uuid5(uuid.NAMESPACE_URL,key))
            local_index+=1
            replacements.append((start+m.start(1),start+m.end(1),stable))
            generated+=1
    # Apply only inside native UUID token spans, not globally anywhere.
    for start,end,stable in reversed(replacements):
        s=s[:start]+stable+s[end:]
    all_ids=[m.group(1).lower() for m in ID_RE.finditer(s)]
    duplicates=[x for x,n in Counter(all_ids).items() if n>1]
    if duplicates:
        # Existing source duplicates may be legal legacy references; fail on
        # newly generated duplicates, but do not tamper with original source.
        new_dupes=[i for i in duplicates if i not in source_uuids]
        if new_dupes:
            raise ValueError("GENERATED_UUID_COLLISION")
    edited.write_text(s)
    return {
        "source_sha256":source_digest,
        "synthesized_identifiers_stabilized":generated,
        "preexisting_ids_preserved":kept_original,
        "source_uuid_count":len(source_uuids),
        "physical_validation":False,
    }
