"""Menu item endpoints (CRUD)."""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_db
from ...db.db import Database
from ...schemas.menu import MenuItemCreate, MenuItemUpdate

router = APIRouter(prefix="/menu", tags=["menu"])


@router.post("", status_code=201)
def create_menu_item(body: MenuItemCreate, db: Database = Depends(get_db)):
    try:
        item_id = db.create_menu_item(
            name=body.name,
            price_cents=body.price_cents,
            expected_prep_minutes=body.expected_prep_minutes,
            category=body.category,
            is_available=1 if body.is_available else 0,
        )
    except Exception as exc:  # duplicate name
        raise HTTPException(status_code=400, detail=str(exc))
    return db.get_menu_item(item_id)


@router.get("")
def list_menu_items(available_only: bool = False, db: Database = Depends(get_db)):
    return db.list_menu_items(available_only=available_only)


@router.get("/{item_id}")
def get_menu_item(item_id: int, db: Database = Depends(get_db)):
    item = db.get_menu_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="menu item not found")
    return item


@router.patch("/{item_id}")
def update_menu_item(item_id: int, body: MenuItemUpdate, db: Database = Depends(get_db)):
    if not db.get_menu_item(item_id):
        raise HTTPException(status_code=404, detail="menu item not found")
    fields = body.model_dump(exclude_unset=True)
    if "is_available" in fields:
        fields["is_available"] = 1 if fields["is_available"] else 0
    return db.update_menu_item(item_id, fields)


@router.delete("/{item_id}", status_code=204)
def delete_menu_item(item_id: int, db: Database = Depends(get_db)):
    if not db.get_menu_item(item_id):
        raise HTTPException(status_code=404, detail="menu item not found")
    db.delete_menu_item(item_id)
    return None
