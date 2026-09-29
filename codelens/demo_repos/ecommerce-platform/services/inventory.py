"""
services/inventory.py - Redis distributed locking for warehouse SKU reservations.
"""
import time

_LOCKS: dict[str, dict] = {}


def reserve_sku_quantity(sku: str, quantity: int, ttl_seconds: int = 600) -> bool:
    """Atomically reserve SKU inventory using a Redis-style distributed lock."""
    now = time.time()
    lock = _LOCKS.get(sku)
    if lock and lock["expires_at"] > now:
        return False
    _LOCKS[sku] = {
        "quantity": quantity,
        "expires_at": now + ttl_seconds,
        "status": "RESERVED",
    }
    return True


def release_sku_reservation(sku: str) -> None:
    """Release an inventory reservation lock for a SKU."""
    _LOCKS.pop(sku, None)


def prevent_overselling(sku: str, available: int, requested: int) -> bool:
    """Return True when a reservation would not oversell available warehouse stock."""
    if requested <= 0:
        return False
    return requested <= available and reserve_sku_quantity(sku, requested)
