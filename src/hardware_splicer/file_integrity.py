"""File digests for on-disk engineering artifacts."""

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()
