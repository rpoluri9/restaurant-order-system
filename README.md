# RKB — Restaurant Order Management System

A restaurant order backend built with **Python** and **FastAPI**, written
**SQL-first**: every database query is explicit raw SQL in `app/db/db.py` —
no ORM anywhere. It covers the full order lifecycle from the waiter taking
an order to the kitchen preparing it to customer care handling delays
politely.

## Features

- **Order lifecycle state machine** — `PLACED → KITCHEN_RECEIVED → PREPARING →
  READY → SERVED → COMPLETED`, plus `CANCELLED` from any non-final state.
  Skipping or reversing states is rejected with a 400 error.
- **Three roles, one flow**
  - *Waiter* — takes orders (table, customer, items), serves ready orders to tables
  - *Kitchen* — sees the live kitchen queue, starts preparing, marks orders ready
  - *Customer care* — sees delayed orders, sends polite delay notices, records
    the customer's response
- **Delay detection** — an order in `PREPARING` becomes delayed when it has
  been preparing longer than the max expected prep time of its items
  (with a configurable floor, default 15 minutes)
- **Polite delay handling** — customer care sends a courteous message from a
  template (*"We're sorry for the wait! Your order will take 10 to 15 more
  minutes. Thank you for your patience."*) and records the customer's reply:
  `WAITING`, `CANCELLED_ORDER`, `ESCALATED`, or `NO_RESPONSE`
- **Menu & table management** — full CRUD for menu items (name, price,
  expected prep minutes, category, availability) and tables
- **Dashboard stats** — orders by status, average prep minutes, delayed count,
  revenue from completed orders
- **Seed script** — 10 menu items, 6 tables, and 8 sample orders across every
  state, including one delayed order with a recorded customer-care interaction
- **27 automated tests** with pytest

> **Raw SQL note:** this project deliberately uses no ORM. `app/db/db.py`
> holds every query as a plain SQL string, working on SQLite (stdlib
> `sqlite3`, dev/tests) and PostgreSQL (`psycopg2`, prod) through a small
> placeholder adapter (`?` → `%s`). Timestamps are stored as UTC ISO-8601
> text so comparisons behave identically on both engines.

## Tech Stack

| Layer    | Technology                                              |
|----------|---------------------------------------------------------|
| API      | FastAPI, Pydantic v2                                    |
| Database | Raw SQL — SQLite (dev/tests), PostgreSQL (prod)         |
| Driver   | sqlite3 (stdlib), psycopg2-binary                       |
| Tests    | pytest, FastAPI TestClient                               |
| Deploy   | Docker, Docker Compose                                   |

## Project Structure

```
restaurant-order-system/
├── app/
│   ├── main.py              # App factory, router wiring
│   ├── core/
│   │   └── config.py        # Settings from environment / .env
│   ├── db/
│   │   ├── schema.sql       # SQLite DDL
│   │   ├── schema_pg.sql    # PostgreSQL DDL
│   │   └── db.py            # ALL raw-SQL queries (no ORM)
│   ├── api/
│   │   ├── deps.py          # Database dependency
│   │   └── v1/
│   │       ├── menu.py      # Menu CRUD
│   │       ├── tables.py    # Table CRUD
│   │       ├── orders.py    # Take / track / advance / cancel orders
│   │       ├── kitchen.py   # Kitchen queue + actions
│   │       ├── customer_care.py  # Delayed orders, notices, responses
│   │       └── dashboard.py # Stats
│   ├── schemas/             # Pydantic request models
│   └── services/
│       ├── orders.py        # State machine + delay detection
│       └── notify.py        # Polite message templates
├── tests/                   # 27 pytest tests
├── images/                  # Architecture, data model, order flow diagrams
├── seed.py                  # Demo data (menu, tables, orders)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Quickstart

```bash
# 1. Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Seed demo data (creates restaurant.db via SQLite)
python seed.py

# 3. Run the API
uvicorn app.main:app --reload
# Open http://127.0.0.1:8000/docs for the interactive API docs
```

With Docker (PostgreSQL):

```bash
docker compose up --build
```

Set `DATABASE_URL` to a `postgresql://...` URL to run against PostgreSQL;
the PostgreSQL DDL in `app/db/schema_pg.sql` is applied automatically.

## API Overview

| Method | Endpoint | Who | What |
|--------|----------|-----|------|
| POST | `/api/orders` | Waiter | Take an order (table, customer, items) |
| GET | `/api/orders?status=PREPARING` | — | List / filter orders |
| GET | `/api/orders/{id}` | — | Order detail with items + notices |
| POST | `/api/orders/{id}/advance` | — | Move to next state (`to_status`, `actor_role`) |
| POST | `/api/orders/{id}/cancel` | — | Cancel the order |
| GET | `/api/kitchen/queue` | Kitchen | Orders to prepare, oldest first |
| POST | `/api/kitchen/{id}/start-preparing` | Kitchen | Begin preparation |
| POST | `/api/kitchen/{id}/mark-ready` | Kitchen | Order is ready to serve |
| GET | `/api/customer-care/delayed` | Care | Delayed orders, most overdue first |
| POST | `/api/customer-care/{id}/notify` | Care | Send polite delay message |
| POST | `/api/customer-care/{id}/respond` | Care | Record customer response |
| GET | `/api/dashboard/stats` | — | Counts, avg prep time, delayed, revenue |
| CRUD | `/api/menu`, `/api/tables` | — | Menu items and tables |

Example — take an order, then move it to the kitchen:

```bash
curl -X POST localhost:8000/api/orders -H 'Content-Type: application/json' -d '{
  "table_id": 1, "customer_name": "Ramesh", "customer_phone": "+15550001111",
  "items": [{"menu_item_id": 5, "quantity": 2}]
}'

curl -X POST localhost:8000/api/orders/1/advance -H 'Content-Type: application/json' -d '{
  "to_status": "KITCHEN_RECEIVED", "actor_role": "WAITER"
}'
```

## Order Flow

```
Waiter takes order
       │
       ▼
    PLACED ──(cancel)──▶ CANCELLED
       │ waiter confirms
       ▼
KITCHEN_RECEIVED ──(cancel)──▶ CANCELLED
       │ kitchen starts
       ▼
   PREPARING ──(cancel)──▶ CANCELLED   ◀── delay? customer care notifies politely
       │ kitchen finishes                        and records the response
       ▼
     READY ──(cancel)──▶ CANCELLED
       │ waiter serves
       ▼
    SERVED ──(cancel)──▶ CANCELLED
       │ payment done
       ▼
   COMPLETED   (table freed)
```

## Running Tests

```bash
pytest tests/ -q
# 27 passed
```

Tests use an isolated in-memory SQLite database; no server needed.
