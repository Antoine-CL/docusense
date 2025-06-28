import os
import time
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer
from jwt import PyJWKClient, decode, InvalidTokenError
from dotenv import load_dotenv

load_dotenv()

# HTTP bearer extractor
bearer_scheme = HTTPBearer()

# Azure AD / Microsoft Entra IDs
TENANT_ID = os.getenv("AAD_TENANT_ID")
CLIENT_ID = os.getenv("AAD_CLIENT_ID")
if not TENANT_ID:
    print("⚠️  AAD_TENANT_ID not set – authentication will fail!")
if not CLIENT_ID:
    print("⚠️  AAD_CLIENT_ID not set – authentication will fail!")

# v2.0 OpenID metadata / JWKS endpoint
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
ISSUER_V2 = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"

# Initialise JWK client once – thread-safe
jwk_client = PyJWKClient(JWKS_URL)


# ---------------------------------------------------------------------------
# Core verification helper
# ---------------------------------------------------------------------------

def _verify_jwt(token: str, required_role: Optional[str] | None = None):
    """Return claims dict after successful validation or raise HTTPException."""

    try:
        # Fetch signing key that matches the token's kid in one network call (cached)
        signing_key = jwk_client.get_signing_key_from_jwt(token).key

        # Decode & validate signature, issuer and (optionally) audience
        # Audience rules:
        #   – Graph tokens (aud = https://graph.microsoft.com) → verify_aud True
        #   – Custom API tokens  (aud = api://<guid>)          → verify_aud True
        # For Graph tokens we pass the actual aud string that is inside the token.
        import jwt  # local import to avoid top-level conflicts
        unverified = jwt.decode(token, options={"verify_signature": False}, algorithms=["RS256"])
        audience_claim = unverified.get("aud")

        claims = decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=audience_claim,
            issuer=ISSUER_V2,
        )

        # Explicit expiry check (PyJWT already does it, but we emit a clearer error)
        if claims.get("exp", 0) < time.time():
            raise HTTPException(401, "Token expired")

        # Role / scope enforcement (client-credentials tokens carry `roles`)
        if required_role:
            token_roles = claims.get("roles", [])
            if required_role not in token_roles:
                raise HTTPException(403, f"Missing role: {required_role}")

        return claims

    except InvalidTokenError as err:
        # Signature, issuer, audience, or other validation error
        print(f"❌ JWT validation error: {err}")
        raise HTTPException(401, "Invalid token")


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def auth_dependency(request: Request):
    """Require valid Azure AD token that contains role `api.access`."""
    credentials = await bearer_scheme(request)
    if not credentials:
        raise HTTPException(401, "Missing credentials")
    return _verify_jwt(credentials.credentials, required_role="api.access")


async def lenient_auth_dependency(request: Request):
    """Validate token signature/issuer only (no role enforced)."""
    credentials = await bearer_scheme(request)
    if not credentials:
        raise HTTPException(401, "Missing credentials")
    return _verify_jwt(credentials.credentials, required_role=None)


async def optional_auth_dependency(request: Request):
    """Return claims if a valid token is supplied, else None (for public endpoints)."""
    try:
        credentials = await bearer_scheme(request)
    except Exception:
        return None
    if not credentials:
        return None
    try:
        return _verify_jwt(credentials.credentials, required_role=None)
    except HTTPException:
        return None 