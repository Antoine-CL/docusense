#!/usr/bin/env python3

import requests
import json
from jose import jwt
from graph_client import graph_client
import os
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("AAD_TENANT_ID")

def debug_jwks_and_token():
    """Debug JWKS keys and token header"""
    print("🔍 Debugging JWKS and Token...")
    
    # Get token
    token = graph_client.get_token()
    if not token:
        print("❌ Failed to get token")
        return
    
    # Get token header
    try:
        header = jwt.get_unverified_header(token)
        print(f"\n🔑 Token Header:")
        print(json.dumps(header, indent=2))
        
        kid = header.get('kid')
        print(f"\n🆔 Token Key ID (kid): {kid}")
        
    except Exception as e:
        print(f"❌ Error getting token header: {e}")
        return
    
    # Fetch JWKS from both endpoints
    v1_url = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/keys"
    v2_url = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
    
    print(f"\n🔍 Fetching JWKS from v1.0 endpoint: {v1_url}")
    try:
        response = requests.get(v1_url)
        response.raise_for_status()
        v1_jwks = response.json()
        print(f"✅ v1.0 JWKS: {len(v1_jwks.get('keys', []))} keys")
        
        # Check if our token's kid exists in v1.0 keys
        v1_kids = [key.get('kid') for key in v1_jwks.get('keys', [])]
        print(f"🔑 v1.0 Key IDs: {v1_kids}")
        print(f"🎯 Token kid in v1.0 keys: {kid in v1_kids}")
        
    except Exception as e:
        print(f"❌ Error fetching v1.0 JWKS: {e}")
    
    print(f"\n🔍 Fetching JWKS from v2.0 endpoint: {v2_url}")
    try:
        response = requests.get(v2_url)
        response.raise_for_status()
        v2_jwks = response.json()
        print(f"✅ v2.0 JWKS: {len(v2_jwks.get('keys', []))} keys")
        
        # Check if our token's kid exists in v2.0 keys
        v2_kids = [key.get('kid') for key in v2_jwks.get('keys', [])]
        print(f"🔑 v2.0 Key IDs: {v2_kids}")
        print(f"🎯 Token kid in v2.0 keys: {kid in v2_kids}")
        
    except Exception as e:
        print(f"❌ Error fetching v2.0 JWKS: {e}")

if __name__ == "__main__":
    debug_jwks_and_token() 