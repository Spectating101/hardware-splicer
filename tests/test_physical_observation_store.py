from __future__ import annotations

import json

import pytest

from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.physical_observation_store import PhysicalObservationStore


def test_store_retains_exact_bytes_and_keeps_truth_unproven(tmp_path):
    store = PhysicalObservationStore(tmp_path / "observations")
    payload = b"raw-frame-bytes"
    record = store.put(
        kind="image",
        source_id="camera-bench-a",
        media_type="image/jpeg",
        data=payload,
        metadata={"width": 640, "height": 480},
    )
    assert record.physical_correctness == "UNPROVEN"
    assert record.size_bytes == len(payload)
    assert store.read_bytes(record.observation_id) == payload
    loaded = store.describe(record.observation_id)
    assert loaded.sha256 == record.sha256
    assert loaded.metadata == {"width": 640, "height": 480}


def test_public_listing_never_exposes_payload_bytes(tmp_path):
    store = PhysicalObservationStore(tmp_path / "observations")
    record = store.put(
        kind="serial_log",
        source_id="dut-uart-0",
        media_type="text/plain",
        data=b"boot ok\n",
    )
    listed = store.list_public()
    assert listed == [record.public_dict()]
    assert "payload" not in listed[0]
    assert "data" not in listed[0]


def test_metadata_cannot_smuggle_physical_authority(tmp_path):
    store = PhysicalObservationStore(tmp_path / "observations")
    for metadata in (
        {"physical_correctness": "PROVEN"},
        {"nested": {"authorized": True}},
        {"fabrication_authorized": True},
        {"passed": True},
    ):
        with pytest.raises(FabricationValidationError, match="authority"):
            store.put(
                kind="machine_telemetry",
                source_id="machine-1",
                media_type="application/json",
                data=b"{}",
                metadata=metadata,
            )


def test_tampered_payload_is_detected(tmp_path):
    store = PhysicalObservationStore(tmp_path / "observations")
    record = store.put(
        kind="instrument_trace",
        source_id="scope-1",
        media_type="application/octet-stream",
        data=b"trace-v1",
    )
    payload_path = tmp_path / "observations" / record.observation_id / "payload.bin"
    payload_path.write_bytes(b"trace-v2")
    with pytest.raises(FabricationValidationError, match="no longer matches"):
        store.describe(record.observation_id)


def test_rejects_path_traversal_and_oversized_payload(tmp_path):
    store = PhysicalObservationStore(tmp_path / "observations", max_bytes=4)
    with pytest.raises(FabricationValidationError, match="invalid"):
        store.describe("../escape")
    with pytest.raises(FabricationValidationError, match="size limit"):
        store.put(
            kind="other",
            source_id="fixture",
            media_type="application/octet-stream",
            data=b"12345",
        )


def test_record_file_is_metadata_only_and_canonical_json(tmp_path):
    store = PhysicalObservationStore(tmp_path / "observations")
    record = store.put(
        kind="image",
        source_id="cam",
        media_type="image/png",
        data=b"png-placeholder",
        metadata={"z": 1, "a": [2, 3]},
    )
    path = tmp_path / "observations" / record.observation_id / "record.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value["physical_correctness"] == "UNPROVEN"
    assert value["metadata"] == {"a": [2, 3], "z": 1}
