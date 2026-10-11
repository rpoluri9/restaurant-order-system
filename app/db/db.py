"""Raw-SQL database layer. No ORM: every query in this module is explicit SQL.

Supports SQLite (stdlib ``sqlite3``, used for local dev and tests) and
PostgreSQL (``psycopg2``, used in production). SQL is written once with ``?``
placeholders and translated to ``%s`` for psycopg2 automatically.
Timestamps are stored as UTC ISO-8601 text so comparisons and ordering behave
identically on both engines.
"""
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_SQL = Path(__file__).with_name("schema.sql").read_text()
SCHEMA_PG_SQL = Path(__file__).with_name("schema_pg.sql").read_text()


def utcnow_iso() -> str:
    """Current UTC time as 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.is_pg = database_url.startswith(("postgres://", "postgresql://"))
        if self.is_pg:
            import psycopg2
            import psycopg2.extras

            self._pg = psycopg2.connect(database_url)
            self._pg.autocommit = True
            self._pg_extras = psycopg2.extras
        else:
            import sqlite3

            path = database_url.replace("sqlite:///", "").replace("sqlite://", "")
            if path in ("", ":memory:"):
                path = ":memory:"
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")

    # -- low-level helpers -------------------------------------------------
    def _adapt(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.is_pg else sql

    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        """Run SQL; return rows as a list of dicts (empty for DML)."""
        sql = self._adapt(sql)
        if self.is_pg:
            with self._pg.cursor(
                cursor_factory=self._pg_extras.RealDictCursor
            ) as cur:
                cur.execute(sql, params)
                if cur.description:
                    return [dict(r) for r in cur.fetchall()]
                return []
        cur = self._conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()] if cur.description else []
        self._conn.commit()
        return rows

    def execute_one(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.execute(sql, params)
        return rows[0] if rows else None

    def insert(self, sql: str, params: tuple = ()) -> int:
        """Run an INSERT and return the new row's id."""
        if self.is_pg:
            row = self.execute_one(sql.rstrip().rstrip(";") + " RETURNING id", params)
            return int(row["id"])
        cur = self._conn.execute(self._adapt(sql), params)
        self._conn.commit()
        return int(cur.lastrowid)

    def init_schema(self) -> None:
        """Create tables if they do not exist (idempotent)."""
        schema = SCHEMA_PG_SQL if self.is_pg else SCHEMA_SQL
        if self.is_pg:
            for stmt in [s.strip() for s in schema.split(";") if s.strip()]:
                self.execute(stmt)
        else:
            self._conn.executescript(schema)
            self._conn.commit()

    # -- menu_items ---------------------------------------------------------
    def create_menu_item(
        self,
        name: str,
        price_cents: int,
        expected_prep_minutes: int,
        category: str,
        is_available: int = 1,
        created_at: str | None = None,
    ) -> int:
        return self.insert(
            """INSERT INTO menu_items
               (name, price_cents, expected_prep_minutes, category, is_available, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                name,
                price_cents,
                expected_prep_minutes,
                category,
                is_available,
                created_at or utcnow_iso(),
            ),
        )

    def list_menu_items(self, available_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM menu_items"
        if available_only:
            sql += " WHERE is_available = 1"
        return self.execute(sql + " ORDER BY category, name")

    def get_menu_item(self, item_id: int) -> dict | None:
        return self.execute_one("SELECT * FROM menu_items WHERE id = ?", (item_id,))

    def update_menu_item(self, item_id: int, fields: dict) -> dict | None:
        allowed = {"name", "price_cents", "expected_prep_minutes", "category", "is_available"}
        sets = [f"{k} = ?" for k in fields if k in allowed]
        if not sets:
            return self.get_menu_item(item_id)
        params = tuple(fields[k] for k in fields if k in allowed) + (item_id,)
        self.execute(f"UPDATE menu_items SET {', '.join(sets)} WHERE id = ?", params)
        return self.get_menu_item(item_id)

    def delete_menu_item(self, item_id: int) -> bool:
        rows = self.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
        # sqlite3 cursor rowcount is unreliable here; re-check existence.
        return self.get_menu_item(item_id) is None

    # -- restaurant_tables ---------------------------------------------------
    def create_table(
        self, table_number: int, seats: int, status: str = "AVAILABLE",
        created_at: str | None = None,
    ) -> int:
        return self.insert(
            """INSERT INTO restaurant_tables (table_number, seats, status, created_at)
               VALUES (?, ?, ?, ?)""",
            (table_number, seats, status, created_at or utcnow_iso()),
        )

    def list_tables(self) -> list[dict]:
        return self.execute("SELECT * FROM restaurant_tables ORDER BY table_number")

    def get_table(self, table_id: int) -> dict | None:
        return self.execute_one(
            "SELECT * FROM restaurant_tables WHERE id = ?", (table_id,)
        )

    def get_table_by_number(self, table_number: int) -> dict | None:
        return self.execute_one(
            "SELECT * FROM restaurant_tables WHERE table_number = ?", (table_number,)
        )

    def update_table(self, table_id: int, fields: dict) -> dict | None:
        allowed = {"table_number", "seats", "status"}
        sets = [f"{k} = ?" for k in fields if k in allowed]
        if not sets:
            return self.get_table(table_id)
        params = tuple(fields[k] for k in fields if k in allowed) + (table_id,)
        self.execute(
            f"UPDATE restaurant_tables SET {', '.join(sets)} WHERE id = ?", params
        )
        return self.get_table(table_id)

    def delete_table(self, table_id: int) -> bool:
        self.execute("DELETE FROM restaurant_tables WHERE id = ?", (table_id,))
        return self.get_table(table_id) is None

    # -- orders --------------------------------------------------------------
    def create_order(
        self,
        table_id: int,
        customer_name: str,
        customer_phone: str | None,
        total_cents: int,
        created_by_role: str = "WAITER",
        placed_at: str | None = None,
    ) -> int:
        return self.insert(
            """INSERT INTO orders
               (table_id, customer_name, customer_phone, status, placed_at,
                total_cents, created_by_role)
               VALUES (?, ?, ?, 'PLACED', ?, ?, ?)""",
            (
                table_id,
                customer_name,
                customer_phone,
                placed_at or utcnow_iso(),
                total_cents,
                created_by_role,
            ),
        )

    def get_order(self, order_id: int) -> dict | None:
        return self.execute_one("SELECT * FROM orders WHERE id = ?", (order_id,))

    def list_orders(self, status: str | None = None) -> list[dict]:
        if status:
            return self.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY placed_at DESC",
                (status,),
            )
        return self.execute("SELECT * FROM orders ORDER BY placed_at DESC")

    def transition_order(self, order_id: int, to_status: str, ts: str) -> dict | None:
        """Set status and stamp the matching lifecycle timestamp column."""
        column = {
            "KITCHEN_RECEIVED": "kitchen_received_at",
            "PREPARING": "preparing_started_at",
            "READY": "ready_at",
            "SERVED": "served_at",
            "COMPLETED": "completed_at",
            "CANCELLED": "cancelled_at",
        }[to_status]
        self.execute(
            f"UPDATE orders SET status = ?, {column} = ? WHERE id = ?",
            (to_status, ts, order_id),
        )
        return self.get_order(order_id)

    def set_order_field(self, order_id: int, field: str, value: str) -> None:
        allowed = {
            "placed_at",
            "kitchen_received_at",
            "preparing_started_at",
            "ready_at",
            "served_at",
            "completed_at",
            "cancelled_at",
        }
        if field not in allowed:
            raise ValueError(f"cannot set field {field!r}")
        self.execute(f"UPDATE orders SET {field} = ? WHERE id = ?", (value, order_id))

    # -- order_items -----------------------------------------------------------
    def create_order_item(
        self,
        order_id: int,
        menu_item_id: int,
        quantity: int,
        price_cents: int,
        expected_prep_minutes: int,
    ) -> int:
        return self.insert(
            """INSERT INTO order_items
               (order_id, menu_item_id, quantity, price_cents, expected_prep_minutes)
               VALUES (?, ?, ?, ?, ?)""",
            (order_id, menu_item_id, quantity, price_cents, expected_prep_minutes),
        )

    def list_order_items(self, order_id: int) -> list[dict]:
        return self.execute(
            """SELECT oi.*, mi.name AS menu_item_name, mi.category
               FROM order_items oi
               JOIN menu_items mi ON mi.id = oi.menu_item_id
               WHERE oi.order_id = ?""",
            (order_id,),
        )

    # -- delay_notices -----------------------------------------------------------
    def create_delay_notice(
        self, order_id: int, message: str, sent_by: str = "CUSTOMER_CARE",
        sent_at: str | None = None,
    ) -> int:
        return self.insert(
            """INSERT INTO delay_notices (order_id, message, sent_at, sent_by)
               VALUES (?, ?, ?, ?)""",
            (order_id, message, sent_at or utcnow_iso(), sent_by),
        )

    def get_notice(self, notice_id: int) -> dict | None:
        return self.execute_one(
            "SELECT * FROM delay_notices WHERE id = ?", (notice_id,)
        )

    def list_delay_notices(self, order_id: int) -> list[dict]:
        return self.execute(
            "SELECT * FROM delay_notices WHERE order_id = ? ORDER BY sent_at DESC",
            (order_id,),
        )

    def latest_notice(self, order_id: int) -> dict | None:
        return self.execute_one(
            """SELECT * FROM delay_notices WHERE order_id = ?
               ORDER BY sent_at DESC, id DESC LIMIT 1""",
            (order_id,),
        )

    def record_customer_response(
        self, notice_id: int, response: str, responded_at: str | None = None
    ) -> dict | None:
        self.execute(
            """UPDATE delay_notices
               SET customer_response = ?, responded_at = ? WHERE id = ?""",
            (response, responded_at or utcnow_iso(), notice_id),
        )
        return self.get_notice(notice_id)

    # -- dashboard ---------------------------------------------------------------
    def count_orders_by_status(self) -> list[dict]:
        return self.execute(
            "SELECT status, COUNT(*) AS count FROM orders GROUP BY status"
        )

    def prep_durations(self) -> list[dict]:
        """ready_at - preparing_started_at for finished-prep orders (raw rows)."""
        return self.execute(
            """SELECT preparing_started_at, ready_at FROM orders
               WHERE preparing_started_at IS NOT NULL AND ready_at IS NOT NULL"""
        )

    def revenue_cents(self) -> int:
        row = self.execute_one(
            "SELECT COALESCE(SUM(total_cents), 0) AS revenue FROM orders "
            "WHERE status = 'COMPLETED'"
        )
        return int(row["revenue"])
