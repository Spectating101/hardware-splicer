#!/usr/bin/env python3
"""Local HS printer status/monitor/upload entry point. Does NOT start printing.

Requires HS_OCTOPRINT_URL and HS_OCTOPRINT_API_KEY set locally.
Printer uploads are disabled by default and require local TTY confirmation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from hardware_splicer.manufacturing_operator import ManufacturingRefusal, OctoPrintOperator


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true")
    group.add_argument("--job", action="store_true")
    group.add_argument("--stage", type=Path, metavar="FILE.gcode")
    args = ap.parse_args()
    url = os.environ.get("HS_OCTOPRINT_URL", "")
    key = os.environ.get("HS_OCTOPRINT_API_KEY", "")
    if not url or not key:
        ap.error("Configure HS_OCTOPRINT_URL and HS_OCTOPRINT_API_KEY locally")
    allow_upload = False
    if args.stage is not None:
        if not sys.stdin.isatty():
            ap.error("Upload requires a local interactive terminal; no unattended agent upload")
        print("Check printer is physically clear and idle. Review installed plugins:")
        print("Some plugins START PRINTING IMMEDIATELY when a G-code file is uploaded.")
        print("Type REVIEWED only if you have checked this printer cannot auto-start on upload.")
        allow_upload = input("Local operator confirmation: ").strip() == "REVIEWED"
        if not allow_upload:
            ap.error("Upload not authorized")
    try:
        with OctoPrintOperator(base_url=url, api_key=key,
                upload_enabled_by_local_operator=allow_upload,
                auto_start_plugins_checked=allow_upload) as printer:
            if args.status:
                result = printer.printer_status()
            elif args.job:
                result = printer.current_job()
            else:
                result = printer.stage_gcode(args.stage).to_dict()
    except (ManufacturingRefusal, OSError, ValueError) as exc:
        print(f"HS manufacturing operation refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
