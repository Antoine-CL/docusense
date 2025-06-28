"""
Tests for DocuSense Admin Endpoints
Tests the live data implementation of admin functionality
"""
import pytest
import json
from fastapi.testclient import TestClient
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'docusense-backend'))

from main_live import app

client = TestClient(app)

class TestAdminEndpoints:
    """Test suite for admin endpoints with live data"""
    
    def test_health_endpoint(self):
        """Test that health endpoint is working"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_get_admin_settings(self):
        """Test getting admin settings"""
        response = client.get("/admin/settings")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "region" in data
        assert "retentionDays" in data
        
        # Check data types
        assert isinstance(data["region"], str)
        assert isinstance(data["retentionDays"], int)
        
        # Check valid values
        assert data["region"] in ["eastus", "westus", "westeurope", "northeurope"]
        assert 1 <= data["retentionDays"] <= 365
    
    def test_update_admin_settings(self):
        """Test updating admin settings"""
        new_settings = {
            "region": "westeurope",
            "retentionDays": 60
        }
        
        response = client.patch("/admin/settings", json=new_settings)
        assert response.status_code == 200
        data = response.json()
        
        # Check the update was applied
        assert data["region"] == "westeurope"
        assert data["retentionDays"] == 60
        assert "lastModified" in data
    
    def test_get_webhooks(self):
        """Test getting webhook subscriptions"""
        response = client.get("/admin/webhooks")
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "subscriptions" in data
        assert "totalCount" in data
        assert "lastUpdated" in data
        
        # Check data types
        assert isinstance(data["subscriptions"], list)
        assert isinstance(data["totalCount"], int)
        
        # Check webhook structure if any exist
        if data["subscriptions"]:
            webhook = data["subscriptions"][0]
            required_fields = ["id", "resource", "changeType", "expirationDateTime", "status"]
            for field in required_fields:
                assert field in webhook
            
            # Check status values
            assert webhook["status"] in ["active", "expiring_soon", "expired"]
    
    def test_get_usage_statistics(self):
        """Test getting usage statistics"""
        response = client.get("/admin/usage")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        required_fields = [
            "documentsIndexed", "totalEmbeddings", "searchRequests",
            "storageUsedMB", "estimatedMonthlyCost", "breakdown", "trends"
        ]
        for field in required_fields:
            assert field in data
        
        # Check data types
        assert isinstance(data["documentsIndexed"], int)
        assert isinstance(data["totalEmbeddings"], int)
        assert isinstance(data["searchRequests"], int)
        assert isinstance(data["storageUsedMB"], (int, float))
        assert isinstance(data["estimatedMonthlyCost"], (int, float))
        
        # Check breakdown structure
        breakdown = data["breakdown"]
        breakdown_fields = ["searchCost", "embeddingCost", "storageCost", "functionCost"]
        for field in breakdown_fields:
            assert field in breakdown
            assert isinstance(breakdown[field], (int, float))
        
        # Check trends structure
        trends = data["trends"]
        trends_fields = ["documentsThisWeek", "searchesThisWeek", "avgResponseTimeMs"]
        for field in trends_fields:
            assert field in trends
            assert isinstance(trends[field], int)
    
    def test_get_audit_log(self):
        """Test getting audit log CSV"""
        response = client.get("/admin/auditlog?from_date=2025-06-20&to_date=2025-06-26")
        assert response.status_code == 200
        
        # Check it's CSV content
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        
        # Check CSV structure
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) >= 1  # At least header
        
        # Check header
        header = lines[0]
        expected_columns = ["timestamp", "event_type", "user", "details", "result"]
        for column in expected_columns:
            assert column in header
    
    def test_user_info_endpoint(self):
        """Test getting user info"""
        response = client.get("/me")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        required_fields = ["user_id", "name", "email", "tenant", "roles"]
        for field in required_fields:
            assert field in data
        
        # Check data types
        assert isinstance(data["roles"], list)
    
    def test_invalid_settings_update(self):
        """Test updating settings with invalid data"""
        invalid_settings = {
            "region": "invalid-region",
            "retentionDays": -1
        }
        
        # This should still work with our current implementation
        # but in production would have validation
        response = client.patch("/admin/settings", json=invalid_settings)
        # For now, we accept any values, but in production this would be validated
        assert response.status_code == 200
    
    def test_settings_persistence(self):
        """Test that settings persist across requests"""
        # Set specific values
        test_settings = {
            "region": "northeurope",
            "retentionDays": 45
        }
        
        # Update settings
        update_response = client.patch("/admin/settings", json=test_settings)
        assert update_response.status_code == 200
        
        # Get settings again
        get_response = client.get("/admin/settings")
        assert get_response.status_code == 200
        data = get_response.json()
        
        # Check persistence
        assert data["region"] == "northeurope"
        assert data["retentionDays"] == 45

# Integration tests for the live data modules
class TestLiveDataModules:
    """Test the underlying live data modules"""
    
    def test_tenant_settings_module(self):
        """Test tenant settings module directly"""
        from tenant_settings import get_tenant_settings, update_tenant_settings
        
        # Test getting settings
        settings = get_tenant_settings("test-tenant")
        assert isinstance(settings, dict)
        assert "region" in settings
        assert "retentionDays" in settings
        
        # Test updating settings
        new_settings = {"region": "westus", "retentionDays": 30}
        updated = update_tenant_settings("test-tenant", new_settings)
        assert updated["region"] == "westus"
        assert updated["retentionDays"] == 30
    
    def test_webhook_manager_module(self):
        """Test webhook manager module directly"""
        from webhook_manager import get_webhook_subscriptions
        
        # Test getting webhooks
        webhooks = get_webhook_subscriptions("default")
        assert isinstance(webhooks, dict)
        assert "subscriptions" in webhooks
        assert "totalCount" in webhooks
    
    def test_usage_analytics_module(self):
        """Test usage analytics module directly"""
        from usage_analytics import get_usage_statistics
        
        # Test getting usage stats
        stats = get_usage_statistics("default")
        assert isinstance(stats, dict)
        assert "documentsIndexed" in stats
        assert "estimatedMonthlyCost" in stats
    
    def test_audit_logger_module(self):
        """Test audit logger module directly"""
        from audit_logger import generate_audit_csv
        
        # Test generating audit log
        csv_content = generate_audit_csv("2025-06-20", "2025-06-26", "default")
        assert isinstance(csv_content, str)
        assert "timestamp" in csv_content
        assert "event_type" in csv_content

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 