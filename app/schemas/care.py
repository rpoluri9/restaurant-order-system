"""Pydantic schemas for customer-care interactions."""
from typing import Literal

from pydantic import BaseModel, Field

CustomerResponse = Literal["WAITING", "CANCELLED_ORDER", "ESCALATED", "NO_RESPONSE"]


class NotifyIn(BaseModel):
    message: str | None = Field(
        default=None,
        description="Custom message; defaults to the polite delay template.",
    )


class RespondIn(BaseModel):
    response: CustomerResponse
