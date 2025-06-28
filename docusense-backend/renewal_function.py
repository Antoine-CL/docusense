import azure.functions as func
import json
import logging
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List

# Import your existing modules
from graph_client import graph_client

def main(mytimer: func.TimerRequest) -> None:
    """Azure Function timer trigger to renew webhook subscriptions"""
    
    utc_timestamp = datetime.utcnow().replace(tzinfo=None).isoformat()
    
    if mytimer.past_due:
        logging.info('The timer is past due!')
    
    logging.info(f'Webhook renewal function ran at {utc_timestamp}')
    
    try:
        # Get all active subscriptions
        subscriptions = get_active_subscriptions()
        
        if not subscriptions:
            logging.info('No active subscriptions found')
            return
        
        logging.info(f'Found {len(subscriptions)} active subscriptions')
        
        # Renew subscriptions that are expiring soon (within 6 hours)
        renewal_threshold = datetime.utcnow() + timedelta(hours=6)
        
        for subscription in subscriptions:
            try:
                expiration_str = subscription.get('expirationDateTime', '')
                # Parse ISO format: 2024-01-15T10:30:00.0000000Z
                expiration_dt = datetime.fromisoformat(expiration_str.replace('Z', '+00:00')).replace(tzinfo=None)
                
                if expiration_dt <= renewal_threshold:
                    logging.info(f'Renewing subscription {subscription["id"]} (expires {expiration_str})')
                    
                    success = renew_subscription(subscription['id'])
                    if success:
                        logging.info(f'Successfully renewed subscription {subscription["id"]}')
                    else:
                        logging.error(f'Failed to renew subscription {subscription["id"]}')
                        # Store failed renewal for alerting
                        store_renewal_failure(subscription)
                else:
                    logging.info(f'Subscription {subscription["id"]} not due for renewal (expires {expiration_str})')
                    
            except Exception as e:
                logging.error(f'Error processing subscription {subscription.get("id", "unknown")}: {str(e)}')
    
    except Exception as e:
        logging.error(f'Error in renewal function: {str(e)}')

