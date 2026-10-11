"""Shared dependencies: access to the raw-SQL Database instance."""
from fastapi import Request

from ..db.db import Database


def get_db(request: Request) -> Database:
    return request.app.state.db
