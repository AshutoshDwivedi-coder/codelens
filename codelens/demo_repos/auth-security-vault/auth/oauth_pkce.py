"""
auth/oauth_pkce.py - OAuth2 PKCE code challenge verifier and authorization code exchange.
"""
import hashlib
import base64


def create_code_challenge(code_verifier: str) -> str:
    """Create S256 code_challenge from a high-entropy code_verifier."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify_pkce_challenge(code_verifier: str, code_challenge: str) -> bool:
    """Verify OAuth2 PKCE code challenge against the original verifier."""
    expected = create_code_challenge(code_verifier)
    return expected == code_challenge


def exchange_authorization_code(code: str, code_verifier: str, code_challenge: str) -> dict:
    """Exchange an authorization code for tokens after PKCE verification."""
    if not verify_pkce_challenge(code_verifier, code_challenge):
        raise PermissionError("PKCE verification failed")
    return {"access_token": f"atk_{code}", "token_type": "Bearer", "expires_in": 3600}
