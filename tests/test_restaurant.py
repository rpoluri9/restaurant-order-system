"""Tests for the Restaurant Order Management System (raw-SQL backend)."""
from datetime import datetime, timedelta, timezone

from tests.conftest import make_menu_item, make_table, place

from app.services.notify import DEFAULT_DELAY_MESSAGE


def _iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _minutes_ago(n):
    return _iso(datetime.now(timezone.utc) - timedelta(minutes=n))


# -- order placement ---------------------------------------------------------
def test_place_order_happy_path(client, db, table, menu_item, menu_item2):
    r = client.post("/api/orders", json={
        "table_id": table,
        "customer_name": "Ramesh",
        "customer_phone": "+15550001111",
        "items": [
            {"menu_item_id": menu_item, "quantity": 2},
            {"menu_item_id": menu_item2, "quantity": 1},
        ],
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "PLACED"
    assert body["total_cents"] == 1299 * 2 + 899
    assert len(body["items"]) == 2
    # table is now occupied
    t = client.get(f"/api/tables/{table}").json()
    assert t["status"] == "OCCUPIED"


def test_place_order_unknown_menu_item(client, db, table):
    r = client.post("/api/orders", json={
        "table_id": table, "customer_name": "X",
        "items": [{"menu_item_id": 9999, "quantity": 1}],
    })
    assert r.status_code == 404


def test_place_order_unavailable_item(client, db, table, menu_item):
    db.update_menu_item(menu_item, {"is_available": 0})
    r = client.post("/api/orders", json={
        "table_id": table, "customer_name": "X",
        "items": [{"menu_item_id": menu_item, "quantity": 1}],
    })
    assert r.status_code == 400


def test_place_order_unknown_table(client, db, menu_item):
    r = client.post("/api/orders", json={
        "table_id": 9999, "customer_name": "X",
        "items": [{"menu_item_id": menu_item, "quantity": 1}],
    })
    assert r.status_code == 404


# -- state machine ------------------------------------------------------------
def test_full_lifecycle(client, db, order, table):
    oid = order["id"]
    flow = ["KITCHEN_RECEIVED", "PREPARING", "READY", "SERVED", "COMPLETED"]
    for status in flow:
        r = client.post(f"/api/orders/{oid}/advance",
                        json={"to_status": status, "actor_role": "WAITER"})
        assert r.status_code == 200, (status, r.text)
        assert r.json()["status"] == status
    final = r.json()
    assert final["completed_at"] is not None
    assert final["preparing_started_at"] is not None
    assert final["ready_at"] is not None
    # table freed after completion
    t = client.get(f"/api/tables/{table}").json()
    assert t["status"] == "AVAILABLE"


def test_invalid_transition_skips_state(client, db, order):
    r = client.post(f"/api/orders/{order['id']}/advance",
                    json={"to_status": "READY"})
    assert r.status_code == 400


def test_invalid_transition_backwards(client, db, order):
    client.post(f"/api/orders/{order['id']}/advance",
                json={"to_status": "KITCHEN_RECEIVED"})
    client.post(f"/api/orders/{order['id']}/advance",
                json={"to_status": "PREPARING"})
    client.post(f"/api/orders/{order['id']}/advance",
                json={"to_status": "READY"})
    r = client.post(f"/api/orders/{order['id']}/advance",
                    json={"to_status": "PREPARING"})
    assert r.status_code == 400


def test_invalid_transition_unknown_status(client, db, order):
    r = client.post(f"/api/orders/{order['id']}/advance",
                    json={"to_status": "EATEN"})
    assert r.status_code == 400


def test_cancel_from_placed(client, db, order, table):
    r = client.post(f"/api/orders/{order['id']}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"
    assert r.json()["cancelled_at"] is not None
    t = client.get(f"/api/tables/{table}").json()
    assert t["status"] == "AVAILABLE"


def test_cancel_from_preparing_ok(client, db, order):
    client.post(f"/api/orders/{order['id']}/advance",
                json={"to_status": "KITCHEN_RECEIVED"})
    client.post(f"/api/orders/{order['id']}/advance",
                json={"to_status": "PREPARING"})
    r = client.post(f"/api/orders/{order['id']}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"


def test_cancel_completed_rejected(client, db, order):
    for s in ["KITCHEN_RECEIVED", "PREPARING", "READY", "SERVED", "COMPLETED"]:
        client.post(f"/api/orders/{order['id']}/advance", json={"to_status": s})
    r = client.post(f"/api/orders/{order['id']}/cancel")
    assert r.status_code == 400


# -- kitchen -------------------------------------------------------------------
def test_kitchen_queue(client, db, table, menu_item):
    o1 = place(db, table, [(menu_item, 1)], name="A")
    t2 = make_table(db, number=2)
    o2 = place(db, t2, [(menu_item, 1)], name="B")
    t3 = make_table(db, number=3)
    o3 = place(db, t3, [(menu_item, 1)], name="C")
    client.post(f"/api/orders/{o1['id']}/advance", json={"to_status": "KITCHEN_RECEIVED"})
    client.post(f"/api/orders/{o2['id']}/advance", json={"to_status": "KITCHEN_RECEIVED"})
    client.post(f"/api/orders/{o2['id']}/advance", json={"to_status": "PREPARING"})
    # o3 stays PLACED -> not in kitchen queue
    queue = client.get("/api/kitchen/queue").json()
    assert [o["id"] for o in queue] == [o1["id"], o2["id"]]
    assert queue[0]["items"]  # items included


def test_kitchen_shortcuts(client, db, order):
    oid = order["id"]
    client.post(f"/api/orders/{oid}/advance", json={"to_status": "KITCHEN_RECEIVED"})
    r = client.post(f"/api/kitchen/{oid}/start-preparing")
    assert r.status_code == 200
    assert r.json()["status"] == "PREPARING"
    r = client.post(f"/api/kitchen/{oid}/mark-ready")
    assert r.status_code == 200
    assert r.json()["status"] == "READY"


def test_kitchen_shortcut_wrong_state(client, db, order):
    r = client.post(f"/api/kitchen/{order['id']}/mark-ready")
    assert r.status_code == 400  # PLACED -> READY is invalid


# -- delay detection & customer care ---------------------------------------------
def _to_preparing(client, db, order, minutes_ago):
    oid = order["id"]
    client.post(f"/api/orders/{oid}/advance", json={"to_status": "KITCHEN_RECEIVED"})
    client.post(f"/api/orders/{oid}/advance", json={"to_status": "PREPARING"})
    db.set_order_field(oid, "preparing_started_at", _minutes_ago(minutes_ago))


def test_delayed_order_detected(client, db, order):
    # items have max 12 min expected prep; 30 min elapsed -> delayed
    _to_preparing(client, db, order, minutes_ago=30)
    delayed = client.get("/api/customer-care/delayed").json()
    assert len(delayed) == 1
    assert delayed[0]["id"] == order["id"]
    assert delayed[0]["minutes_overdue"] > 0


def test_not_delayed_within_time(client, db, order):
    _to_preparing(client, db, order, minutes_ago=5)
    delayed = client.get("/api/customer-care/delayed").json()
    assert delayed == []


def test_notify_sends_polite_default_message(client, db, order):
    _to_preparing(client, db, order, minutes_ago=30)
    r = client.post(f"/api/customer-care/{order['id']}/notify", json={})
    assert r.status_code == 201, r.text
    notice = r.json()
    assert notice["message"] == DEFAULT_DELAY_MESSAGE
    assert "10 to 15" in notice["message"]
    # stored on the order
    detail = client.get(f"/api/orders/{order['id']}").json()
    assert len(detail["delay_notices"]) == 1


def test_notify_custom_message(client, db, order):
    r = client.post(f"/api/customer-care/{order['id']}/notify",
                    json={"message": "Custom apology."})
    assert r.status_code == 201
    assert r.json()["message"] == "Custom apology."


def test_notify_finished_order_rejected(client, db, order):
    for s in ["KITCHEN_RECEIVED", "PREPARING", "READY", "SERVED", "COMPLETED"]:
        client.post(f"/api/orders/{order['id']}/advance", json={"to_status": s})
    r = client.post(f"/api/customer-care/{order['id']}/notify", json={})
    assert r.status_code == 400


def test_respond_records_customer_response(client, db, order):
    client.post(f"/api/customer-care/{order['id']}/notify", json={})
    r = client.post(f"/api/customer-care/{order['id']}/respond",
                    json={"response": "WAITING"})
    assert r.status_code == 200
    assert r.json()["customer_response"] == "WAITING"
    assert r.json()["responded_at"] is not None


def test_respond_without_notice_rejected(client, db, order):
    r = client.post(f"/api/customer-care/{order['id']}/respond",
                    json={"response": "WAITING"})
    assert r.status_code == 404


def test_respond_invalid_enum_rejected(client, db, order):
    client.post(f"/api/customer-care/{order['id']}/notify", json={})
    r = client.post(f"/api/customer-care/{order['id']}/respond",
                    json={"response": "MAYBE"})
    assert r.status_code == 422


# -- menu & table CRUD ------------------------------------------------------------
def test_menu_crud(client, db):
    r = client.post("/api/menu", json={
        "name": "Paneer Tikka", "price_cents": 1099,
        "expected_prep_minutes": 15, "category": "Starters",
    })
    assert r.status_code == 201
    item_id = r.json()["id"]
    assert client.get("/api/menu").json()
    r = client.patch(f"/api/menu/{item_id}", json={"price_cents": 1199})
    assert r.json()["price_cents"] == 1199
    r = client.delete(f"/api/menu/{item_id}")
    assert r.status_code == 204
    assert client.get(f"/api/menu/{item_id}").status_code == 404


def test_tables_crud(client, db):
    r = client.post("/api/tables", json={"table_number": 7, "seats": 6})
    assert r.status_code == 201
    tid = r.json()["id"]
    r = client.patch(f"/api/tables/{tid}", json={"status": "RESERVED"})
    assert r.json()["status"] == "RESERVED"
    assert client.get("/api/tables").json()


# -- dashboard & listing ------------------------------------------------------------
def test_dashboard_stats(client, db, table, menu_item):
    o1 = place(db, table, [(menu_item, 1)], name="A")
    t2 = make_table(db, number=2)
    o2 = place(db, t2, [(menu_item, 1)], name="B")
    # complete o1 with a 10-minute prep
    for s in ["KITCHEN_RECEIVED", "PREPARING"]:
        client.post(f"/api/orders/{o1['id']}/advance", json={"to_status": s})
    db.set_order_field(o1["id"], "preparing_started_at", _minutes_ago(10))
    client.post(f"/api/orders/{o1['id']}/advance", json={"to_status": "READY"})
    for s in ["SERVED", "COMPLETED"]:
        client.post(f"/api/orders/{o1['id']}/advance", json={"to_status": s})
    # o2 delayed: 40 min in preparing
    for s in ["KITCHEN_RECEIVED", "PREPARING"]:
        client.post(f"/api/orders/{o2['id']}/advance", json={"to_status": s})
    db.set_order_field(o2["id"], "preparing_started_at", _minutes_ago(40))

    stats = client.get("/api/dashboard/stats").json()
    assert stats["orders_by_status"]["COMPLETED"] == 1
    assert stats["orders_by_status"]["PREPARING"] == 1
    assert stats["delayed_count"] == 1
    assert stats["delayed_order_ids"] == [o2["id"]]
    assert stats["avg_prep_minutes"] is not None
    assert stats["avg_prep_minutes"] >= 9  # ~10 min prep recorded
    assert stats["revenue_cents"] == 1299  # only the completed order


def test_list_orders_filter_by_status(client, db, order):
    r = client.get("/api/orders", params={"status": "PLACED"})
    assert r.status_code == 200
    assert all(o["status"] == "PLACED" for o in r.json())
    assert any(o["id"] == order["id"] for o in r.json())
    r = client.get("/api/orders", params={"status": "BOGUS"})
    assert r.status_code == 400


def test_get_order_detail_includes_items_and_notices(client, db, order):
    r = client.get(f"/api/orders/{order['id']}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["delay_notices"] == []
    assert client.get("/api/orders/9999").status_code == 404
