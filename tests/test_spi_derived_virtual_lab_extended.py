from pathlib import Path

from hardware_splicer.spi_derived_verilog_runner import run_derived_verilog_oracle
from hardware_splicer.spi_surrogate_sensitivity import run_sensitivity_sweep


def test_sensitivity_sweep_is_large_and_authority_bounded() -> None:
    result = run_sensitivity_sweep()
    assert result["case_count"] == 6 * 5 * 4 * 4 * 4
    assert result["pass_count"] > 0
    assert result["fail_count"] > 0
    assert set(result["by_clock_hz"]) == {
        "1000000", "5000000", "10000000", "15000000", "20000000", "25000000"
    }
    assert result["eligible_for_vendor_model_campaign_credit"] is False
    assert result["physical_correctness"] == "UNPROVEN"


def test_optional_verilog_runner_never_promotes_authority(monkeypatch) -> None:
    import hardware_splicer.spi_derived_verilog_runner as runner

    monkeypatch.setattr(runner.shutil, "which", lambda _: None)
    repo_root = Path(__file__).resolve().parents[1]
    result = run_derived_verilog_oracle(repo_root=repo_root)
    assert result["status"] == "tool_unavailable"
    assert result["eligible_for_vendor_model_campaign_credit"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False
