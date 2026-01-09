import sys
from pathlib import Path


# Make `import src.*` work when running `pytest` without installing the package.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

