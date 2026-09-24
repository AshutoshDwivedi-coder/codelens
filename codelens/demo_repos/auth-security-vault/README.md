# Vault Security & Identity Microservice

Enterprise authentication and authorization gateway featuring OAuth2 PKCE, JWT RS256 token rotation, Argon2 password hashing, and role-based access control (RBAC).

## Key Features

- **OAuth2 PKCE Flow**: Secures public clients and single-page applications against authorization code interception attacks.
- **JWT RS256 Key Rotation**: Generates asymmetric cryptographically signed tokens with automated 24-hour key rollover and JWKS endpoints.
- **Argon2id Password Hashing**: Utilizes memory-hard password hashing parameters resistant to GPU/ASIC cracking.
- **Role-Based Access Control (RBAC)**: Fine-grained permissions middleware evaluating user roles, tenant scopes, and resource actions.
- **Brute-Force Rate Limiting**: Exponential backoff and IP-based lockout after repeated failed credential attempts.

## System Architecture & Modules

- `auth/jwt_handler.py`: Asymmetric RS256 token issuance, signature verification, and JWKS cache.
- `auth/oauth_pkce.py`: OAuth2 code challenge verifier and authorization code exchange.
- `security/argon_hasher.py`: Argon2id password hashing and constant-time credential comparison.
- `middleware/rbac.py`: FastAPI authorization middleware inspecting JWT claims against route scopes.
- `services/ratelimit.py`: Sliding window counter for IP throttling and lockout enforcement.

## Questions to Ask this Codebase

- Where is the RS256 JWT token generation and verification implemented in `auth/jwt_handler.py`?
- How does the OAuth2 PKCE code challenge verification work in `auth/oauth_pkce.py`?
- Where is Argon2id password hashing configured in `security/argon_hasher.py`?
- How does the RBAC middleware intercept unauthorized requests in `middleware/rbac.py`?
- Where is the brute force IP rate limiting logic handled in `services/ratelimit.py`?
- How are cryptographic key rotations and JWKS endpoints refreshed?
