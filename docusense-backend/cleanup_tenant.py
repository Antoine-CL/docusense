"""
Tenant Cleanup Function
Handles complete tenant removal when subscription is cancelled
This would be triggered by a subscriptionRemoved event
"""
import os
import json
from typing import Dict, Any, List
from datetime import datetime
import asyncio

class TenantCleanupManager:
    def __init__(self):
        # In production, these would be actual Azure clients
        # self.search_client = SearchClient(endpoint, index_name, credential)
        # self.graph_client = GraphServiceClient(credential)
        # self.keyvault_client = KeyVaultClient(credential)
        pass
    
    async def cleanup_tenant(self, tenant_id: str, reason: str = "subscription_cancelled") -> Dict[str, Any]:
        """
        Complete tenant cleanup orchestrator
        Removes all tenant data and resources
        """
        print(f"Starting complete cleanup for tenant {tenant_id}")
        print(f"Cleanup reason: {reason}")
        
        result = {
            "tenant_id": tenant_id,
            "reason": reason,
            "started": datetime.now().isoformat(),
            "status": "in_progress",
            "steps": []
        }
        
        try:
            # Step 1: Remove webhook subscriptions
            await self._remove_webhook_subscriptions(tenant_id, result)
            
            # Step 2: Delete search documents
            await self._delete_search_documents(tenant_id, result)
            
            # Step 3: Remove Key Vault secrets
            await self._remove_keyvault_secrets(tenant_id, result)
            
            # Step 4: Clean up tenant configuration
            await self._remove_tenant_config(tenant_id, result)
            
            # Step 5: Log cleanup completion
            await self._log_cleanup_completion(tenant_id, result)
            
            result["status"] = "completed"
            result["completed"] = datetime.now().isoformat()
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["failed"] = datetime.now().isoformat()
            print(f"Tenant cleanup failed for {tenant_id}: {e}")
        
        return result
    
    async def _remove_webhook_subscriptions(self, tenant_id: str, result: Dict[str, Any]):
        """Remove all webhook subscriptions for the tenant"""
        print(f"Removing webhook subscriptions for tenant {tenant_id}")
        
        step = {
            "step": "remove_webhooks",
            "started": datetime.now().isoformat()
        }
        
        try:
            # Get all webhook subscriptions for tenant
            subscriptions = await self._get_tenant_webhooks(tenant_id)
            
            removed_count = 0
            for subscription in subscriptions:
                await self._delete_webhook_subscription(subscription["id"])
                removed_count += 1
            
            step["status"] = "completed"
            step["completed"] = datetime.now().isoformat()
            step["subscriptions_removed"] = removed_count
            print(f"  ✓ Removed {removed_count} webhook subscriptions")
            
        except Exception as e:
            step["status"] = "failed"
            step["error"] = str(e)
            print(f"  ✗ Failed to remove webhook subscriptions: {e}")
            raise
        
        result["steps"].append(step)
    
    async def _delete_search_documents(self, tenant_id: str, result: Dict[str, Any]):
        """Delete all search documents for the tenant"""
        print(f"Deleting search documents for tenant {tenant_id}")
        
        step = {
            "step": "delete_search_documents",
            "started": datetime.now().isoformat()
        }
        
        try:
            # Find all documents for tenant
            documents = await self._find_tenant_documents(tenant_id)
            
            if documents:
                deleted_count = await self._batch_delete_documents(documents)
                step["documents_deleted"] = deleted_count
                print(f"  ✓ Deleted {deleted_count} search documents")
            else:
                step["documents_deleted"] = 0
                print(f"  ✓ No search documents found")
            
            step["status"] = "completed"
            step["completed"] = datetime.now().isoformat()
            
        except Exception as e:
            step["status"] = "failed"
            step["error"] = str(e)
            print(f"  ✗ Failed to delete search documents: {e}")
            raise
        
        result["steps"].append(step)
    
    async def _remove_keyvault_secrets(self, tenant_id: str, result: Dict[str, Any]):
        """Remove tenant-specific secrets from Key Vault"""
        print(f"Removing Key Vault secrets for tenant {tenant_id}")
        
        step = {
            "step": "remove_keyvault_secrets",
            "started": datetime.now().isoformat()
        }
        
        try:
            # Find tenant-specific secrets
            secret_names = await self._find_tenant_secrets(tenant_id)
            
            removed_count = 0
            for secret_name in secret_names:
                await self._delete_keyvault_secret(secret_name)
                removed_count += 1
            
            step["status"] = "completed"
            step["completed"] = datetime.now().isoformat()
            step["secrets_removed"] = removed_count
            print(f"  ✓ Removed {removed_count} Key Vault secrets")
            
        except Exception as e:
            step["status"] = "failed"
            step["error"] = str(e)
            print(f"  ✗ Failed to remove Key Vault secrets: {e}")
            # Don't raise - this is not critical
        
        result["steps"].append(step)
    
    async def _remove_tenant_config(self, tenant_id: str, result: Dict[str, Any]):
        """Remove tenant configuration from database"""
        print(f"Removing tenant configuration for {tenant_id}")
        
        step = {
            "step": "remove_tenant_config",
            "started": datetime.now().isoformat()
        }
        
        try:
            # Remove from tenant settings
            await self._delete_tenant_settings(tenant_id)
            
            # Remove from webhook subscriptions
            await self._delete_tenant_webhooks(tenant_id)
            
            step["status"] = "completed"
            step["completed"] = datetime.now().isoformat()
            print(f"  ✓ Removed tenant configuration")
            
        except Exception as e:
            step["status"] = "failed"
            step["error"] = str(e)
            print(f"  ✗ Failed to remove tenant configuration: {e}")
            raise
        
        result["steps"].append(step)
    
    async def _get_tenant_webhooks(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all webhook subscriptions for tenant"""
        # Production implementation would query Graph API
        """
        subscriptions = await self.graph_client.subscriptions.get()
        return [sub for sub in subscriptions.value if sub.client_state == f"tenant-{tenant_id}"]
        """
        
        # Simulate with file-based storage
        try:
            with open("webhook_subscriptions.json", "r") as f:
                data = json.load(f)
            
            return [sub for sub in data.get("subscriptions", []) if sub.get("tenantId") == tenant_id]
        except Exception:
            return []
    
    async def _delete_webhook_subscription(self, subscription_id: str):
        """Delete a single webhook subscription"""
        # Production implementation would call Graph API
        """
        await self.graph_client.subscriptions[subscription_id].delete()
        """
        await asyncio.sleep(0.1)  # Simulate API call
    
    async def _find_tenant_documents(self, tenant_id: str) -> List[str]:
        """Find all search documents for tenant"""
        # Production implementation would query Azure Search
        """
        results = self.search_client.search(
            search_text="*",
            filter=f"tenant_id eq '{tenant_id}'",
            select=["id"],
            top=10000  # Get all documents
        )
        return [doc["id"] for doc in results]
        """
        
        # Simulate finding documents
        await asyncio.sleep(0.5)
        
        # Generate some sample document IDs
        import random
        doc_count = random.randint(50, 500)
        return [f"{tenant_id}_doc_{i}_{random.randint(1000, 9999)}" for i in range(doc_count)]
    
    async def _batch_delete_documents(self, document_ids: List[str]) -> int:
        """Delete documents in batches"""
        # Production implementation would batch delete from Azure Search
        """
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, len(document_ids), batch_size):
            batch = document_ids[i:i + batch_size]
            delete_batch = [{"@search.action": "delete", "id": doc_id} for doc_id in batch]
            
            result = self.search_client.upload_documents(delete_batch)
            for item in result:
                if item.succeeded:
                    deleted_count += 1
        
        return deleted_count
        """
        
        await asyncio.sleep(2)  # Simulate batch deletion
        return len(document_ids)
    
    async def _find_tenant_secrets(self, tenant_id: str) -> List[str]:
        """Find tenant-specific secrets in Key Vault"""
        # Production implementation would list Key Vault secrets
        """
        secret_properties = self.keyvault_client.list_properties_of_secrets()
        tenant_secrets = []
        
        for secret in secret_properties:
            if tenant_id in secret.name:
                tenant_secrets.append(secret.name)
        
        return tenant_secrets
        """
        
        # Simulate finding secrets
        await asyncio.sleep(0.2)
        return [
            f"tenant-{tenant_id}-graph-token",
            f"tenant-{tenant_id}-search-key",
            f"tenant-{tenant_id}-webhook-secret"
        ]
    
    async def _delete_keyvault_secret(self, secret_name: str):
        """Delete a secret from Key Vault"""
        # Production implementation would delete from Key Vault
        """
        self.keyvault_client.begin_delete_secret(secret_name)
        """
        await asyncio.sleep(0.1)
    
    async def _delete_tenant_settings(self, tenant_id: str):
        """Remove tenant from settings file"""
        try:
            with open("tenant_settings.json", "r") as f:
                all_settings = json.load(f)
            
            if tenant_id in all_settings:
                del all_settings[tenant_id]
                
                with open("tenant_settings.json", "w") as f:
                    json.dump(all_settings, f, indent=2)
        except Exception as e:
            print(f"Error removing tenant settings: {e}")
    
    async def _delete_tenant_webhooks(self, tenant_id: str):
        """Remove tenant webhooks from subscriptions file"""
        try:
            with open("webhook_subscriptions.json", "r") as f:
                data = json.load(f)
            
            # Filter out tenant webhooks
            data["subscriptions"] = [
                sub for sub in data.get("subscriptions", [])
                if sub.get("tenantId") != tenant_id
            ]
            data["lastUpdated"] = datetime.now().isoformat() + "Z"
            
            with open("webhook_subscriptions.json", "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error removing tenant webhooks: {e}")
    
    async def _log_cleanup_completion(self, tenant_id: str, result: Dict[str, Any]):
        """Log tenant cleanup completion"""
        # Production implementation would log to Application Insights
        """
        telemetry_client.track_event(
            "TenantCleanupCompleted",
            {
                "tenant_id": tenant_id,
                "reason": result["reason"],
                "status": result["status"],
                "steps_completed": len([s for s in result["steps"] if s.get("status") == "completed"])
            }
        )
        """
        print(f"Logged tenant cleanup completion for {tenant_id}")

# Global instance
cleanup_manager = TenantCleanupManager()

async def cleanup_tenant(tenant_id: str, reason: str = "subscription_cancelled") -> Dict[str, Any]:
    """Clean up tenant completely"""
    return await cleanup_manager.cleanup_tenant(tenant_id, reason)

# For testing
if __name__ == "__main__":
    import asyncio
    
    async def test_cleanup():
        result = await cleanup_tenant("test-tenant", "subscription_cancelled")
        print(json.dumps(result, indent=2))
    
    asyncio.run(test_cleanup()) 