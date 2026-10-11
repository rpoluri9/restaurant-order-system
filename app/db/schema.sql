-- Restaurant Order Management System — SQLite schema.
-- All timestamps are UTC ISO-8601 text ("YYYY-MM-DD HH:MM:SS") so that
-- ordering and comparison work identically on SQLite and PostgreSQL.

CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    expected_prep_minutes INTEGER NOT NULL CHECK (expected_prep_minutes > 0),
    category TEXT NOT NULL,
    is_available INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS restaurant_tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number INTEGER NOT NULL UNIQUE,
    seats INTEGER NOT NULL CHECK (seats > 0),
    status TEXT NOT NULL DEFAULT 'AVAILABLE',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL REFERENCES restaurant_tables(id),
    customer_name TEXT NOT NULL,
    customer_phone TEXT,
    status TEXT NOT NULL DEFAULT 'PLACED',
    placed_at TEXT NOT NULL,
    kitchen_received_at TEXT,
    preparing_started_at TEXT,
    ready_at TEXT,
    served_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT,
    total_cents INTEGER NOT NULL DEFAULT 0,
    created_by_role TEXT NOT NULL DEFAULT 'WAITER'
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price_cents INTEGER NOT NULL,
    expected_prep_minutes INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS delay_notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    sent_by TEXT NOT NULL DEFAULT 'CUSTOMER_CARE',
    customer_response TEXT,
    responded_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_table ON orders(table_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_notices_order ON delay_notices(order_id);
