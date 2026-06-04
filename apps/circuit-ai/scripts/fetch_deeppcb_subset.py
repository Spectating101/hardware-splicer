#!/usr/bin/env python3
"""Download a bounded DeepPCB subset for golden-reference AOI evaluation."""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RAW_BASE = "https://raw.githubusercontent.com/tangsanli5201/DeepPCB/master/PCBData"
CLASS_NAMES = {
    1: "open",
    2: "short",
    3: "mousebite",
    4: "spur",
    5: "copper",
    6: "pin_hole",
}


def _read_split(split: str) -> list[str]:
    url = f"{RAW_BASE}/{split}.txt"
    with urllib.request.urlopen(url, timeout=30) as response:
        return [line.strip() for line in response.read().decode("utf-8").splitlines() if line.strip()]


def _urlretrieve(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(path)


def _entry_to_files(entry: str) -> tuple[str, str, str]:
    image_rel, label_rel = entry.split()
    stem = Path(image_rel).stem
    parent = str(Path(image_rel).parent)
    test_rel = f"{parent}/{stem}_test.jpg"
    temp_rel = f"{parent}/{stem}_temp.jpg"
    return temp_rel, test_rel, label_rel


def _parse_label(path: Path) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        x1, y1, x2, y2, cls_id = [int(value) for value in parts]
        annotations.append(
            {
                "bbox": [x1, y1, x2, y2],
                "class_id": cls_id,
                "class_name": CLASS_NAMES.get(cls_id, f"class_{cls_id}"),
            }
        )
    return annotations


def fetch_subset(split: str, limit: int, output_dir: Path) -> dict[str, Any]:
    entries = _read_split(split)[:limit]
    samples: list[dict[str, Any]] = []

    for index, entry in enumerate(entries):
        temp_rel, test_rel, label_rel = _entry_to_files(entry)
        sample_id = Path(label_rel).stem
        template_path = output_dir / "templates" / f"{sample_id}_temp.jpg"
        test_path = output_dir / "images" / f"{sample_id}_test.jpg"
        label_path = output_dir / "labels" / f"{sample_id}.txt"
        _urlretrieve(f"{RAW_BASE}/{temp_rel}", template_path)
        _urlretrieve(f"{RAW_BASE}/{test_rel}", test_path)
        _urlretrieve(f"{RAW_BASE}/{label_rel}", label_path)
        samples.append(
            {
                "sample_id": sample_id,
                "template": str(template_path),
                "image": str(test_path),
                "label": str(label_path),
                "annotations": _parse_label(label_path),
                "source": {
                    "template": temp_rel,
                    "image": test_rel,
                    "label": label_rel,
                    "split": split,
                    "index": index,
                },
            }
        )

    manifest = {
        "dataset_id": "deeppcb_subset",
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "source": {
            "repository": "https://github.com/tangsanli5201/DeepPCB",
            "raw_base": RAW_BASE,
            "split": split,
        },
        "class_names": CLASS_NAMES,
        "samples": samples,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a bounded DeepPCB subset")
    parser.add_argument("--split", choices=["trainval", "test"], default="test")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--output-dir", default="datasets/deeppcb_subset")
    args = parser.parse_args()

    manifest = fetch_subset(args.split, args.limit, Path(args.output_dir))
    print(f"wrote {Path(args.output_dir) / 'manifest.json'}")
    print(f"samples={len(manifest['samples'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
