"""Pydantic schemas for menu items."""
from pydantic import BaseModel, Field


class MenuItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price_cents: int = Field(ge=0, description="Price in cents, e.g. 1299 = $12.99")
    expected_prep_minutes: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=50)
    is_available: bool = True


class MenuItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    price_cents: int | None = Field(default=None, ge=0)
    expected_prep_minutes: int | None = Field(default=None, gt=0)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    is_available: bool | None = None
