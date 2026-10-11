"""Dashboard statistics endpoints."""
from fastapi import APIRouter, Depends

from ..deps import get_db
from ...core.config import settings
from ...db.db import Database
from ...services.orders import _minutes_between, delayed_orders

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
def stats(db: Database = Depends(get_db)):
    by_status_rows = db.count_orders_by_status()
    by_status = {row["status"]: row["count"] for row in by_status_rows}

    durations = [
        _minutes_between(r["preparing_started_at"], r["ready_at"])
        for r in db.prep_durations()
    ]
    avg_prep = round(sum(durations) / len(durations), 1) if durations else None

    delayed = delayed_orders(db, threshold=settings.delay_threshold_minutes)

    return {
        "orders_by_status": by_status,
        "total_orders": sum(by_status.values()),
        "avg_prep_minutes": avg_prep,
        "delayed_count": len(delayed),
        "delayed_order_ids": [o["id"] for o in delayed],
        "revenue_cents": db.revenue_cents(),
    }
