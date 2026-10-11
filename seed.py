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
    # Prices range from $10.00 to $100.00 as set for RKB restaurant.
    # --- Non-Veg ---
    ("Chicken Curry", 2500, 20, "Non-Veg"),
    ("Mutton Curry", 4500, 25, "Non-Veg"),
    ("Lamb Chops", 6000, 25, "Non-Veg"),
    ("Fish Fry", 3500, 20, "Non-Veg"),
    ("Chicken Biryani", 3000, 20, "Biryanis"),
    ("Mutton Biryani", 4500, 25, "Biryanis"),
    ("Fish Biryani", 4000, 22, "Biryanis"),
    ("Ice Cream", 1000, 5, "Desserts"),
    # --- Veg ---
    ("Sambar", 1200, 10, "Veg"),
    ("Rice", 1000, 8, "Veg"),
    ("Okarn", 1500, 12, "Veg"),
    ("Dondi Fry", 1800, 12, "Veg"),
    ("Mondal", 2000, 15, "Veg"),
    ("Roti", 1000, 5, "Veg"),
    ("Dal", 1200, 10, "Veg"),
    ("Tomato Dal", 1400, 10, "Veg"),
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
    o1 = order(1, [("Sambar", 1), ("Chicken Biryani", 1)], "Anita Rao", "+15550001001")
    db.set_order_field(o1["id"], "placed_at", minutes_ago(90))
    for status, ago in [("KITCHEN_RECEIVED", 85), ("PREPARING", 80),
                        ("READY", 65), ("SERVED", 60), ("COMPLETED", 30)]:
        db.transition_order(o1["id"], status, minutes_ago(ago))

    # 2. Served order
    o2 = order(2, [("Chicken Biryani", 2)], "Vikram Shah", "+15550001002")
    for status in ["KITCHEN_RECEIVED", "PREPARING", "READY", "SERVED"]:
        advance_order(db, o2["id"], status)

    # 3. Ready order waiting for the waiter
    o3 = order(3, [("Roti", 2), ("Ice Cream", 2)], "Priya Nair", "+15550001003")
    for status in ["KITCHEN_RECEIVED", "PREPARING", "READY"]:
        advance_order(db, o3["id"], status)

    # 4. Preparing, on time (started 5 minutes ago)
    o4 = order(4, [("Rice", 1)], "Arjun Mehta", "+15550001004")
    for status in ["KITCHEN_RECEIVED", "PREPARING"]:
        advance_order(db, o4["id"], status)
    db.set_order_field(o4["id"], "preparing_started_at", minutes_ago(5))

    # 5. DELAYED order: 35 min in PREPARING, max item prep is 25 min
    o5 = order(5, [("Mutton Curry", 1), ("Fish Fry", 1)], "Ramesh Poluri", "+15550001005")
    for status in ["KITCHEN_RECEIVED", "PREPARING"]:
        advance_order(db, o5["id"], status)
    db.set_order_field(o5["id"], "preparing_started_at", minutes_ago(35))
    notice_id = db.create_delay_notice(o5["id"], DEFAULT_DELAY_MESSAGE)
    db.record_customer_response(notice_id, "WAITING")
    print(f"Seeded delayed order #{o5['id']} with a customer-care notice (response: WAITING).")

    # 6. Just received by the kitchen
    o6 = order(6, [("Dal", 1), ("Ice Cream", 2)], "Sara Khan", "+15550001006")
    advance_order(db, o6["id"], "KITCHEN_RECEIVED")

    # 7. Freshly placed
    o7 = order(1, [("Tomato Dal", 1)], "Dev Patel", "+15550001007")

    # 8. Cancelled order
    o8 = order(2, [("Sambar", 1)], "Neha Gupta", "+15550001008")
    advance_order(db, o8["id"], "CANCELLED")

    print("Seeded 8 sample orders across all states.")
    print(f"Done at {utcnow_iso()} UTC.")


if __name__ == "__main__":
    main()
