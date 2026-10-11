"""Order business logic: the strict order state machine and delay detection.

State machine::

    PLACED -> KITCHEN_RECEIVED -> PREPARING -> READY -> SERVED -> COMPLETED
       |            |                |           |         |
       +------------+----------------+-----------+---------+--> CANCELLED
"""
from datetime import datetime

from ..db.db import Database, utcnow_iso

STATUSES = [
    "PLACED",
    "KITCHEN_RECEIVED",
    "PREPARING",
    "READY",
    "SERVED",
    "COMPLETED",
    "CANCELLED",
]

FINAL_STATUSES = {"COMPLETED", "CANCELLED"}

VALID_TRANSITIONS: dict[str, set[str]] = {
    "PLACED": {"KITCHEN_RECEIVED", "CANCELLED"},
    "KITCHEN_RECEIVED": {"PREPARING", "CANCELLED"},
    "PREPARING": {"READY", "CANCELLED"},
    "READY": {"SERVED", "CANCELLED"},
    "SERVED": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}

ACTOR_ROLES = {"WAITER", "KITCHEN", "CUSTOMER_CARE", "SYSTEM"}


class OrderError(Exception):
    """Domain error carrying an HTTP status code and message."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in VALID_TRANSITIONS.get(from_status, set())


def _minutes_between(start_iso: str, end_iso: str) -> float:
    fmt = "%Y-%m-%d %H:%M:%S"
    return (
        datetime.strptime(end_iso, fmt) - datetime.strptime(start_iso, fmt)
    ).total_seconds() / 60


def place_order(
    db: Database,
    table_id: int,
    customer_name: str,
    customer_phone: str | None,
    items: list[dict],
    actor_role: str = "WAITER",
) -> dict:
    """Waiter takes an order: validate, price it, create it, occupy the table."""
    table = db.get_table(table_id)
    if not table:
        raise OrderError(f"table id {table_id} not found", 404)
    if not items:
        raise OrderError("order must contain at least one item", 400)

    lines = []
    total_cents = 0
    for entry in items:
        menu_item = db.get_menu_item(entry["menu_item_id"])
        if not menu_item:
            raise OrderError(
                f"menu item id {entry['menu_item_id']} not found", 404
            )
        if not menu_item["is_available"]:
            raise OrderError(
                f"menu item '{menu_item['name']}' is not available", 400
            )
        qty = int(entry["quantity"])
        if qty <= 0:
            raise OrderError("quantity must be positive", 400)
        lines.append(
            {
                "menu_item_id": menu_item["id"],
                "quantity": qty,
                "price_cents": menu_item["price_cents"],
                "expected_prep_minutes": menu_item["expected_prep_minutes"],
            }
        )
        total_cents += menu_item["price_cents"] * qty

    order_id = db.create_order(
        table_id=table_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        total_cents=total_cents,
        created_by_role=actor_role,
    )
    for line in lines:
        db.create_order_item(order_id, **line)
    db.update_table(table_id, {"status": "OCCUPIED"})
    return get_order_detail(db, order_id)


def get_order_detail(db: Database, order_id: int) -> dict:
    order = db.get_order(order_id)
    if not order:
        raise OrderError(f"order id {order_id} not found", 404)
    order["items"] = db.list_order_items(order_id)
    order["delay_notices"] = db.list_delay_notices(order_id)
    return order


def advance_order(
    db: Database, order_id: int, to_status: str, actor_role: str = "SYSTEM"
) -> dict:
    """Move an order forward in the state machine (timestamps are stamped)."""
    if to_status not in STATUSES:
        raise OrderError(f"unknown status {to_status!r}", 400)
    order = db.get_order(order_id)
    if not order:
        raise OrderError(f"order id {order_id} not found", 404)
    if not can_transition(order["status"], to_status):
        raise OrderError(
            f"cannot move order {order_id} from {order['status']} to {to_status}", 400
        )
    db.transition_order(order_id, to_status, utcnow_iso())
    if to_status in FINAL_STATUSES:
        # Free the table once the order is done or cancelled.
        db.update_table(order["table_id"], {"status": "AVAILABLE"})
    return get_order_detail(db, order_id)


def cancel_order(db: Database, order_id: int, actor_role: str = "WAITER") -> dict:
    return advance_order(db, order_id, "CANCELLED", actor_role)


def kitchen_queue(db: Database) -> list[dict]:
    """Orders the kitchen must act on, oldest first."""
    queue = []
    for order in db.list_orders():
        if order["status"] in ("KITCHEN_RECEIVED", "PREPARING"):
            order["items"] = db.list_order_items(order["id"])
            queue.append(order)
    queue.sort(key=lambda o: o["placed_at"])
    return queue


def minutes_in_preparing(order: dict, now_iso: str | None = None) -> float | None:
    if order["status"] != "PREPARING" or not order.get("preparing_started_at"):
        return None
    return _minutes_between(order["preparing_started_at"], now_iso or utcnow_iso())


def is_delayed(order: dict, item_prep_minutes: list[int], threshold: int) -> bool:
    """An order is delayed when it has been PREPARING longer than the max
    expected prep time of its items, with a configurable floor (default 15)."""
    elapsed = minutes_in_preparing(order)
    if elapsed is None:
        return False
    limit = max(threshold, max(item_prep_minutes) if item_prep_minutes else 0)
    return elapsed > limit


def delayed_orders(db: Database, threshold: int) -> list[dict]:
    """All currently-delayed orders with how overdue they are."""
    delayed = []
    for order in db.list_orders(status="PREPARING"):
        items = db.list_order_items(order["id"])
        preps = [i["expected_prep_minutes"] for i in items]
        elapsed = minutes_in_preparing(order) or 0
        limit = max(threshold, max(preps) if preps else 0)
        if elapsed > limit:
            order["items"] = items
            order["minutes_in_preparing"] = round(elapsed, 1)
            order["delay_limit_minutes"] = limit
            order["minutes_overdue"] = round(elapsed - limit, 1)
            delayed.append(order)
    delayed.sort(key=lambda o: o["minutes_overdue"], reverse=True)
    return delayed
