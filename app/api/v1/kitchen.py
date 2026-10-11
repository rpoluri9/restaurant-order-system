"""Kitchen endpoints: the queue of orders to prepare, and kitchen actions."""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_db
from ...db.db import Database
from ...services.orders import OrderError, advance_order, kitchen_queue

router = APIRouter(prefix="/kitchen", tags=["kitchen"])


@router.get("/queue")
def get_queue(db: Database = Depends(get_db)):
    """Orders waiting for the kitchen: KITCHEN_RECEIVED + PREPARING, oldest first."""
    return kitchen_queue(db)


@router.post("/{order_id}/start-preparing")
def start_preparing(order_id: int, db: Database = Depends(get_db)):
    try:
        return advance_order(db, order_id, "PREPARING", actor_role="KITCHEN")
    except OrderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/{order_id}/mark-ready")
def mark_ready(order_id: int, db: Database = Depends(get_db)):
    try:
        return advance_order(db, order_id, "READY", actor_role="KITCHEN")
    except OrderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
