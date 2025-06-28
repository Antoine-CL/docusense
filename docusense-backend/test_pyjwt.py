#!/usr/bin/env python3

import jwt
import requests
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from graph_client import graph_client
import os
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("AAD_TENANT_ID")

def test_pyjwt_verification():
    """Test JWT verification using PyJWT instead of python-jose"""
    print("🧪 Testing PyJWT verification...")
    
    # Get token
    token = graph_client.get_token()
    if not token:
        print("❌ Failed to get token")
        return
    
    # Get token header and claims
    header = jwt.get_unverified_header(token)
    payload = jwt.decode(token, options={"verify_signature": False})
    kid = header.get('kid')
    
    print(f"🆔 Token Key ID: {kid}")
    print(f"🔍 Token Issuer: {payload.get('iss')}")
    print(f"🔍 Token Audience: {payload.get('aud')}")
    
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
        
        # Convert JWK to PEM format for PyJWT
        print(f"\n🔑 Converting JWK to RSA public key...")
        try:
            # Extract RSA components
            n = jwt.utils.base64url_decode(target_key['n'])
            e = jwt.utils.base64url_decode(target_key['e'])
            
            # Convert to integers
            n_int = int.from_bytes(n, byteorder='big')
            e_int = int.from_bytes(e, byteorder='big')
            
            # Create RSA public key
            public_key = rsa.RSAPublicNumbers(e_int, n_int).public_key()
            
            # Convert to PEM format
            pem_key = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            print("✅ RSA public key created successfully")
            
        except Exception as e:
            print(f"❌ Error creating RSA key: {e}")
            return
        
        # Test verification with PyJWT
        print(f"\n🧪 Testing PyJWT verification...")
        try:
            decoded = jwt.decode(
                token,
                pem_key,
                algorithms=["RS256"],
                issuer=payload.get('iss'),
                options={
                    "verify_aud": False,  # Skip audience verification for Graph tokens
                    "verify_iss": True,
                    "verify_signature": True
                }
            )
            print("✅ PyJWT verification SUCCESS!")
            print(f"🎉 Decoded claims: {json.dumps(decoded, indent=2)}")
            return decoded
            
        except jwt.InvalidSignatureError:
            print("❌ PyJWT: Invalid signature")
        except jwt.InvalidIssuerError:
            print("❌ PyJWT: Invalid issuer")
        except jwt.ExpiredSignatureError:
            print("❌ PyJWT: Token expired")
        except jwt.InvalidTokenError as e:
            print(f"❌ PyJWT: Invalid token - {e}")
        except Exception as e:
            print(f"❌ PyJWT: Unexpected error - {e}")
            
    except Exception as e:
        print(f"❌ Error fetching JWKS: {e}")

if __name__ == "__main__":
    test_pyjwt_verification() 