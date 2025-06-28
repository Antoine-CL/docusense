#!/usr/bin/env python3

from graph_client import graph_client
from auth_simple import validate_token_hybrid, validate_token_with_userinfo
import traceback

def test_simple_authentication():
    """Test the simplified authentication approaches"""
    print("🧪 Testing SIMPLE authentication approaches...")
    
    # Get a token
    token = graph_client.get_token()
    if not token:
        print("❌ Failed to get token")
        return
    
    print(f"✅ Got token: {token[:50]}...")
    
    # Test hybrid validation
    print("\n🔍 Testing hybrid validation...")
    try:
        claims = validate_token_hybrid(token, required_scope=None)
        print("✅ Hybrid validation successful!")
        print(f"🎉 Claims preview: {claims.get('aud', 'N/A')} | {claims.get('appid', 'N/A')} | {claims.get('validation_method', 'N/A')}")
        
        # Test userinfo validation
        print("\n🔍 Testing userinfo validation...")
        user_claims = validate_token_with_userinfo(token)
        print("✅ Userinfo validation successful!")
        print(f"🎉 User info: {user_claims.get('graph_user_info', {}).get('displayName', 'N/A')}")
        
        return claims
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        print(f"Exception type: {type(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_authentication() 