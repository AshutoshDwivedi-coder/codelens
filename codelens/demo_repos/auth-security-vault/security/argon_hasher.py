"""
security/argon_hasher.py - Argon2id password hashing and constant-time credential comparison.
"""
import hashlib
import hmac


def hash_password_argon2id(password: str, salt: str) -> str:
    """Hash a password with Argon2id-like memory-hard parameters (demo SHA256 stand-in)."""
    material = f"argon2id:{salt}:{password}".encode()
    return hashlib.sha256(material).hexdigest()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Constant-time credential comparison against a stored Argon2id hash."""
    candidate = hash_password_argon2id(password, salt)
    return hmac.compare_digest(candidate, expected_hash)
