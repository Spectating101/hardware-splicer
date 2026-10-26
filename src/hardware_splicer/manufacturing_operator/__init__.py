"""Constrained desktop manufacturing operator adapters.

Agent tools should expose read/prepare/status/monitor only. Direct machine
commands and credential configuration belong to a separate local operator UI.
"""
from .cad_pipeline import render_openscad, slice_prusaslicer, ToolpathReceipt
from .octoprint import ManufacturingRefusal, OctoPrintOperator, StagedPrintReceipt

__all__ = ["ManufacturingRefusal", "OctoPrintOperator", "StagedPrintReceipt", "ToolpathReceipt", "render_openscad", "slice_prusaslicer"]
