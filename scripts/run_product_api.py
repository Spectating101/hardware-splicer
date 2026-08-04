#!/usr/bin/env python3
"""Run the canonical Hardware Splicer product API on its dedicated port."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.getenv("HARDWARE_SPLICER_API_HOST", "127.0.0.1")
    port = int(os.getenv("HARDWARE_SPLICER_API_PORT", "8090"))
    reload_enabled = os.getenv("HARDWARE_SPLICER_API_RELOAD", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    uvicorn.run(
        "hardware_splicer.product_api:app",
        host=host,
        port=port,
        reload=reload_enabled,
        access_log=True,
    )


if __name__ == "__main__":
    main()
