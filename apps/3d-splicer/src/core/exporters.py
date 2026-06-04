from pathlib import Path

def ensure_dirs() -> None:
    """Ensure output directories exist."""
    Path("stl").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
