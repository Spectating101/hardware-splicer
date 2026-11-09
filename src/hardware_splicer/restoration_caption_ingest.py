"""Timestamp-limited YouTube WebVTT repair evidence; NO video outcome access.

Caller obtains captions separately and supplies the VTT path. Only clips
whose START time is within the declared early-intake cutoff are admitted.
Overlapping auto-caption fragments are deduped; raw transcript is not
committed to repository or treated as an instruction source.
"""
from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path
from typing import Any

from .restoration_reasoning_agent import build_context

CUE = re.compile(
    r"(?m)^(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\.(?P<ms>\d{3})"
    r"\s+-->\s+"
    r"(?P<eh>\d{2}):(?P<em>\d{2}):(?P<es>\d{2})\.(?P<ems>\d{3})"
)
TAG = re.compile(r"<[^>]*>")


def parse_early_vtt(path: Path, *, cutoff_s: int = 120,
                    start_s: int = 0, max_chunks: int = 6,
                    chars_per_chunk: int = 480) -> dict[str, Any]:
    if not 10 <= cutoff_s <= 600 or not 0 <= start_s < cutoff_s:
        raise ValueError("source window must fit within 0..600 seconds")
    if not 1 <= max_chunks <= 12 or not 100 <= chars_per_chunk <= 1500:
        raise ValueError("caption evidence limits exceeded")
    raw = path.read_bytes()
    if len(raw) > 4_000_000:
        raise ValueError("caption file exceeds source processing limit")
    text = raw.decode("utf-8-sig")
    if not text.lstrip().startswith("WEBVTT"):
        raise ValueError("not a WebVTT caption file")
    snippets: list[tuple[float, str]] = []
    for block in re.split(r"\r?\n\s*\r?\n", text):
        match = CUE.search(block)
        if match is None:
            continue
        def sec(prefix: str) -> float:
            keys = ("h","m","s","ms") if not prefix else ("eh","em","es","ems")
            a,b,c,d = [int(match[x]) for x in keys]
            return a*3600 + b*60 + c + d/1000
        start, end = sec(""), sec("end")
        if start > cutoff_s:
            break
        if start < start_s or end > cutoff_s:
            continue
        # Auto-caption finalized single-line short cues avoid rolling text repetition.
        if not (0 <= end-start <= .2):
            continue
        lines = [
            html.unescape(TAG.sub("", x)).strip()
            for x in block.splitlines()
            if "-->" not in x and not x.startswith(("WEBVTT","Kind:","Language:"))
        ]
        lines = [x for x in lines if x]
        if len(lines) != 1:
            continue
        words = lines[0]
        if words and (not snippets or snippets[-1][1] != words):
            snippets.append((start, words))
    if not snippets:
        raise ValueError("no safe early finalized caption cues found")
    # Split earliest allowed span into timestamped intervals, not full transcript.
    width = (cutoff_s - start_s) / max_chunks
    batches: list[list[tuple[float,str]]] = [[] for _ in range(max_chunks)]
    for stamp, words in snippets:
        batches[min(max_chunks-1,int((stamp-start_s)/width))].append((stamp,words))
    chunks=[]
    for batch in batches:
        if not batch:
            continue
        excerpt = " ".join(s for _,s in batch)
        if len(excerpt) > chars_per_chunk:
            excerpt=excerpt[:chars_per_chunk].rsplit(" ",1)[0] + "…"
        chunks.append({
            "start_second":round(batch[0][0],3),
            "end_second":round(batch[-1][0],3),
            "auto_caption_excerpt":excerpt,
            "auto_generated_and_unverified":True,
        })
    return {
        "schema":"hs.restoration.early_vtt.v1",
        "raw_vtt_sha256":hashlib.sha256(raw).hexdigest(),
        "window_start_seconds":start_s,
        "cutoff_seconds":cutoff_s,
        "source_kind":"YouTube auto-caption WebVTT (not video frame understanding)",
        "total_early_final_cues":len(snippets),
        "chunks":chunks,
    }


def caption_case_context(*, case_id: str, device: str, title_symptom: str,
                         video_url: str, hazards: list[str], vtt_path: Path,
                         cutoff_s: int = 120) -> dict[str, Any]:
    if "root cause" in title_symptom.lower() or "fixed by" in title_symptom.lower():
        raise ValueError("title reveals repair outcome")
    parsed = parse_early_vtt(vtt_path,cutoff_s=cutoff_s)
    initial = [title_symptom] + [
        f"Unverified creator speech at {ch['start_second']}–{ch['end_second']}s: {ch['auto_caption_excerpt']}"
        for ch in parsed["chunks"]
    ]
    ctx = build_context(
        case_id=case_id,device=device,
        repair_intake={"device_hint":device,"symptoms":initial},
        source_url=video_url,hazards=hazards,
        evidence_stage=f"auto_vtt_first_{cutoff_s}s",
    )
    ctx["caption_provenance"] = {
        "raw_vtt_sha256":parsed["raw_vtt_sha256"],
        "cutoff_seconds":cutoff_s,
        "total_early_final_cues":parsed["total_early_final_cues"],
        "no_video_frames":True,
        "caption_reliability":"unverified_auto_generated",
    }
    return ctx
