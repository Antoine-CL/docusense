#!/usr/bin/env python3
"""
Setup Microsoft Graph Webhooks for Real-time Document Ingestion
"""

import os
import requests
from dotenv import load_dotenv
from graph_client import graph_client
from webhook_handler import webhook_manager

load_dotenv()

def setup_webhooks():
    """Setup webhook subscriptions for all accessible drives"""
    
    print("🔄 Setting up Microsoft Graph webhooks...")
    
    # Your webhook endpoint URL (must be publicly accessible)
    webhook_url = os.getenv("WEBHOOK_URL", "https://your-app.com/api/webhooks/graph")
    
    if webhook_url == "https://your-app.com/api/webhooks/graph":
        print("❌ Please set WEBHOOK_URL environment variable to your public webhook endpoint")
        print("Example: https://your-allfind-api.azurewebsites.net/api/webhooks/graph")
        return
    
    # Get all accessible drives
    drives = graph_client.list_drives()
    if not drives:
        print("❌ No drives found or authentication failed")
        return
    
    print(f"📁 Found {len(drives)} drives to monitor")
    
    # Create webhook subscription for each drive
    for drive in drives:
        drive_id = drive["id"]
        drive_name = drive.get("name", "Unknown")
        
        print(f"📂 Setting up webhook for: {drive_name}")
        
        subscription = webhook_manager.create_subscription(drive_id, webhook_url)
        if subscription:
            print(f"✅ Webhook active for {drive_name}")
            print(f"   Subscription ID: {subscription['id']}")
            print(f"   Expires: {subscription['expirationDateTime']}")
        else:
            print(f"❌ Failed to create webhook for {drive_name}")
    
    print("\n🎉 Webhook setup complete!")
    print("📝 Remember to:")
    print("1. Keep your webhook endpoint running")
    print("2. Renew subscriptions before they expire (every 2-3 days)")
    print("3. Monitor webhook logs for incoming notifications")

def list_active_subscriptions():
    """List all active webhook subscriptions"""
    
    print("🔄 Checking active webhook subscriptions...")
    
    try:
        headers = graph_client.get_headers()
        response = requests.get(
            "https://graph.microsoft.com/v1.0/subscriptions",
            headers=headers
        )
        
        if response.status_code == 200:
            subscriptions = response.json().get("value", [])
            print(f"📋 Found {len(subscriptions)} active subscriptions:")
            
            for sub in subscriptions:
                print(f"   ID: {sub['id']}")
                print(f"   Resource: {sub['resource']}")
                print(f"   Expires: {sub['expirationDateTime']}")
                print(f"   Notification URL: {sub['notificationUrl']}")
                print()
        else:
            print(f"❌ Failed to list subscriptions: {response.text}")
            
    except Exception as e:
        print(f"❌ Error listing subscriptions: {e}")

def cleanup_subscriptions():
    """Delete all webhook subscriptions"""
    
    print("🔄 Cleaning up webhook subscriptions...")
    
    try:
        headers = graph_client.get_headers()
        
        # Get all subscriptions
        response = requests.get(
            "https://graph.microsoft.com/v1.0/subscriptions",
            headers=headers
        )
        
        if response.status_code == 200:
            subscriptions = response.json().get("value", [])
            
            for sub in subscriptions:
                sub_id = sub["id"]
                print(f"🗑️  Deleting subscription: {sub_id}")
                
                delete_response = requests.delete(
                    f"https://graph.microsoft.com/v1.0/subscriptions/{sub_id}",
                    headers=headers
                )
                
                if delete_response.status_code == 204:
                    print(f"✅ Deleted subscription: {sub_id}")
                else:
                    print(f"❌ Failed to delete subscription: {sub_id}")
        
        print("🧹 Cleanup complete!")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "setup":
            setup_webhooks()
        elif command == "list":
            list_active_subscriptions()
        elif command == "cleanup":
            cleanup_subscriptions()
        else:
            print("Usage: python setup_webhooks.py [setup|list|cleanup]")
    else:
        print("Microsoft Graph Webhook Management")
        print("Usage: python setup_webhooks.py [command]")
        print()
        print("Commands:")
        print("  setup   - Create webhook subscriptions for all drives")
        print("  list    - List all active subscriptions")
        print("  cleanup - Delete all webhook subscriptions")
        print()
        print("Example:")
        print("  python setup_webhooks.py setup") 