from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


class Splicer3DClient:
    """
    Thin client for the sibling `3d-splicer` API.
    Used for PCB-style enclosures (CadQuery script / STL).
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("SPLICER_API_URL") or "http://127.0.0.1:8000").rstrip("/")

    def splice_script(self, payload: Dict[str, Any], *, timeout_s: float = 30.0) -> Dict[str, Any]:
        r = httpx.post(f"{self.base_url}/v1/splice/script", json=payload, timeout=timeout_s)
        r.raise_for_status()
        return r.json()

    def splice_stl(self, payload: Dict[str, Any], *, timeout_s: float = 120.0) -> Dict[str, Any]:
        r = httpx.post(f"{self.base_url}/v1/splice", json=payload, timeout=timeout_s)
        r.raise_for_status()
        return r.json()

