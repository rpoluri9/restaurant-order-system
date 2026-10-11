"""Customer-care endpoints: delayed orders, polite delay notices, responses."""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_db
from ...core.config import settings
from ...db.db import Database
from ...schemas.care import NotifyIn, RespondIn
from ...services.notify import CUSTOMER_RESPONSES, build_delay_message
from ...services.orders import OrderError, delayed_orders, get_order_detail

router = APIRouter(prefix="/customer-care", tags=["customer-care"])


@router.get("/delayed")
def list_delayed(db: Database = Depends(get_db)):
    """Orders currently delayed, most overdue first."""
    return delayed_orders(db, threshold=settings.delay_threshold_minutes)


@router.post("/{order_id}/notify", status_code=201)
def notify_customer(order_id: int, body: NotifyIn, db: Database = Depends(get_db)):
    """Send the polite delay message and store it on the order."""
    try:
        order = get_order_detail(db, order_id)
    except OrderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    if order["status"] in ("COMPLETED", "CANCELLED"):
        raise HTTPException(
            status_code=400, detail="order is already finished; nothing to notify"
        )
    message = build_delay_message(custom=body.message)
    notice_id = db.create_delay_notice(order_id, message, sent_by="CUSTOMER_CARE")
    return db.get_notice(notice_id)


@router.post("/{order_id}/respond")
def record_response(order_id: int, body: RespondIn, db: Database = Depends(get_db)):
    """Record how the customer answered the delay notice."""
    if body.response not in CUSTOMER_RESPONSES:
        raise HTTPException(status_code=422, detail="invalid customer response")
    notice = db.latest_notice(order_id)
    if not notice:
        raise HTTPException(
            status_code=404, detail="no delay notice sent for this order yet"
        )
    return db.record_customer_response(notice["id"], body.response)
