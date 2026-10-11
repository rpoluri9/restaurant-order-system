"""Seed the RKB restaurant database with demo menu, tables, and sample orders.

Run:  python seed.py
"""
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.db.db import Database, utcnow_iso
from app.services.notify import DEFAULT_DELAY_MESSAGE
from app.services.orders import advance_order, place_order


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def minutes_ago(n: int) -> str:
    return iso(datetime.now(timezone.utc) - timedelta(minutes=n))


MENU = [
    # name, price_cents, expected_prep_minutes, category
    ("Tomato Soup", 599, 8, "Starters"),
    ("Paneer Tikka", 1099, 15, "Starters"),
    ("Chicken 65", 1199, 15, "Starters"),
    ("Caesar Salad", 899, 8, "Starters"),
    ("Margherita Pizza", 1299, 12, "Mains"),
    ("Chicken Biryani", 1499, 20, "Mains"),
    ("Veg Fried Rice", 999, 10, "Mains"),
    ("Masala Dosa", 899, 10, "Mains"),
    ("Gulab Jamun", 499, 5, "Desserts"),
    ("Mango Lassi", 399, 5, "Beverages"),
]

TABLES = [(1, 2), (2, 4), (3, 4), (4, 6), (5, 2), (6, 8)]


def main() -> None:
    db = Database(settings.database_url)
    db.init_schema()

    if db.list_menu_items():
        print("Database already has data; skipping seed.")
        return

    menu_ids = {}
    for name, price, prep, cat in MENU:
        menu_ids[name] = db.create_menu_item(
            name=name, price_cents=price,
            expected_prep_minutes=prep, category=cat,
        )
    table_ids = {}
    for number, seats in TABLES:
        table_ids[number] = db.create_table(table_number=number, seats=seats)
    print(f"Seeded {len(menu_ids)} menu items and {len(table_ids)} tables.")

    def order(table_no, items, name, phone):
        return place_order(
            db,
            table_id=table_ids[table_no],
            customer_name=name,
            customer_phone=phone,
            items=[
                {"menu_item_id": menu_ids[n], "quantity": q} for n, q in items
            ],
        )

    # 1. Completed order (full history, realistic timestamps)
    o1 = order(1, [("Tomato Soup", 1), ("Margherita Pizza", 1)], "Anita Rao", "+15550001001")
    db.set_order_field(o1["id"], "placed_at", minutes_ago(90))
    for status, ago in [("KITCHEN_RECEIVED", 85), ("PREPARING", 80),
                        ("READY", 65), ("SERVED", 60), ("COMPLETED", 30)]:
        db.transition_order(o1["id"], status, minutes_ago(ago))

    # 2. Served order
    o2 = order(2, [("Chicken Biryani", 2)], "Vikram Shah", "+15550001002")
    for status in ["KITCHEN_RECEIVED", "PREPARING", "READY", "SERVED"]:
        advance_order(db, o2["id"], status)

    # 3. Ready order waiting for the waiter
    o3 = order(3, [("Masala Dosa", 2), ("Mango Lassi", 2)], "Priya Nair", "+15550001003")
    for status in ["KITCHEN_RECEIVED", "PREPARING", "READY"]:
        advance_order(db, o3["id"], status)

    # 4. Preparing, on time (started 5 minutes ago)
    o4 = order(4, [("Veg Fried Rice", 1)], "Arjun Mehta", "+15550001004")
    for status in ["KITCHEN_RECEIVED", "PREPARING"]:
        advance_order(db, o4["id"], status)
    db.set_order_field(o4["id"], "preparing_started_at", minutes_ago(5))

    # 5. DELAYED order: 35 min in PREPARING, max item prep is 15 min
    o5 = order(5, [("Paneer Tikka", 1), ("Chicken 65", 1)], "Ramesh Poluri", "+15550001005")
    for status in ["KITCHEN_RECEIVED", "PREPARING"]:
        advance_order(db, o5["id"], status)
    db.set_order_field(o5["id"], "preparing_started_at", minutes_ago(35))
    notice_id = db.create_delay_notice(o5["id"], DEFAULT_DELAY_MESSAGE)
    db.record_customer_response(notice_id, "WAITING")
    print(f"Seeded delayed order #{o5['id']} with a customer-care notice (response: WAITING).")

    # 6. Just received by the kitchen
    o6 = order(6, [("Caesar Salad", 1), ("Gulab Jamun", 2)], "Sara Khan", "+15550001006")
    advance_order(db, o6["id"], "KITCHEN_RECEIVED")

    # 7. Freshly placed
    o7 = order(1, [("Mango Lassi", 1)], "Dev Patel", "+15550001007")

    # 8. Cancelled order
    o8 = order(2, [("Tomato Soup", 1)], "Neha Gupta", "+15550001008")
    advance_order(db, o8["id"], "CANCELLED")

    print("Seeded 8 sample orders across all states.")
    print(f"Done at {utcnow_iso()} UTC.")


if __name__ == "__main__":
    main()
