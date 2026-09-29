"""
services/ratelimit.py - Sliding window counter for IP throttling and lockout enforcement.
"""
import time

_ATTEMPTS: dict[str, list[float]] = {}


def record_failed_attempt(ip_address: str) -> int:
    """Record a failed credential attempt and return the attempt count in the window."""
    now = time.time()
    window = [t for t in _ATTEMPTS.get(ip_address, []) if now - t < 300]
    window.append(now)
    _ATTEMPTS[ip_address] = window
    return len(window)


def is_ip_locked(ip_address: str, max_attempts: int = 5) -> bool:
    """Return True when brute-force rate limiting should lock out an IP."""
    return record_failed_attempt(ip_address) >= max_attempts
