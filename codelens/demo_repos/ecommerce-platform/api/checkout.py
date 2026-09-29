"""
api/checkout.py - Checkout session initialization and inventory locking.
"""
from services.cart import calculate_cart_total
from services.inventory import reserve_sku_quantity


def initialize_checkout_session(user_id: str, cart_items: list[dict]) -> dict:
    """Create a checkout session and lock inventory for each cart line item."""
    reservations = []
    for item in cart_items:
        ok = reserve_sku_quantity(item["sku"], item["quantity"], ttl_seconds=900)
        if not ok:
            raise RuntimeError(f"Unable to reserve inventory for SKU {item['sku']}")
        reservations.append(item["sku"])

    totals = calculate_cart_total(cart_items, coupon_code=None)
    return {
        "session_id": f"chk_{user_id}",
        "status": "PENDING",
        "reservations": reservations,
        "totals": totals,
    }
