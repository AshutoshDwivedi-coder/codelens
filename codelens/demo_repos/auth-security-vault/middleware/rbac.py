"""
middleware/rbac.py - FastAPI authorization middleware inspecting JWT claims against route scopes.
"""


def evaluate_rbac(roles: list[str], required_scope: str, tenant: str | None = None) -> bool:
    """Evaluate role-based access control for a request route scope."""
    if "admin" in roles:
        return True
    normalized = {r.lower() for r in roles}
    scope = required_scope.lower()
    if scope in normalized:
        return True
    if tenant and f"{tenant}:{scope}" in normalized:
        return True
    return False


def intercept_unauthorized(roles: list[str], required_scope: str) -> None:
    """Raise when RBAC middleware detects an unauthorized request."""
    if not evaluate_rbac(roles, required_scope):
        raise PermissionError(f"Unauthorized for scope {required_scope}")
