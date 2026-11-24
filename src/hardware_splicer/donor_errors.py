"""Validation error shared by the donor intake and salvage resource modules."""

from __future__ import annotations


class DonorValidationError(ValueError):
    """Donor, capture or artifact input was rejected before anything was recorded."""
