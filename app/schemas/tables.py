"""Pydantic schemas for restaurant tables."""
from pydantic import BaseModel, Field


class TableCreate(BaseModel):
    table_number: int = Field(gt=0)
    seats: int = Field(gt=0)
    status: str = "AVAILABLE"


class TableUpdate(BaseModel):
    table_number: int | None = Field(default=None, gt=0)
    seats: int | None = Field(default=None, gt=0)
    status: str | None = None
