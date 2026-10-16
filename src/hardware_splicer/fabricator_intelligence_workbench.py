"""Bounded agent facade for fabricator inspection and procurement intelligence."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .fabrication_operator import FabricationValidationError
from .procurement_quotes import ProcurementQuoteBook
from .vision_inspection import VisionInspectionService


class FabricatorIntelligenceWorkbench:
    def __init__(
        self,
        *,
        vision: VisionInspectionService | None = None,
        procurement: ProcurementQuoteBook | None = None,
    ) -> None:
        self.vision = vision
        self.procurement = procurement or ProcurementQuoteBook()

    def inspect_image(
        self,
        *,
        observation_id: str,
        task_id: str,
        output_artifact_id: str,
    ) -> dict[str, Any]:
        if self.vision is None:
            raise FabricationValidationError("vision inspection integration is not configured")
        return self.vision.inspect(
            observation_id=observation_id,
            task_id=task_id,
            output_artifact_id=output_artifact_id,
        )

    def list_quotes(
        self,
        *,
        part_key: str | None = None,
        supplier_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.procurement.list_public(part_key=part_key, supplier_id=supplier_id)

    def cost_bom(
        self,
        *,
        lines: Sequence[Mapping[str, Any]],
        currency: str,
        as_of: str | None = None,
        require_known_stock: bool = False,
    ) -> dict[str, Any]:
        return self.procurement.cost_bom(
            lines=lines,
            currency=currency,
            as_of=as_of,
            require_known_stock=require_known_stock,
        )
