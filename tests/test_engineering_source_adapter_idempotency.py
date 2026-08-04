from __future__ import annotations

from hardware_splicer.engineering_source_adapters import adapt_engineering_sources


def test_graph_ready_measurement_claims_pass_through_unchanged() -> None:
    source = {
        "source_id": "measured-rail",
        "source_type": "measurement",
        "revision": "capture-7",
        "content_hash": "sha256:abc",
        "authority_ceiling": "measured",
        "claims": [
            {
                "claim_id": "rail-minimum",
                "subject_id": "power-system",
                "predicate": "minimum_voltage_v",
                "value": 4.88,
                "units": "V",
                "authority": "measured",
            }
        ],
        "metadata": {"instrument_id": "scope-a"},
    }

    bundle = adapt_engineering_sources([source])

    assert bundle.unresolved == []
    assert bundle.robot_models == {}
    assert bundle.sources == [source]
    assert bundle.sources[0]["claims"][0]["claim_id"] == "rail-minimum"


def test_graph_ready_telemetry_claims_do_not_become_empty_raw_manifest() -> None:
    source = {
        "source_id": "run-18",
        "source_type": "telemetry",
        "revision": "run-18",
        "claims": [
            {
                "subject_id": "robot-base",
                "predicate": "peak_pitch_deg",
                "value": 18.2,
                "authority": "measured",
            }
        ],
    }

    bundle = adapt_engineering_sources([source])

    assert len(bundle.sources[0]["claims"]) == 1
    assert bundle.sources[0]["claims"][0]["predicate"] == "peak_pitch_deg"
