"""Order endpoints: take orders, track them, advance the state machine."""
from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_db
from ...db.db import Database
from ...schemas.orders import AdvanceIn, OrderCreate
from ...services.orders import (
    STATUSES,
    OrderError,
    advance_order,
    cancel_order,
    get_order_detail,
    place_order,
)
from ...services.billing import calculate_bill

router = APIRouter(prefix="/orders", tags=["orders"])


def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except OrderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("", status_code=201)
def create_order(body: OrderCreate, db: Database = Depends(get_db)):
    return _handle(
        place_order,
        db,
        table_id=body.table_id,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        items=[i.model_dump() for i in body.items],
        actor_role=body.actor_role,
    )


@router.get("")
def list_orders(
    status: str | None = Query(default=None),
    db: Database = Depends(get_db),
):
    if status and status not in STATUSES:
        raise HTTPException(status_code=400, detail="invalid status filter")
    orders = db.list_orders(status=status)
    for order in orders:
        order["items"] = db.list_order_items(order["id"])
    return orders


@router.get("/{order_id}")
def get_order(order_id: int, db: Database = Depends(get_db)):
    return _handle(get_order_detail, db, order_id)


@router.post("/{order_id}/advance")
def advance(order_id: int, body: AdvanceIn, db: Database = Depends(get_db)):
    return _handle(
        advance_order, db, order_id, body.to_status, actor_role=body.actor_role
    )


@router.post("/{order_id}/cancel")
def cancel(order_id: int, db: Database = Depends(get_db)):
    return _handle(cancel_order, db, order_id)


@router.get("/{order_id}/bill")
def get_bill(order_id: int, db: Database = Depends(get_db)):
    """Bill breakdown: subtotal, 25% family discount above $200,
    GST 10% + state tax 6% + sales tax 4%, and the grand total."""
    return _handle(calculate_bill, db, order_id)
