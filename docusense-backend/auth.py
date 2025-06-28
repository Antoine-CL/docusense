import os
import requests
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from dotenv import load_dotenv

load_dotenv()

bearer = HTTPBearer()

# Azure AD configuration
TENANT_ID = os.getenv("AAD_TENANT_ID")
CLIENT_ID = os.getenv("AAD_CLIENT_ID")

if not TENANT_ID:
    print("⚠️  AAD_TENANT_ID not found in environment variables")
if not CLIENT_ID:
    print("⚠️  AAD_CLIENT_ID not found in environment variables")

# Azure AD endpoints - handle both v1.0 and v2.0
ISSUER_V1 = f"https://sts.windows.net/{TENANT_ID}/"
ISSUER_V2 = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
JWKS_URI_V1 = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/keys"
JWKS_URI_V2 = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

# Cache for JWKS keys - separate caches for v1.0 and v2.0
_jwks_cache_v1 = None
_jwks_cache_v2 = None

def get_jwks_for_issuer(issuer: str):
    """Get JSON Web Key Set from Azure AD based on issuer"""
    global _jwks_cache_v1, _jwks_cache_v2
    
    if issuer == ISSUER_V1:
        # v1.0 token - use v1.0 JWKS endpoint
        if _jwks_cache_v1 is None:
            try:
                print(f"🔍 Fetching JWKS from v1.0 endpoint: {JWKS_URI_V1}")
                response = requests.get(JWKS_URI_V1, timeout=10)
                response.raise_for_status()
                _jwks_cache_v1 = response.json()
                print("✅ v1.0 JWKS fetched successfully")
            except Exception as e:
                print(f"❌ Error fetching v1.0 JWKS: {e}")
                raise HTTPException(500, "Authentication service unavailable")
        return _jwks_cache_v1
    else:
        # v2.0 token - use v2.0 JWKS endpoint
        if _jwks_cache_v2 is None:
            try:
                print(f"🔍 Fetching JWKS from v2.0 endpoint: {JWKS_URI_V2}")
                response = requests.get(JWKS_URI_V2, timeout=10)
                response.raise_for_status()
                _jwks_cache_v2 = response.json()
                print("✅ v2.0 JWKS fetched successfully")
            except Exception as e:
                print(f"❌ Error fetching v2.0 JWKS: {e}")
                raise HTTPException(500, "Authentication service unavailable")
        return _jwks_cache_v2

def verify_token(token: str, required_scope: Optional[str] = None):
    """Verify JWT token from Azure AD"""
    try:
        # First, decode without verification to check the audience and issuer
        unverified_claims = jwt.get_unverified_claims(token)
        audience = unverified_claims.get("aud")
        issuer = unverified_claims.get("iss")
        
        if not issuer:
            print("❌ Token missing issuer claim")
            raise HTTPException(401, "Invalid token: missing issuer")
        
        print(f"🔍 Token audience: {audience}")
        print(f"🔍 Token issuer: {issuer}")
        print(f"🔍 Expected client ID: {CLIENT_ID}")
        print(f"🔍 ISSUER_V1: {ISSUER_V1}")
        print(f"🔍 ISSUER_V2: {ISSUER_V2}")
        
        # Determine which issuer to expect based on the token
        expected_issuer = ISSUER_V1 if issuer == ISSUER_V1 else ISSUER_V2
        print(f"🔍 Expected issuer: {expected_issuer}")
        print(f"🔍 Issuer match v1: {issuer == ISSUER_V1}")
        
        # Get the appropriate JWKS for this issuer
        print(f"🔍 Getting JWKS for issuer: {issuer}")
        jwks = get_jwks_for_issuer(issuer)
        print(f"🔍 JWKS keys count: {len(jwks.get('keys', []))}")
        
        # Handle different token types
        if audience == "https://graph.microsoft.com":
            # This is a Graph API token - validate differently
            print("📊 Detected Graph API token")
            # For Graph tokens, we can be more lenient with audience
            claims = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                issuer=expected_issuer,
                options={"verify_aud": False, "verify_iss": True}
            )
        elif audience == CLIENT_ID or audience == f"api://{CLIENT_ID}":
            # This is our custom API token
            print("🔑 Detected custom API token")
            claims = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                issuer=expected_issuer,
                audience=audience,
                options={"verify_aud": True, "verify_iss": True}
            )
        else:
            print(f"❌ Unexpected audience: {audience}")
            raise HTTPException(401, f"Invalid token audience: {audience}")
        
        # Check scopes/roles if required (client-credentials tokens have roles, not scp)
        if required_scope and audience != "https://graph.microsoft.com":
            scopes = claims.get("scp", "").split() if claims.get("scp") else []
            roles = claims.get("roles", [])
            all_permissions = scopes + roles
            
            if required_scope not in all_permissions:
                print(f"❌ Missing required scope: {required_scope}")
                print(f"🔍 Available scopes: {scopes}")
                print(f"🔍 Available roles: {roles}")
                raise HTTPException(403, f"Missing required scope or role: {required_scope}")
        
        print("✅ Token verified successfully")
        return claims
        
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