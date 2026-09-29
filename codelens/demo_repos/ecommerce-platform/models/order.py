"""
models/order.py - Order entity schema, line items, and state machine transitions.
"""

ALLOWED_TRANSITIONS = {
    "PENDING": {"PAID", "CANCELLED"},
    "PAID": {"PROCESSING", "REFUNDED"},
    "PROCESSING": {"SHIPPED"},
    "SHIPPED": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
    "REFUNDED": set(),
}


def transition_order_state(current: str, next_state: str) -> str:
    """Enforce strict order state machine transitions."""
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if next_state not in allowed:
        raise ValueError(f"Illegal order transition {current} -> {next_state}")
    return next_state


def build_order(order_id: str, line_items: list[dict]) -> dict:
    """Create an order entity in PENDING state with line items."""
    return {
        "order_id": order_id,
        "status": "PENDING",
        "line_items": line_items,
        "created_at": None,
    }
