import os
import requests
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer
from jose import jwt
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

def validate_token_with_userinfo(token: str) -> Dict[str, Any]:
    """Validate token by calling Microsoft Graph userinfo endpoint"""
    try:
        print("🔍 Validating token with Microsoft Graph...")
        
        # Call Microsoft Graph to validate the token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Try Graph API me endpoint first
        response = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_info = response.json()
            print("✅ Token validated successfully via Graph API")
            
            # Also get the token claims without signature verification
            try:
                claims = jwt.get_unverified_claims(token)
                print(f"🔍 Token claims extracted")
                
                # Combine user info with token claims
                result = {
                    **claims,
                    "graph_user_info": user_info,
                    "validation_method": "graph_api"
                }
                return result
                
            except Exception as e:
                print(f"⚠️  Could not extract claims: {e}")
                # Return just the user info if claims extraction fails
                return {
                    "sub": user_info.get("id"),
                    "name": user_info.get("displayName"),
                    "email": user_info.get("mail") or user_info.get("userPrincipalName"),
                    "graph_user_info": user_info,
                    "validation_method": "graph_api_only"
                }
        
        elif response.status_code == 401:
            print(f"❌ Token validation failed: {response.status_code}")
            raise HTTPException(401, "Invalid or expired token")
        else:
            print(f"❌ Unexpected response from Graph API: {response.status_code}")
            raise HTTPException(401, f"Token validation failed: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error during token validation: {e}")
        raise HTTPException(503, "Authentication service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Unexpected error during token validation: {e}")
        raise HTTPException(401, "Token validation failed")

def validate_token_hybrid(token: str, required_scope: Optional[str] = None) -> Dict[str, Any]:
    """Hybrid validation: extract claims without signature verification + validate with Graph API"""
    try:
        print("🔍 Starting hybrid token validation...")
        
        # First, extract claims without signature verification
        claims = jwt.get_unverified_claims(token)
        header = jwt.get_unverified_header(token)
        
        audience = claims.get("aud")
        issuer = claims.get("iss")
        app_id = claims.get("appid")
        
        print(f"🔍 Token audience: {audience}")
        print(f"🔍 Token issuer: {issuer}")
        print(f"🔍 Token app_id: {app_id}")
        
        # Basic validation of claims
        if not issuer or not issuer.startswith("https://sts.windows.net/"):
            print("❌ Invalid issuer")
            raise HTTPException(401, "Invalid token issuer")
        
        # Check if token is expired (basic check)
        import time
        exp = claims.get("exp")
        if exp and exp < time.time():
            print("❌ Token expired")
            raise HTTPException(401, "Token expired")
        
        # Validate with Microsoft Graph if it's a Graph token
        if audience == "https://graph.microsoft.com":
            print("📊 Graph API token - validating with Microsoft Graph...")
            try:
                headers = {"Authorization": f"Bearer {token}"}
                response = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=5)
                
                if response.status_code == 200:
                    print("✅ Token validated with Microsoft Graph")
                    claims["graph_validation"] = "success"
                    claims["graph_user_info"] = response.json()
                else:
                    print(f"⚠️  Graph validation failed: {response.status_code}")
                    claims["graph_validation"] = "failed"
            except Exception as e:
                print(f"⚠️  Could not validate with Graph: {e}")
                claims["graph_validation"] = "error"
        
        # Check scopes/roles if required
        if required_scope:
            scopes = claims.get("scp", "").split() if claims.get("scp") else []
            roles = claims.get("roles", [])
            all_permissions = scopes + roles
            
            if required_scope not in all_permissions:
                print(f"❌ Missing required scope: {required_scope}")
                print(f"🔍 Available scopes: {scopes}")
                print(f"🔍 Available roles: {roles}")
                raise HTTPException(403, f"Missing required scope or role: {required_scope}")
        
        print("✅ Hybrid token validation successful")
        claims["validation_method"] = "hybrid"
        return claims
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Hybrid validation error: {e}")
        raise HTTPException(401, "Token validation failed")

async def simple_auth_dependency(request: Request):
    """Simple authentication using Graph API validation"""
    try:
        credentials = await bearer(request)
        if credentials is None:
            raise HTTPException(401, "No credentials provided")
        claims = validate_token_with_userinfo(credentials.credentials)
        return claims
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        raise HTTPException(401, "Authentication failed")

async def hybrid_auth_dependency(request: Request):
    """Hybrid authentication with claims extraction + optional Graph validation"""
    try:
        credentials = await bearer(request)
        if credentials is None:
            raise HTTPException(401, "No credentials provided")
        claims = validate_token_hybrid(credentials.credentials, required_scope=None)
        return claims
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        raise HTTPException(401, "Authentication failed") 