#!/usr/bin/env python3
"""Run the zero-Astra Derived Virtual Lab v1 SPI benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
src_root = str(SRC_ROOT)
while src_root in sys.path:
    sys.path.remove(src_root)
sys.path.insert(0, src_root)

from hardware_splicer.spi_derived_lab_source_manifest import (  # noqa: E402
    build_derived_lab_source_manifest,
)
from hardware_splicer.spi_derived_virtual_lab import (  # noqa: E402
    generate_derived_surrogate_corpus,
    run_derived_virtual_lab_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-out", type=Path, help="Optional path for the benchmark JSON report.")
    parser.add_argument("--corpus-out", type=Path, help="Optional path for the frozen 512-case corpus JSON.")
    parser.add_argument("--source-manifest-out", type=Path, help="Optional path for the canonical-input source manifest.")
    args = parser.parse_args()

    report = run_derived_virtual_lab_benchmark()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")

    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(rendered, encoding="utf-8")
    if args.corpus_out:
        args.corpus_out.parent.mkdir(parents=True, exist_ok=True)
        args.corpus_out.write_text(
            json.dumps(generate_derived_surrogate_corpus(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.source_manifest_out:
        args.source_manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.source_manifest_out.write_text(
            json.dumps(build_derived_lab_source_manifest(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return 0 if report["benchmark_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
