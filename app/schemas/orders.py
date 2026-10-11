"""Pydantic schemas for orders."""
from pydantic import BaseModel, Field


class OrderItemIn(BaseModel):
    menu_item_id: int
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    table_id: int
    customer_name: str = Field(min_length=1, max_length=100)
    customer_phone: str | None = Field(default=None, max_length=20)
    items: list[OrderItemIn] = Field(min_length=1)
    actor_role: str = "WAITER"


class AdvanceIn(BaseModel):
    to_status: str
    actor_role: str = "SYSTEM"
