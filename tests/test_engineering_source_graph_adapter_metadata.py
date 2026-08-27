from __future__ import annotations

from hardware_splicer.engineering_source_adapters import adapt_engineering_sources
from hardware_splicer.engineering_source_graph import build_engineering_source_graph


def test_firmware_and_middleware_metadata_remain_graph_visible() -> None:
    bundle = adapt_engineering_sources(
        [
            {
                "source_id": "firmware-build",
                "artifact_kind": "firmware_manifest",
                "manifest": {
                    "firmware_component_id": "main-controller",
                    "source_revision": "commit-123",
                    "toolchain": "platformio",
                    "build_command": "pio run",
                    "binary_hash": "sha256:binary",
                    "flash_result": "success",
                },
            },
            {
                "source_id": "ros-contract",
                "artifact_kind": "ros_interface_manifest",
                "manifest": {
                    "node_id": "rover-node",
                    "distribution": "jazzy",
                    "topics": [{"name": "/cmd_vel", "type": "geometry_msgs/msg/Twist"}],
                    "frames": ["base_link"],
                },
            },
        ]
    )

    graph = build_engineering_source_graph(bundle.sources)
    by_id = {row.source_id: row for row in graph.sources}

    firmware = by_id["firmware-build"]
    middleware = by_id["ros-contract"]
    assert firmware.metadata["artifact_kind"] == "firmware_manifest"
    assert firmware.metadata["firmware_manifest"]["firmware_component_id"] == "main-controller"
    assert middleware.metadata["artifact_kind"] == "ros_interface_manifest"
    assert middleware.metadata["ros_interface_manifest"]["node_id"] == "rover-node"

    # Adapter projection only changes representation. It cannot elevate evidence.
    assert firmware.authority_ceiling.value == "declared"
    assert middleware.authority_ceiling.value == "declared"
