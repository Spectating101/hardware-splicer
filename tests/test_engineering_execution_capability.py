from __future__ import annotations

from hardware_splicer.engineering_execution_capability import build_engineering_execution_capability


def test_capability_report_distinguishes_adapters_tools_and_host_policy(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EXECUTION_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_EXECUTION_ENABLED", raising=False)
    monkeypatch.setattr(
        "hardware_splicer.engineering_execution_capability.shutil.which",
        lambda tool: "/usr/bin/ngspice" if tool == "ngspice" else None,
    )

    report = build_engineering_execution_capability()
    by_operation = {row.operation.value: row for row in report.operations}

    assert report.execution_root == str(tmp_path.resolve())
    assert report.execution_enabled is False
    assert by_operation["artifact_hash"].tool_installed is True
    assert by_operation["python_compile"].tool_installed is True
    assert by_operation["ngspice"].tool_installed is True
    assert by_operation["kicad_erc"].tool_installed is False
    assert all(row.preview_available is True for row in report.operations)
    assert all(row.executable_under_host_policy is False for row in report.operations)
    assert all(row.physical_operation is False for row in report.operations)
    assert report.metadata["network_authorized"] is False
    assert report.metadata["network_isolation_enforced"] is False
    assert report.metadata["device_access_authorized"] is False
    assert "firmware_flash" in report.prohibited_operations
    assert "robot_motion" in report.prohibited_operations


def test_enabled_host_only_exposes_installed_operations(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EXECUTION_ROOT", str(tmp_path))
    monkeypatch.setenv("HARDWARE_SPLICER_EXECUTION_ENABLED", "1")
    monkeypatch.setattr(
        "hardware_splicer.engineering_execution_capability.shutil.which",
        lambda tool: f"/opt/tools/{tool}" if tool in {"kicad-cli", "pio"} else None,
    )

    report = build_engineering_execution_capability()
    by_operation = {row.operation.value: row for row in report.operations}

    assert by_operation["artifact_hash"].executable_under_host_policy is True
    assert by_operation["python_compile"].executable_under_host_policy is True
    assert by_operation["kicad_erc"].executable_under_host_policy is True
    assert by_operation["kicad_drc"].executable_under_host_policy is True
    assert by_operation["platformio_build"].executable_under_host_policy is True
    assert by_operation["ngspice"].executable_under_host_policy is False
    assert report.metadata["executable_operation_count"] == 5
