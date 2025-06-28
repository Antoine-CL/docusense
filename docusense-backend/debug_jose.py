#!/usr/bin/env python3

import requests
import json
from jose import jwt, jwk
from jose.backends import RSAKey
from graph_client import graph_client
import os
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("AAD_TENANT_ID")

def debug_jose_verification():
    """Debug jose JWT verification step by step"""
    print("🔍 Debugging Jose JWT Verification...")
    
    # Get token
    token = graph_client.get_token()
    if not token:
        print("❌ Failed to get token")
        return
    
    # Get token header and claims
    header = jwt.get_unverified_header(token)
    claims = jwt.get_unverified_claims(token)
    kid = header.get('kid')
    
    print(f"🆔 Token Key ID: {kid}")
    print(f"🔍 Token Issuer: {claims.get('iss')}")
    print(f"🔍 Token Audience: {claims.get('aud')}")
    
    # Fetch JWKS
    jwks_url = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/keys"
    print(f"\n🔍 Fetching JWKS from: {jwks_url}")
    
    try:
        response = requests.get(jwks_url)
        response.raise_for_status()
        jwks_data = response.json()
        
        print(f"✅ JWKS fetched: {len(jwks_data.get('keys', []))} keys")
        
        # Find the specific key for our token
        target_key = None
        for key_data in jwks_data.get('keys', []):
            if key_data.get('kid') == kid:
                target_key = key_data
                break
        
        if not target_key:
            print(f"❌ Key with kid '{kid}' not found in JWKS")
            return
        
        print(f"✅ Found matching key:")
        print(f"   - kid: {target_key.get('kid')}")
        print(f"   - kty: {target_key.get('kty')}")
        print(f"   - use: {target_key.get('use')}")
        print(f"   - alg: {target_key.get('alg')}")
        
        # Try different verification approaches
        print(f"\n🧪 Testing verification approaches...")
        
        # Approach 1: Using JWKS directly (current approach)
        print(f"\n1️⃣ Testing with full JWKS...")
        try:
            decoded = jwt.decode(
                token,
                jwks_data,
                algorithms=["RS256"],
                issuer=claims.get('iss'),
                options={"verify_aud": False, "verify_iss": True}
            )
            print("✅ Approach 1 SUCCESS!")
            return decoded
        except Exception as e:
            print(f"❌ Approach 1 failed: {e}")
        
        # Approach 2: Using specific key
        print(f"\n2️⃣ Testing with specific key...")
        try:
            decoded = jwt.decode(
                token,
                target_key,
                algorithms=["RS256"],
                issuer=claims.get('iss'),
                options={"verify_aud": False, "verify_iss": True}
            )
            print("✅ Approach 2 SUCCESS!")
            return decoded
        except Exception as e:
            print(f"❌ Approach 2 failed: {e}")
        
        # Approach 3: Construct RSA key manually
        print(f"\n3️⃣ Testing with manual RSA key construction...")
        try:
            # Create RSA key from JWK
            rsa_key = jwk.construct(target_key)
            decoded = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                issuer=claims.get('iss'),
                options={"verify_aud": False, "verify_iss": True}
            )
            print("✅ Approach 3 SUCCESS!")
            return decoded
        except Exception as e:
            print(f"❌ Approach 3 failed: {e}")
        
        # Approach 4: No issuer verification
        print(f"\n4️⃣ Testing without issuer verification...")
        try:
            decoded = jwt.decode(
                token,
                jwks_data,
                algorithms=["RS256"],
                options={"verify_aud": False, "verify_iss": False}
            )
            print("✅ Approach 4 SUCCESS!")
            return decoded
        except Exception as e:
            print(f"❌ Approach 4 failed: {e}")
            
    except Exception as e:
        print(f"❌ Error fetching JWKS: {e}")

if __name__ == "__main__":
    result = debug_jose_verification()
    if result:
        print(f"\n🎉 Final result: {result}") 