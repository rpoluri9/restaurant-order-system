"""Application entry point."""
from fastapi import FastAPI

from .api.v1 import customer_care, dashboard, kitchen, menu, orders, tables
from .core.config import settings
from .db.db import Database


def create_app(*, init_db: bool = True) -> FastAPI:
    """Build the FastAPI app.

    init_db=False is used by the test suite, which manages its own
    in-memory SQLite database instead of the configured database.
    """
    db = Database(settings.database_url)
    if init_db:
        db.init_schema()

    app = FastAPI(title=settings.app_name, version="1.0.0")
    app.state.db = db

    app.include_router(menu.router, prefix="/api")
    app.include_router(tables.router, prefix="/api")
    app.include_router(orders.router, prefix="/api")
    app.include_router(kitchen.router, prefix="/api")
    app.include_router(customer_care.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
