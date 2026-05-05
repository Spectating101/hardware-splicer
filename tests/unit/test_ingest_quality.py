from src.core.ingest import CircuitAnalyzer


def test_confidence_band_is_stratified():
    analyzer = CircuitAnalyzer()

    assert analyzer._confidence_band(0.92) == "high"
    assert analyzer._confidence_band(0.64) == "medium"
    assert analyzer._confidence_band(0.39) == "low"
