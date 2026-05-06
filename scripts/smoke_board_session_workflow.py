#!/usr/bin/env python3
"""Smoke-test the live board-session workflow against a running API."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import requests


def _post_json(base_url: str, path: str, api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a live board-session smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010", help="Circuit-AI API base URL")
    parser.add_argument("--api-key", default="dev", help="Bearer API key")
    parser.add_argument("--image", default="assets/samples/test_pcb.png", help="primary board scan")
    parser.add_argument("--evidence", default="tests/data/defect_samples/corrosion.jpg", help="follow-up evidence image")
    parser.add_argument("--backend", default="hybrid", help="detector backend")
    parser.add_argument("--description", default="USB fan board from a salvage pile; warms but motor will not spin consistently.")
    parser.add_argument("--device-hint", default="USB fan controller board")
    parser.add_argument("--symptoms", default="warm board; intermittent motor; no spin unless wire is wiggled")
    parser.add_argument("--no-export", action="store_true", help="skip training package export")
    args = parser.parse_args()

    image = Path(args.image)
    evidence = Path(args.evidence)
    headers = {"Authorization": f"Bearer {args.api_key}"}

    with image.open("rb") as handle:
        response = requests.post(
            f"{args.base_url}/board-sessions/from-scan",
            headers=headers,
            files={"file": (image.name, handle, "image/png")},
            data={
                "description": args.description,
                "device_hint": args.device_hint,
                "symptoms": args.symptoms,
                "backend": args.backend,
                "enable_ocr": "true",
                "commit": "true",
            },
            timeout=120,
        )
    response.raise_for_status()
    session = response.json()["session"]
    session_id = session["session_id"]
    print(f"session={session_id} route={session['route']} metrics={session['metrics']}")

    if evidence.exists():
        with evidence.open("rb") as handle:
            response = requests.post(
                f"{args.base_url}/board-sessions/{session_id}/captures",
                headers=headers,
                files={"file": (evidence.name, handle, "image/jpeg")},
                data={"kind": "connector_closeup", "notes": "operator follow-up evidence"},
                timeout=60,
            )
        response.raise_for_status()
        print(f"capture={response.json()['result']['capture']['capture_id']}")

    measurement = _post_json(
        args.base_url,
        f"/board-sessions/{session_id}/measurement",
        args.api_key,
        {"type": "continuity", "target": "ground to connector ground", "value": "pass", "unit": ""},
    )
    print(f"measurement={measurement['result']['measurement']['measurement_id']}")

    queue = requests.get(
        f"{args.base_url}/board-sessions/review-queue",
        headers=headers,
        timeout=30,
    )
    queue.raise_for_status()
    task = next(item for item in queue.json()["tasks"] if item["session_id"] == session_id)
    review = _post_json(
        args.base_url,
        f"/board-sessions/{session_id}/review",
        args.api_key,
        {"task_id": task["task_id"], "action": "accepted", "notes": "smoke reviewed"},
    )
    print(f"review={review['result']['review']['review_id']} task={task['task_id']}")

    outcome = _post_json(
        args.base_url,
        f"/board-sessions/{session_id}/outcome",
        args.api_key,
        {"decision": "salvaged", "value_recovered_usd": 9.5, "time_saved_minutes": 14},
    )
    print(f"outcome={outcome['result']['outcome']['outcome_id']}")

    if not args.no_export:
        response = requests.post(
            f"{args.base_url}/board-sessions/{session_id}/training-export",
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        export = response.json()["result"]["training_export"]
        print(f"export={export['path']} counts={export['counts']}")

    benchmark = requests.get(f"{args.base_url}/board-sessions/benchmark", headers=headers, timeout=30)
    benchmark.raise_for_status()
    print(f"benchmark={benchmark.json()['benchmark']['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
