from __future__ import annotations

import io

import httpx
import pytest
from PIL import Image

from hardware_splicer.camera_observer import (
    CameraCaptureError,
    CameraObservationHandle,
    HttpSnapshotSource,
)
from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.physical_dispatch import PhysicalDispatcher
from hardware_splicer.physical_authority import PhysicalPlanGrantStore
from hardware_splicer.physical_observation_store import PhysicalObservationStore
from hardware_splicer.physical_operator import PhysicalOperatorRegistry
from hardware_splicer.physical_presets import camera_observer_descriptor


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 6), (20, 30, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


def _runtime(tmp_path, *, response: httpx.Response | None = None):
    payload = _png_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("http://camera.test/snapshot")
        return response or httpx.Response(200, content=payload, headers={"content-type": "image/png"})

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    source = HttpSnapshotSource(
        source_id="bench-cam-a",
        url="http://camera.test/snapshot",
        client=client,
    )
    observations = PhysicalObservationStore(tmp_path / "observations")
    handle = CameraObservationHandle(
        operator_id="camera-a",
        source=source,
        observations=observations,
    )
    operators = PhysicalOperatorRegistry()
    operators.register(
        camera_observer_descriptor(operator_id="camera-a", display_name="Bench Camera A"),
        handle,
    )
    dispatcher = PhysicalDispatcher(
        registry=operators,
        grants=PhysicalPlanGrantStore(tmp_path / "grants"),
    )
    return payload, client, observations, operators, dispatcher


def test_camera_capture_is_observation_only_and_retains_exact_frame(tmp_path):
    payload, client, observations, operators, dispatcher = _runtime(tmp_path)
    plan = operators.plan(
        operator_id="camera-a",
        project_id="project-a",
        mission_id="mission-a",
        action="capture",
        payload={},
    )
    receipt = dispatcher.dispatch(plan)
    assert receipt["authority"] == "not_required"
    result = receipt["result"]
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["interpretation_performed"] is False
    observation = result["observation"]
    assert observation["metadata"]["width"] == 8
    assert observation["metadata"]["height"] == 6
    assert observation["metadata"]["format"] == "PNG"
    assert observations.read_bytes(observation["observation_id"]) == payload
    client.close()


def test_camera_status_does_not_capture_or_claim_correctness(tmp_path):
    _payload, client, observations, operators, dispatcher = _runtime(tmp_path)
    plan = operators.plan(
        operator_id="camera-a",
        project_id="project-a",
        mission_id="mission-a",
        action="status",
        payload={},
    )
    receipt = dispatcher.dispatch(plan)
    assert receipt["result"]["available"] is True
    assert receipt["result"]["physical_correctness"] == "UNPROVEN"
    assert observations.list_public() == []
    client.close()


def test_camera_rejects_mismatched_media_type(tmp_path):
    payload = _png_bytes()
    response = httpx.Response(200, content=payload, headers={"content-type": "image/jpeg"})
    _payload, client, _observations, operators, dispatcher = _runtime(tmp_path, response=response)
    plan = operators.plan(
        operator_id="camera-a",
        project_id="project-a",
        mission_id="mission-a",
        action="capture",
        payload={},
    )
    with pytest.raises(CameraCaptureError, match="does not match"):
        dispatcher.dispatch(plan)
    client.close()


def test_camera_rejects_redirect_and_arbitrary_bad_url_configuration(tmp_path):
    with pytest.raises(FabricationValidationError, match="credentials"):
        HttpSnapshotSource(
            source_id="cam",
            url="http://user:pass@camera.test/snapshot",
        )

    response = httpx.Response(302, headers={"location": "http://other.test/frame"})
    _payload, client, _observations, operators, dispatcher = _runtime(tmp_path, response=response)
    plan = operators.plan(
        operator_id="camera-a",
        project_id="project-a",
        mission_id="mission-a",
        action="capture",
        payload={},
    )
    with pytest.raises(CameraCaptureError, match="request failed"):
        dispatcher.dispatch(plan)
    client.close()
