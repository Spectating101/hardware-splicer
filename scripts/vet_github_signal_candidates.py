#!/usr/bin/env python3
"""Attach review evidence to a feed without fetching or running candidates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Avoid same-directory scripts/hardware_splicer.py shadowing HS package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hardware_splicer.github_signal_vetting import load_pcm_feed, vet_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--feed", type=Path)
    source.add_argument("--kicad-pcm", help="Local packages.json/repository.json or metadata URL")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--offline", action="store_true", help="Skip all HTTP requests")
    args = parser.parse_args()
    try:
        feed = (load_pcm_feed(args.kicad_pcm, offline=args.offline) if args.kicad_pcm
                else json.loads(args.feed.read_text(encoding="utf-8")))
        if (not isinstance(feed, dict)
                or feed.get("schema_version") != "hardware_splicer.github_signal_feed.v1"
                or not isinstance(feed.get("candidates"), list)
                or any(not isinstance(c, dict) for c in feed["candidates"])):
            raise ValueError("expected a normalized candidate feed")
        enriched = {**feed, "candidates": [
            {**candidate, "vetting": vet_candidate(candidate, offline=args.offline)}
            for candidate in feed["candidates"]
        ]}
        args.out.write_text(json.dumps(enriched, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
