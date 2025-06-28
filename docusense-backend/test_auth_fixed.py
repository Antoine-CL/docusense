#!/usr/bin/env python3

from graph_client import graph_client
from auth_fixed import verify_token
import traceback

def test_fixed_authentication():
    """Test the fixed authentication function"""
    print("🧪 Testing FIXED authentication...")
    
    # Get a token
    token = graph_client.get_token()
    if not token:
        print("❌ Failed to get token")
        return
    
    print(f"✅ Got token: {token[:50]}...")
    
    # Test token verification
    try:
        print("\n🔍 Testing token verification with fixed implementation...")
        claims = verify_token(token, required_scope=None)
        print("✅ Token verification successful!")
        print(f"🎉 Claims preview: {claims.get('aud', 'N/A')} | {claims.get('iss', 'N/A')} | {claims.get('appid', 'N/A')}")
        return claims
        
    except Exception as e:
        print(f"❌ Token verification failed: {e}")
        print(f"Exception type: {type(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    test_fixed_authentication() 