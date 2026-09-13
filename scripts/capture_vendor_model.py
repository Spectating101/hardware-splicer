#!/usr/bin/env python3
"""Capture one explicitly selected manufacturer model into bytes + immutable manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.vendor_model_capture import capture_vendor_model_url, manifest_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-host", action="append", required=True)
    parser.add_argument("--filename", required=True)
    parser.add_argument("--expected-kind", required=True, choices=["IBIS", "Verilog"])
    parser.add_argument("--expected-sha256")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=32 * 1024 * 1024)
    args = parser.parse_args()

    payload, manifest = capture_vendor_model_url(
        model_id=args.model_id,
        url=args.url,
        expected_hosts=args.expected_host,
        filename=args.filename,
        expected_model_kind=args.expected_kind,
        expected_sha256=args.expected_sha256,
        max_bytes=args.max_bytes,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    bytes_path = args.out_dir / args.filename
    manifest_path = args.out_dir / f"{args.model_id}.capture.json"
    bytes_path.write_bytes(payload)
    manifest_path.write_text(manifest_json(manifest), encoding="utf-8")

    print(
        json.dumps(
            {
                "bytes_path": str(bytes_path),
                "manifest_path": str(manifest_path),
                "sha256": manifest["sha256"],
                "expected_model_kind": manifest["expected_model_kind"],
                "recognized_expected_model_file_count": manifest[
                    "recognized_expected_model_file_count"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
