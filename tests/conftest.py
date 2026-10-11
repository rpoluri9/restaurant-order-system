"""Pytest fixtures: isolated in-memory SQLite DB via raw SQL, test data helpers."""
import pytest
from fastapi.testclient import TestClient

from app.db.db import Database
from app.main import create_app

# Test app skips schema creation: the db fixture manages its own database.
app = create_app(init_db=False)


@pytest.fixture()
def db():
    database = Database("sqlite:///:memory:")
    database.init_schema()
    app.state.db = database
    yield database


@pytest.fixture()
def client(db):
    with TestClient(app) as c:
        yield c


def make_menu_item(db, name="Margherita Pizza", price_cents=1299,
                   prep=12, category="Mains", available=1):
    return db.create_menu_item(
        name=name, price_cents=price_cents, expected_prep_minutes=prep,
        category=category, is_available=available,
    )


def make_table(db, number=1, seats=4):
    return db.create_table(table_number=number, seats=seats)


@pytest.fixture()
def menu_item(db):
    return make_menu_item(db)


@pytest.fixture()
def menu_item2(db):
    return make_menu_item(db, name="Caesar Salad", price_cents=899,
                          prep=8, category="Starters")


@pytest.fixture()
def table(db):
    return make_table(db)


def place(db, table_id, items, name="Ramesh", phone="+15550001111"):
    """Place an order through the service layer (bypasses HTTP)."""
    from app.services.orders import place_order
    return place_order(
        db, table_id=table_id, customer_name=name, customer_phone=phone,
        items=[{"menu_item_id": i, "quantity": q} for i, q in items],
    )


@pytest.fixture()
def order(db, table, menu_item, menu_item2):
    return place(db, table, [(menu_item, 2), (menu_item2, 1)])
