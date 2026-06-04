from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