def get_active_subscriptions() -> List[Dict]:
    """Get all active webhook subscriptions"""
    
    try:
        headers = graph_client.get_headers()
        response = requests.get(
            "https://graph.microsoft.com/v1.0/subscriptions",
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            logging.error(f'Failed to get subscriptions: {response.status_code} - {response.text}')
            return []
            
    except Exception as e:
        logging.error(f'Error getting subscriptions: {str(e)}')
        return []

def renew_subscription(subscription_id: str) -> bool:
    """Renew a webhook subscription"""
    
    # Extend for 2 days from now
    new_expiration = (datetime.utcnow() + timedelta(days=2)).isoformat() + "Z"
    
    renewal_data = {
        "expirationDateTime": new_expiration
    }
    
    try:
        headers = graph_client.get_headers()
        response = requests.patch(
            f"https://graph.microsoft.com/v1.0/subscriptions/{subscription_id}",
            headers=headers,
            json=renewal_data
        )
        
        if response.status_code == 200:
            logging.info(f'Renewed subscription {subscription_id} until {new_expiration}')
            return True
        else:
            logging.error(f'Failed to renew subscription {subscription_id}: {response.status_code} - {response.text}')
            return False
            
    except Exception as e:
        logging.error(f'Error renewing subscription {subscription_id}: {str(e)}')
        return False

def store_renewal_failure(subscription: Dict):
    """Store renewal failure for alerting (could be database, storage, etc.)"""
    
    # For now, just log the failure - in production you might want to:
    # - Store in a database table
    # - Send to Azure Service Bus for processing
    # - Trigger an alert/notification
    
    failure_info = {
        "subscription_id": subscription.get("id"),
        "resource": subscription.get("resource"),
        "expiration": subscription.get("expirationDateTime"),
        "failure_time": datetime.utcnow().isoformat(),
        "notification_url": subscription.get("notificationUrl")
    }
    
    logging.error(f'RENEWAL FAILURE: {json.dumps(failure_info)}')
    
    # You could also write to Azure Storage, send to a queue, etc.
    # Example: store_in_table_storage(failure_info)

# Multi-tenant subscription management functions
def create_subscription_for_tenant(tenant_id: str, drive_id: str, notification_url: str) -> Dict:
    """Create a webhook subscription for a specific tenant"""
    
    # Use app-only token for the specific tenant
    headers = get_app_only_headers_for_tenant(tenant_id)
    
    subscription_data = {
        "changeType": "created,updated,deleted",
        "notificationUrl": notification_url,
        "resource": f"/drives/{drive_id}/root",
        "expirationDateTime": (datetime.utcnow() + timedelta(days=2)).isoformat() + "Z",
        "clientState": f"docusense-{tenant_id}-webhook"  # Include tenant ID in client state
    }
    
    try:
        response = requests.post(
            "https://graph.microsoft.com/v1.0/subscriptions",
            headers=headers,
            json=subscription_data
        )
        
        if response.status_code == 201:
            subscription = response.json()
            # Store the mapping of tenant -> subscription
            store_tenant_subscription_mapping(tenant_id, subscription['id'], drive_id)
            logging.info(f'Created subscription {subscription["id"]} for tenant {tenant_id}')
            return subscription
        else:
            logging.error(f'Failed to create subscription for tenant {tenant_id}: {response.text}')
            return None
            
    except Exception as e:
        logging.error(f'Error creating subscription for tenant {tenant_id}: {str(e)}')
        return None

def get_app_only_headers_for_tenant(tenant_id: str) -> Dict:
    """Get app-only authentication headers for a specific tenant"""
    
    # This would use the admin-consented app registration
    # to get an app-only token for the specific tenant
    
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    
    # Get app-only token for specific tenant
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }
    
    try:
        response = requests.post(token_url, data=token_data)
        
        if response.status_code == 200:
            token_info = response.json()
            access_token = token_info["access_token"]
            
            return {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        else:
            logging.error(f'Failed to get app-only token for tenant {tenant_id}: {response.text}')
            return None
            
    except Exception as e:
        logging.error(f'Error getting app-only token for tenant {tenant_id}: {str(e)}')
        return None

def store_tenant_subscription_mapping(tenant_id: str, subscription_id: str, drive_id: str):
    """Store mapping of tenant to subscription IDs"""
    
    # In production, this should be stored in a database
    # For now, we'll use environment variables or Azure Storage
    
    mapping_info = {
        "tenant_id": tenant_id,
        "subscription_id": subscription_id,
        "drive_id": drive_id,
        "created_at": datetime.utcnow().isoformat()
    }
    
    logging.info(f'TENANT MAPPING: {json.dumps(mapping_info)}')
    
    # TODO: Store in database table with schema:
    # - tenant_id (string)
    # - subscription_id (string) 
    # - drive_id (string)
    # - created_at (datetime)
    # - status (active/expired/failed)

def cleanup_tenant_subscriptions(tenant_id: str):
    """Clean up all subscriptions for a tenant (when they uninstall)"""
    
    # Get all subscriptions for this tenant
    tenant_subscriptions = get_subscriptions_for_tenant(tenant_id)
    
    headers = get_app_only_headers_for_tenant(tenant_id)
    if not headers:
        logging.error(f'Cannot get headers for tenant {tenant_id} cleanup')
        return
    
    for subscription_id in tenant_subscriptions:
        try:
            response = requests.delete(
                f"https://graph.microsoft.com/v1.0/subscriptions/{subscription_id}",
                headers=headers
            )
            
            if response.status_code == 204:
                logging.info(f'Deleted subscription {subscription_id} for tenant {tenant_id}')
            else:
                logging.error(f'Failed to delete subscription {subscription_id}: {response.text}')
                
        except Exception as e:
            logging.error(f'Error deleting subscription {subscription_id}: {str(e)}')

def get_subscriptions_for_tenant(tenant_id: str) -> List[str]:
    """Get all subscription IDs for a specific tenant"""
    
    # In production, query from database
    # For now, return empty list - implement based on your storage
    
    # TODO: Query database for subscriptions where tenant_id = tenant_id
    return []

# Timer trigger configuration (runs daily at 2 AM UTC)
# Add this to function.json:
# {
#   "scriptFile": "renewal_function.py",
#   "bindings": [
#     {
#       "name": "mytimer",
#       "type": "timerTrigger",
#       "direction": "in",
#       "schedule": "0 0 2 * * *"
#     }
#   ]
# } 