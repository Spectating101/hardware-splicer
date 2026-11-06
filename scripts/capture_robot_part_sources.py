#!/usr/bin/env python3
"""Capture the text of every source the robot part library cites, so its quotes can be checked offline.

HTML pages become their visible text; PDFs go through ``pdftotext``. Captures are third-party content, so they live
under the gitignored cache, not in the repository; ``verify_robot_part_quotes.py`` records each capture's sha256 in its
tracked result. A source that cannot be fetched is reported and makes the script exit non-zero; it is never skipped
silently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.robot_parts import html_to_text, load_parts  # noqa: E402

DEFAULT_DIR = ROOT / ".cache" / "hardware-splicer" / "robot_part_sources"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) HS-robot-parts-capture/1"


def _fetch(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=40) as reply:
        return reply.read(), reply.headers.get("Content-Type", "")


def _pdf_text(raw: bytes) -> str:
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "source.pdf"
        pdf.write_bytes(raw)
        return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True).stdout.decode(
            "utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture-dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--refresh", action="store_true", help="re-fetch sources that already have a capture")
    args = ap.parse_args()
    args.capture_dir.mkdir(parents=True, exist_ok=True)
    index_path = args.capture_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {}
    urls = sorted({s["url"] for p in load_parts() for s in p["sources"]} | {q["source"] for p in load_parts() for q in p["quotes"]})
    failed = []
    for url in urls:
        if url in index and (args.capture_dir / index[url]).is_file() and not args.refresh:
            continue
        try:
            raw, ctype = _fetch(url)
            text = _pdf_text(raw) if raw[:5] == b"%PDF-" or "pdf" in ctype else html_to_text(raw.decode("utf-8", errors="replace"))
        except Exception as e:  # noqa: BLE001 - every failure is reported below
            failed.append({"url": url, "error": f"{type(e).__name__}: {e}"})
            continue
        name = hashlib.sha1(url.encode()).hexdigest()[:16] + ".txt"
        (args.capture_dir / name).write_text(text, encoding="utf-8")
        index[url] = name
        print(f"captured {url} -> {name} ({len(text)} chars)")
    index_path.write_text(json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for f in failed:
        print(f"FAILED {f['url']}: {f['error']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
