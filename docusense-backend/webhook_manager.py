"""
Webhook Subscription Management
Handles reading webhook subscription data from storage or Microsoft Graph
"""
import os
import json
from typing import Dict, Any, List
from datetime import datetime, timedelta

WEBHOOK_SUBSCRIPTIONS_FILE = "webhook_subscriptions.json"

class WebhookManager:
    def __init__(self):
        self.subscriptions_file = WEBHOOK_SUBSCRIPTIONS_FILE
        self._ensure_subscriptions_file()
    
    def _ensure_subscriptions_file(self):
        """Ensure the subscriptions file exists with sample data"""
        if not os.path.exists(self.subscriptions_file):
            # Create realistic sample subscriptions
            sample_subscriptions = {
                "subscriptions": [
                    {
                        "id": "12345678-1234-1234-1234-123456789012",
                        "resource": "/me/drive/root",
                        "changeType": "created,updated,deleted",
                        "notificationUrl": "https://docusense-func.azurewebsites.net/api/webhook",
                        "expirationDateTime": (datetime.now() + timedelta(days=2, hours=12)).isoformat() + "Z",
                        "clientState": "tenant-abc123",
                        "tenantId": "default",
                        "createdDateTime": (datetime.now() - timedelta(days=1)).isoformat() + "Z"
                    },
                    {
                        "id": "87654321-4321-4321-4321-210987654321", 
                        "resource": "/sites/root/drives/b!abc123def456/root",
                        "changeType": "created,updated,deleted",
                        "notificationUrl": "https://docusense-func.azurewebsites.net/api/webhook",
                        "expirationDateTime": (datetime.now() + timedelta(hours=18)).isoformat() + "Z",
                        "clientState": "tenant-abc123",
                        "tenantId": "default",
                        "createdDateTime": (datetime.now() - timedelta(days=2)).isoformat() + "Z"
                    },
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "resource": "/sites/contoso.sharepoint.com,abc123,def456/drives/b!xyz789/root",
                        "changeType": "created,updated,deleted", 
                        "notificationUrl": "https://docusense-func.azurewebsites.net/api/webhook",
                        "expirationDateTime": (datetime.now() + timedelta(days=3)).isoformat() + "Z",
                        "clientState": "tenant-abc123",
                        "tenantId": "default",
                        "createdDateTime": (datetime.now() - timedelta(hours=6)).isoformat() + "Z"
                    }
                ],
                "lastUpdated": datetime.now().isoformat() + "Z"
            }
            
            with open(self.subscriptions_file, 'w') as f:
                json.dump(sample_subscriptions, f, indent=2)
    
    def get_webhook_subscriptions(self, tenant_id: str = "default") -> Dict[str, Any]:
        """Get webhook subscriptions for a tenant"""
        try:
            with open(self.subscriptions_file, 'r') as f:
                data = json.load(f)
            
            # Filter subscriptions by tenant
            tenant_subscriptions = [
                sub for sub in data.get("subscriptions", [])
                if sub.get("tenantId") == tenant_id
            ]
            
            # Add status information
            for sub in tenant_subscriptions:
                sub["status"] = self._get_subscription_status(sub["expirationDateTime"])
            
            return {
                "subscriptions": tenant_subscriptions,
                "lastUpdated": data.get("lastUpdated", datetime.now().isoformat() + "Z"),
                "totalCount": len(tenant_subscriptions)
            }
        except Exception as e:
            print(f"Error reading webhook subscriptions: {e}")
            return {"subscriptions": [], "lastUpdated": datetime.now().isoformat() + "Z", "totalCount": 0}
    
    def _get_subscription_status(self, expiration_datetime: str) -> str:
        """Determine subscription status based on expiration"""
        try:
            expiry = datetime.fromisoformat(expiration_datetime.replace('Z', '+00:00'))
            now = datetime.now(expiry.tzinfo)
            hours_until_expiry = (expiry - now).total_seconds() / 3600
            
            if hours_until_expiry < 0:
                return "expired"
            elif hours_until_expiry < 24:
                return "expiring_soon"
            else:
                return "active"
        except Exception:
            return "unknown"
    
    def add_webhook_subscription(self, subscription: Dict[str, Any], tenant_id: str = "default"):
        """Add a new webhook subscription"""
        try:
            with open(self.subscriptions_file, 'r') as f:
                data = json.load(f)
            
            subscription["tenantId"] = tenant_id
            subscription["createdDateTime"] = datetime.now().isoformat() + "Z"
            
            data["subscriptions"].append(subscription)
            data["lastUpdated"] = datetime.now().isoformat() + "Z"
            
            with open(self.subscriptions_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            print(f"Added webhook subscription {subscription.get('id')} for tenant {tenant_id}")
        except Exception as e:
            print(f"Error adding webhook subscription: {e}")
            raise
    
    def remove_webhook_subscription(self, subscription_id: str, tenant_id: str = "default"):
        """Remove a webhook subscription"""
        try:
            with open(self.subscriptions_file, 'r') as f:
                data = json.load(f)
            
            original_count = len(data["subscriptions"])
            data["subscriptions"] = [
                sub for sub in data["subscriptions"]
                if not (sub.get("id") == subscription_id and sub.get("tenantId") == tenant_id)
            ]
            
            if len(data["subscriptions"]) < original_count:
                data["lastUpdated"] = datetime.now().isoformat() + "Z"
                with open(self.subscriptions_file, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"Removed webhook subscription {subscription_id} for tenant {tenant_id}")
            else:
                print(f"Webhook subscription {subscription_id} not found for tenant {tenant_id}")
                
        except Exception as e:
            print(f"Error removing webhook subscription: {e}")
            raise

# Global instance
webhook_manager = WebhookManager()

def get_webhook_subscriptions(tenant_id: str = "default") -> Dict[str, Any]:
    """Get webhook subscriptions for a tenant"""
    return webhook_manager.get_webhook_subscriptions(tenant_id)

def add_webhook_subscription(subscription: Dict[str, Any], tenant_id: str = "default"):
    """Add a new webhook subscription"""
    return webhook_manager.add_webhook_subscription(subscription, tenant_id)

def remove_webhook_subscription(subscription_id: str, tenant_id: str = "default"):
    """Remove a webhook subscription"""
    return webhook_manager.remove_webhook_subscription(subscription_id, tenant_id) 