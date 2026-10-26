"""HS local manufacturing adapters and vendor-neutral capability routing.

No auto-start of machine jobs or unrestricted motion commands are exposed.
"""
from .cad_pipeline import render_openscad, slice_prusaslicer, ToolpathReceipt
from .octoprint import ManufacturingRefusal, OctoPrintOperator, StagedPrintReceipt
from .moonraker import MoonrakerDriver
from .fleet import (MachineCapabilities, MachineObservation, ManufacturingRequest,
                    ManufacturingPlan, ManufacturingFleet, OctoPrintDriver)
from .discovery import connect_enrolled_controller

__all__ = [
    "ManufacturingRefusal", "OctoPrintOperator", "StagedPrintReceipt",
    "ToolpathReceipt", "render_openscad", "slice_prusaslicer",
    "MoonrakerDriver", "OctoPrintDriver", "MachineCapabilities",
    "MachineObservation", "ManufacturingRequest", "ManufacturingPlan",
    "ManufacturingFleet", "connect_enrolled_controller",
]
