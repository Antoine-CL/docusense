"""
Tenant Settings Management
Handles reading/writing tenant configuration to database storage
"""
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime

# For now, we'll use file-based storage as a simple database replacement
# In production, this would connect to Cosmos DB or Azure Table Storage

TENANT_SETTINGS_FILE = "tenant_settings.json"

class TenantSettingsManager:
    def __init__(self):
        self.settings_file = TENANT_SETTINGS_FILE
        self._ensure_settings_file()
    
    def _ensure_settings_file(self):
        """Ensure the settings file exists with default data"""
        if not os.path.exists(self.settings_file):
            default_settings = {
                "default": {
                    "region": "eastus",
                    "retentionDays": 90,
                    "created": datetime.now().isoformat(),
                    "lastModified": datetime.now().isoformat()
                }
            }
            with open(self.settings_file, 'w') as f:
                json.dump(default_settings, f, indent=2)
    
    def get_tenant_settings(self, tenant_id: str = "default") -> Dict[str, Any]:
        """Get settings for a specific tenant"""
        try:
            with open(self.settings_file, 'r') as f:
                all_settings = json.load(f)
            
            if tenant_id not in all_settings:
                # Create default settings for new tenant
                all_settings[tenant_id] = {
                    "region": "eastus",
                    "retentionDays": 90,
                    "created": datetime.now().isoformat(),
                    "lastModified": datetime.now().isoformat()
                }
                self._save_all_settings(all_settings)
            
            return all_settings[tenant_id]
        except Exception as e:
            print(f"Error reading tenant settings: {e}")
            return {
                "region": "eastus",
                "retentionDays": 90,
                "created": datetime.now().isoformat(),
                "lastModified": datetime.now().isoformat()
            }
    
    def update_tenant_settings(self, tenant_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update settings for a specific tenant"""
        try:
            with open(self.settings_file, 'r') as f:
                all_settings = json.load(f)
            
            if tenant_id not in all_settings:
                all_settings[tenant_id] = {}
            
            # Update only the provided fields
            all_settings[tenant_id].update(settings)
            all_settings[tenant_id]["lastModified"] = datetime.now().isoformat()
            
            self._save_all_settings(all_settings)
            
            # In production, this would trigger a Service Bus message for reprocessing
            self._trigger_reprovision(tenant_id, settings)
            
            return all_settings[tenant_id]
        except Exception as e:
            print(f"Error updating tenant settings: {e}")
            raise
    
    def _save_all_settings(self, settings: Dict[str, Any]):
        """Save all settings to file"""
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
    
    def _trigger_reprovision(self, tenant_id: str, changed_settings: Dict[str, Any]):
        """Trigger tenant reprovisioning (placeholder for Service Bus message)"""
        print(f"REPROVISION TRIGGER: Tenant {tenant_id} changed settings: {changed_settings}")
        print("In production: Would send Service Bus message to Durable Function")
        
        # Simulate what would happen in production:
        if "region" in changed_settings:
            print(f"  → Would create Search index in {changed_settings['region']}")
            print(f"  → Would re-ingest documents via delta query")
            print(f"  → Would update tenant configuration")
        
        if "retentionDays" in changed_settings:
            print(f"  → Would update retention policy to {changed_settings['retentionDays']} days")

# Global instance
tenant_manager = TenantSettingsManager()

def get_tenant_settings(tenant_id: str = "default") -> Dict[str, Any]:
    """Get tenant settings"""
    return tenant_manager.get_tenant_settings(tenant_id)

def update_tenant_settings(tenant_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """Update tenant settings"""
    return tenant_manager.update_tenant_settings(tenant_id, settings) 