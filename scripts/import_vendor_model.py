#!/usr/bin/env python3
"""Import a vendor simulation model downloaded through a browser/session.

The command never executes the model and never publishes raw model bytes. It validates the
selected model against the frozen HS vendor-model registry, hashes the payload and recognized
archive members, and writes only the capture manifest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.spi_virtual_target import build_vendor_model_registry
from hardware_splicer.vendor_model_capture import capture_vendor_model_file


def _registry_row(model_id: str) -> dict:
    registry = build_vendor_model_registry()
    for row in registry.get("models", []):
        if row.get("model_id") == model_id:
            return row
    raise SystemExit(f"unknown vendor model id: {model_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--max-bytes", type=int, default=32 * 1024 * 1024)
    args = parser.parse_args()

    row = _registry_row(args.model_id)
    source_url = row.get("download_url") or row.get("landing_url")
    if not source_url:
        raise SystemExit(f"vendor model {args.model_id} has no official source locator")

    _, manifest = capture_vendor_model_file(
        path=args.file,
        model_id=args.model_id,
        source_url=source_url,
        expected_hosts=row.get("expected_hosts", []),
        expected_model_kind=str(row["model_kind"]),
        filename=args.file.name,
        expected_sha256=args.expected_sha256,
        max_bytes=args.max_bytes,
    )
    manifest["registry_landing_url"] = row.get("landing_url")
    manifest["registry_download_url"] = row.get("download_url")
    manifest["registry_advertised_artifact"] = row.get("advertised_artifact")

    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "model_id": manifest["model_id"],
        "capture_status": manifest["capture_status"],
        "sha256": manifest["sha256"],
        "size_bytes": manifest["size_bytes"],
        "recognized_expected_model_file_count": manifest["recognized_expected_model_file_count"],
        "manifest_out": str(args.manifest_out),
        "raw_model_bytes_published": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
