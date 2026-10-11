"""RKB restaurant billing: family discount + taxes.

Billing rules:
- Family discount: 25% off when the bill subtotal is above $200.
- Taxes are charged on the discounted subtotal:
  GST 10%, state tax 6%, sales tax 4%.
"""
from ..db.db import Database
from .orders import OrderError, get_order_detail

FAMILY_DISCOUNT_THRESHOLD_CENTS = 20000  # $200
FAMILY_DISCOUNT_PERCENT = 25
GST_PERCENT = 10
STATE_TAX_PERCENT = 6
SALES_TAX_PERCENT = 4


def calculate_bill(db: Database, order_id: int) -> dict:
    """Return the full bill breakdown for an order.

    Raises OrderError(404) when the order does not exist.
    """
    order = get_order_detail(db, order_id)
    subtotal = order["total_cents"]

    discount_cents = 0
    if subtotal > FAMILY_DISCOUNT_THRESHOLD_CENTS:
        discount_cents = subtotal * FAMILY_DISCOUNT_PERCENT // 100

    taxable = subtotal - discount_cents
    gst = taxable * GST_PERCENT // 100
    state_tax = taxable * STATE_TAX_PERCENT // 100
    sales_tax = taxable * SALES_TAX_PERCENT // 100

    return {
        "order_id": order_id,
        "subtotal_cents": subtotal,
        "family_discount_applied": discount_cents > 0,
        "family_discount_percent": FAMILY_DISCOUNT_PERCENT,
        "family_discount_cents": discount_cents,
        "taxable_cents": taxable,
        "gst_percent": GST_PERCENT,
        "gst_cents": gst,
        "state_tax_percent": STATE_TAX_PERCENT,
        "state_tax_cents": state_tax,
        "sales_tax_percent": SALES_TAX_PERCENT,
        "sales_tax_cents": sales_tax,
        "total_cents": taxable + gst + state_tax + sales_tax,
    }
