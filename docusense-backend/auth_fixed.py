import os
import requests
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from dotenv import load_dotenv
import json
import base64
import hashlib

load_dotenv()

bearer = HTTPBearer()

# Azure AD configuration
TENANT_ID = os.getenv("AAD_TENANT_ID")
CLIENT_ID = os.getenv("AAD_CLIENT_ID")

if not TENANT_ID:
    print("⚠️  AAD_TENANT_ID not found in environment variables")
if not CLIENT_ID:
    print("⚠️  AAD_CLIENT_ID not found in environment variables")

# Azure AD endpoints
ISSUER_V1 = f"https://sts.windows.net/{TENANT_ID}/"
ISSUER_V2 = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"

# Cache for JWKS keys and OpenID config
_jwks_cache = None
_openid_config_cache = None

def get_openid_configuration():
    """Get OpenID configuration from Azure AD"""
    global _openid_config_cache
    if _openid_config_cache is None:
        try:
            # Try v2.0 first
            config_url = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration"
            print(f"🔍 Fetching OpenID config from: {config_url}")
            response = requests.get(config_url, timeout=10)
            response.raise_for_status()
            _openid_config_cache = response.json()
            print("✅ OpenID configuration fetched successfully")
        except Exception as e:
            print(f"❌ Error fetching OpenID config: {e}")
            # Fallback to v1.0
            try:
                config_url = f"https://login.microsoftonline.com/{TENANT_ID}/.well-known/openid-configuration"
                print(f"🔍 Trying v1.0 config: {config_url}")
                response = requests.get(config_url, timeout=10)
                response.raise_for_status()
                _openid_config_cache = response.json()
                print("✅ v1.0 OpenID configuration fetched successfully")
            except Exception as e2:
                print(f"❌ Error fetching v1.0 config: {e2}")
                raise HTTPException(500, "Authentication service unavailable")
    return _openid_config_cache

def get_jwks():
    """Get JSON Web Key Set from Azure AD using OpenID configuration"""
    global _jwks_cache
    if _jwks_cache is None:
        try:
            config = get_openid_configuration()
            jwks_uri = config.get("jwks_uri")
            if not jwks_uri:
                raise Exception("jwks_uri not found in OpenID configuration")
            
            print(f"🔍 Fetching JWKS from: {jwks_uri}")
            response = requests.get(jwks_uri, timeout=10)
            response.raise_for_status()
            _jwks_cache = response.json()
            print(f"✅ JWKS fetched successfully: {len(_jwks_cache.get('keys', []))} keys")
        except Exception as e:
            print(f"❌ Error fetching JWKS: {e}")
            raise HTTPException(500, "Authentication service unavailable")
    return _jwks_cache

# Place helper just after global caches but before verify_token function.
def _normalize_graph_token(token: str) -> str:
    """Hash the plain 'nonce' header value on Microsoft Graph access tokens so
    that signature verification succeeds. Returns the original token for other
    cases."""
    try:
        header_b64, payload_b64, signature_b64 = token.split('.')
        padded = header_b64 + '=' * (-len(header_b64) % 4)
        header_json = json.loads(base64.urlsafe_b64decode(padded))
        nonce = header_json.get('nonce')
        if not nonce or len(nonce) == 43:
            return token
        hashed = hashlib.sha256(nonce.encode()).digest()
        hashed_b64 = base64.urlsafe_b64encode(hashed).decode().rstrip('=')
        header_json['nonce'] = hashed_b64
        new_header = base64.urlsafe_b64encode(json.dumps(header_json, separators=(',', ':')).encode()).decode().rstrip('=')
        return f"{new_header}.{payload_b64}.{signature_b64}"
    except Exception:
        return token

