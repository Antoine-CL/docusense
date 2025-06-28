import os
import time
from typing import Optional
import json
import base64
import hashlib

from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer
from jwt import PyJWKClient, decode, InvalidTokenError
from dotenv import load_dotenv
import jwt

load_dotenv()

# Azure AD tenant & client information
TENANT_ID: str = os.getenv("AAD_TENANT_ID", "")
CLIENT_ID: str = os.getenv("AAD_CLIENT_ID", "")

if not TENANT_ID:
    print("⚠️  AAD_TENANT_ID environment variable missing – auth will fail")
if not CLIENT_ID:
    print("⚠️  AAD_CLIENT_ID environment variable missing – auth will fail")

# v2.0 issuer & JWKS endpoint
ISSUER = f"https://sts.windows.net/{TENANT_ID}/"
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/keys?api-version=1.0"

jwk_client = PyJWKClient(JWKS_URL)

bearer_scheme = HTTPBearer()

# ---------------------------------------------------------------------------
# Helper: normalise Microsoft Graph tokens (hash 'nonce' header)
# ---------------------------------------------------------------------------

def _normalize_graph_token(token: str) -> str:
    """For Microsoft Graph access tokens the 'nonce' header arrives in plain text.
    Azure AD internally hashes this value before signing, therefore the plain
    token will always fail signature verification.  The fix is to SHA-256 hash
    the nonce value, base64-url encode it (without padding) and replace it in
    the JWT header before running signature validation.

    If the token is already in the correct format (nonce already hashed) we
    return it unchanged so it is safe to call on any Graph token.
    """
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        # Ensure proper padding for decode
        padded_header = header_b64 + "=" * (-len(header_b64) % 4)
        header_json = json.loads(base64.urlsafe_b64decode(padded_header))

        nonce = header_json.get("nonce")
        if not nonce:
            return token  # nothing to fix

        # Heuristic: hashed nonce is 43 chars (SHA256 => 32 bytes => 43 base64url chars)
        if len(nonce) == 43:
            return token  # already hashed

        # Compute SHA256 hash and base64-url encode (no padding)
        hashed = hashlib.sha256(nonce.encode()).digest()
        hashed_b64 = base64.urlsafe_b64encode(hashed).decode().rstrip("=")
        header_json["nonce"] = hashed_b64

        # Re-encode header
        new_header_b64 = base64.urlsafe_b64encode(
            json.dumps(header_json, separators=(",", ":")).encode()
        ).decode().rstrip("=")

        # Rebuild token
        return f"{new_header_b64}.{payload_b64}.{signature_b64}"
    except Exception:
        # If anything goes wrong fall back to original token; verification may fail later
        return token

# ---------------------------------------------------------------------------
# Core verifier
# ---------------------------------------------------------------------------

def verify_token(token: str, required_role: Optional[str] = None):
    """Verify Azure AD v1.0 access-token and return its claims."""
    try:
        # Normalize Microsoft Graph tokens
        token = _normalize_graph_token(token)

        # Locate signing key by kid
        signing_key = jwk_client.get_signing_key_from_jwt(token).key

        # Validate signature & issuer (skip audience for app-only Graph token)
        claims = decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=ISSUER,
            options={"verify_aud": False},
        )

        # Expiry check (PyJWT already enforces, but emit clearer message)
        if claims.get("exp", 0) < time.time():
            raise HTTPException(401, "Token expired")

        # Check for required permission in either roles (app-only) or scopes (delegated)
        if required_role:
            allowed = set(claims.get("roles", [])) | set(claims.get("scp", "").split())
            if "api.access" not in allowed and "api.role" not in allowed:
                raise HTTPException(403, "Missing permission")

        return claims

    except InvalidTokenError as err:
        print(f"❌ JWT validation error: {err}")
        raise HTTPException(401, "Invalid token")

# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def auth_dependency(request: Request):
    credentials = await bearer_scheme(request)
    if credentials is None:
        raise HTTPException(401, "No credentials provided")
    return verify_token(credentials.credentials, required_role="api.access")


async def lenient_auth_dependency(request: Request):
    credentials = await bearer_scheme(request)
    if credentials is None:
        raise HTTPException(401, "No credentials provided")
    return verify_token(credentials.credentials)


async def optional_auth_dependency(request: Request):
    try:
        credentials = await bearer_scheme(request)
    except Exception:
        return None
    if credentials is None:
        return None
    try:
        return verify_token(credentials.credentials)
    except HTTPException:
        return None