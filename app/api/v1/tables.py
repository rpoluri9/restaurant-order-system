"""Restaurant table endpoints (CRUD)."""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_db
from ...db.db import Database
from ...schemas.tables import TableCreate, TableUpdate

router = APIRouter(prefix="/tables", tags=["tables"])

TABLE_STATUSES = {"AVAILABLE", "OCCUPIED", "RESERVED"}


@router.post("", status_code=201)
def create_table(body: TableCreate, db: Database = Depends(get_db)):
    if body.status not in TABLE_STATUSES:
        raise HTTPException(status_code=400, detail="invalid table status")
    try:
        table_id = db.create_table(
            table_number=body.table_number, seats=body.seats, status=body.status
        )
    except Exception as exc:  # duplicate table number
        raise HTTPException(status_code=400, detail=str(exc))
    return db.get_table(table_id)


@router.get("")
def list_tables(db: Database = Depends(get_db)):
    return db.list_tables()


@router.get("/{table_id}")
def get_table(table_id: int, db: Database = Depends(get_db)):
    table = db.get_table(table_id)
    if not table:
        raise HTTPException(status_code=404, detail="table not found")
    return table


@router.patch("/{table_id}")
def update_table(table_id: int, body: TableUpdate, db: Database = Depends(get_db)):
    if not db.get_table(table_id):
        raise HTTPException(status_code=404, detail="table not found")
    fields = body.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] not in TABLE_STATUSES:
        raise HTTPException(status_code=400, detail="invalid table status")
    return db.update_table(table_id, fields)


@router.delete("/{table_id}", status_code=204)
def delete_table(table_id: int, db: Database = Depends(get_db)):
    if not db.get_table(table_id):
        raise HTTPException(status_code=404, detail="table not found")
    db.delete_table(table_id)
    return None