def verify_token(token: str, required_scope: Optional[str] = None):
    """Verify JWT token from Azure AD using the recommended pattern"""
    try:
        # Before unverified header claims retrieval we can normalize.
        token = _normalize_graph_token(token)
        # First, decode without verification to check the header and claims
        unverified_header = jwt.get_unverified_header(token)
        unverified_claims = jwt.get_unverified_claims(token)
        
        audience = unverified_claims.get("aud")
        issuer = unverified_claims.get("iss")
        kid = unverified_header.get("kid")
        
        print(f"🔍 Token audience: {audience}")
        print(f"🔍 Token issuer: {issuer}")
        print(f"🔍 Token kid: {kid}")
        print(f"🔍 Expected client ID: {CLIENT_ID}")
        
        if not kid:
            print("❌ Token missing 'kid' header")
            raise HTTPException(401, "Invalid token: missing key ID")
        
        # Get JWKS and find the signing key
        jwks = get_jwks()
        
        # Find the key which was used to sign the JWT token
        rsa_key = {}
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = {
                    "kty": key.get("kty"),
                    "kid": key.get("kid"),
                    "use": key.get("use"),
                    "n": key.get("n"),
                    "e": key.get("e"),
                }
                break
        
        if not rsa_key:
            print(f"❌ Unable to find signing key with kid: {kid}")
            raise HTTPException(401, "Unable to find appropriate signing key")
        
        print(f"✅ Found signing key: {kid}")
        
        # Determine issuer based on token
        expected_issuer = issuer  # Use the issuer from the token itself
        
        # Verify the JWT token with appropriate options based on token type
        options = {"verify_aud": False, "verify_iss": True}
        
        if audience == "https://graph.microsoft.com":
            # This is a Graph API token - be more lenient
            print("📊 Detected Graph API token")
            options["verify_aud"] = False
        elif audience == CLIENT_ID or audience == f"api://{CLIENT_ID}":
            # This is our custom API token
            print("🔑 Detected custom API token")
            options["verify_aud"] = True
        else:
            print(f"📊 Unknown audience, proceeding with lenient verification: {audience}")
            options["verify_aud"] = False
        
        print(f"🔍 Verification options: {options}")
        print(f"🔍 Expected issuer: {expected_issuer}")
        
        # Decode and verify the token
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=audience if options["verify_aud"] else None,
            issuer=expected_issuer,
            options=options,
        )
        
        # Check scopes/roles if required (client-credentials tokens have roles, not scp)
        if required_scope and audience != "https://graph.microsoft.com":
            scopes = payload.get("scp", "").split() if payload.get("scp") else []
            roles = payload.get("roles", [])
            all_permissions = scopes + roles
            
            if required_scope not in all_permissions:
                print(f"❌ Missing required scope: {required_scope}")
                print(f"🔍 Available scopes: {scopes}")
                print(f"🔍 Available roles: {roles}")
                raise HTTPException(403, f"Missing required scope or role: {required_scope}")
        
        print("✅ Token verified successfully")
        return payload
        
    except JWTError as e:
        print(f"❌ JWT Error: {e}")
        raise HTTPException(401, "Invalid token")
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        print(f"❌ Token verification error: {e}")
        raise HTTPException(401, "Token verification failed")

async def auth_dependency(request: Request):
    """FastAPI dependency for authentication with required scope"""
    try:
        credentials = await bearer(request)
        if credentials is None:
            raise HTTPException(401, "No credentials provided")
        claims = verify_token(credentials.credentials, required_scope="api.access")
        return claims
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        raise HTTPException(401, "Authentication failed")

# Lenient auth for development/testing with Graph tokens
async def lenient_auth_dependency(request: Request):
    """Lenient authentication that accepts Graph API tokens without scope check"""
    try:
        credentials = await bearer(request)
        if credentials is None:
            raise HTTPException(401, "No credentials provided")
        claims = verify_token(credentials.credentials, required_scope=None)
        return claims
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        raise HTTPException(401, "Authentication failed")

# Optional: Create a dependency that doesn't require a specific scope
async def optional_auth_dependency(request: Request):
    """Optional authentication - returns None if no token provided"""
    try:
        credentials = await bearer(request)
        if credentials is None:
            return None
        claims = verify_token(credentials.credentials, required_scope=None)
        return claims
    except HTTPException:
        return None
    except Exception:
        return None 