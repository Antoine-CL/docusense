#!/usr/bin/env python3

from graph_client import graph_client
from auth import verify_token
import traceback

def test_authentication():
    """Test the authentication function directly"""
    print("🧪 Testing authentication...")
    
    # Get a token
    token = graph_client.get_token()
    if not token:
        print("❌ Failed to get token")
        return
    
    print(f"✅ Got token: {token[:50]}...")
    
    # Test token verification
    try:
        print("\n🔍 Testing token verification...")
        claims = verify_token(token, required_scope=None)
        print("✅ Token verification successful!")
        print(f"Claims: {claims}")
        
    except Exception as e:
        print(f"❌ Token verification failed: {e}")
        print(f"Exception type: {type(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    test_authentication() 