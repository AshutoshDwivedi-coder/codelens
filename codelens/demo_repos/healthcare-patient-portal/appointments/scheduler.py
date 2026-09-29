"""
appointments/scheduler.py - Physician calendar availability and double-booking prevention.
"""

_BOOKINGS: dict[str, set[str]] = {}


def find_open_slots(physician_id: str, day: str, booked: set[str] | None = None) -> list[str]:
    """Resolve physician calendar booking slots that are still available."""
    all_slots = [f"{hour:02d}:00" for hour in range(9, 17)]
    taken = booked if booked is not None else _BOOKINGS.get(f"{physician_id}:{day}", set())
    return [s for s in all_slots if s not in taken]


def book_appointment(physician_id: str, day: str, slot: str) -> bool:
    """Book a slot while preventing double booking conflicts."""
    key = f"{physician_id}:{day}"
    taken = _BOOKINGS.setdefault(key, set())
    if slot in taken:
        return False
    taken.add(slot)
    return True
