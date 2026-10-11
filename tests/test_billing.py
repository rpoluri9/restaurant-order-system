"""Tests for RKB billing: family discount + taxes."""
import pytest

from app.services.billing import calculate_bill
from app.services.orders import OrderError, place_order
from tests.conftest import make_menu_item, make_table


def make_order(db, items):
    table_id = make_table(db)
    return place_order(
        db,
        table_id=table_id,
        customer_name="Test Family",
        customer_phone="+15550009999",
        items=[
            {"menu_item_id": make_menu_item(
                db, name=f"Item{i}", price_cents=price),
             "quantity": qty}
            for i, (price, qty) in enumerate(items)
        ],
    )


def test_bill_no_discount_under_200(db):
    order = make_order(db, [(5000, 2)])  # $100 subtotal
    bill = calculate_bill(db, order["id"])
    assert bill["subtotal_cents"] == 10000
    assert bill["family_discount_applied"] is False
    assert bill["family_discount_cents"] == 0
    assert bill["gst_cents"] == 1000          # 10%
    assert bill["state_tax_cents"] == 600     # 6%
    assert bill["sales_tax_cents"] == 400     # 4%
    assert bill["total_cents"] == 12000       # $120


def test_bill_no_discount_at_exactly_200(db):
    order = make_order(db, [(10000, 2)])  # $200 subtotal (not above)
    bill = calculate_bill(db, order["id"])
    assert bill["family_discount_applied"] is False
    assert bill["total_cents"] == 20000 + 2000 + 1200 + 800


def test_bill_family_discount_above_200(db):
    order = make_order(db, [(15000, 2)])  # $300 subtotal
    bill = calculate_bill(db, order["id"])
    assert bill["subtotal_cents"] == 30000
    assert bill["family_discount_applied"] is True
    assert bill["family_discount_cents"] == 7500   # 25% of $300
    assert bill["taxable_cents"] == 22500
    assert bill["gst_cents"] == 2250
    assert bill["state_tax_cents"] == 1350
    assert bill["sales_tax_cents"] == 900
    assert bill["total_cents"] == 22500 + 2250 + 1350 + 900


def test_bill_missing_order(db):
    with pytest.raises(OrderError):
        calculate_bill(db, 9999)


def test_bill_endpoint(client, db):
    table_id = make_table(db)
    item_id = make_menu_item(db, name="Family Platter", price_cents=25000)
    r = client.post("/api/orders", json={
        "table_id": table_id,
        "customer_name": "Test Family",
        "customer_phone": "+15550009999",
        "items": [{"menu_item_id": item_id, "quantity": 1}],
    })
    order_id = r.json()["id"]
    r = client.get(f"/api/orders/{order_id}/bill")
    assert r.status_code == 200
    bill = r.json()
    assert bill["family_discount_applied"] is True
    assert bill["total_cents"] == 18750 + 1875 + 1125 + 750


def test_bill_endpoint_missing_order(client, db):
    r = client.get("/api/orders/9999/bill")
    assert r.status_code == 404
