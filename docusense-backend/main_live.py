from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import os

# Import our live data modules
from tenant_settings import get_tenant_settings, update_tenant_settings
from webhook_manager import get_webhook_subscriptions
from usage_analytics import get_usage_statistics
from audit_logger import generate_audit_csv

# Import authentication modules
from auth_verified import auth_dependency, lenient_auth_dependency

app = FastAPI(title="AllFind API", version="1.0.0")

# Add CORS middleware for development and production
origins = [
    "http://localhost:3000",                         # Local development
    "https://app.allfind.ai",                        # AllFind production frontend
    "https://docusense-web.azurestaticapps.net",     # Legacy Azure Static Web Apps
    "https://*.teams.microsoft.com"                  # Teams tab iframe
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    query: str

class AdminSettings(BaseModel):
    region: str
    retentionDays: int

# Environment-based auth selection
USE_SIMPLE_AUTH = os.getenv("USE_SIMPLE_AUTH", "false").lower() == "true"

# Simple auth dependency for testing (no real auth)
def simple_auth_dependency():
    return {
        "sub": "test-user-123",
        "name": "Test User",
        "preferred_username": "test@example.com",
        "roles": ["TenantAdmin"],  # For testing admin functionality
        "tid": "default"  # Use default tenant to match sample data
    }

# Production auth dependency
def production_auth_dependency():
    """Use real JWT validation for production"""
    return auth_dependency

# Dynamic auth dependency based on environment
def get_auth_dependency():
    """Return appropriate auth dependency based on environment"""
    if USE_SIMPLE_AUTH:
        print("🔧 Using simple auth for development")
        return simple_auth_dependency
    else:
        print("🔐 Using production JWT authentication")
        return lenient_auth_dependency

# Get the current auth dependency
current_auth_dependency = get_auth_dependency()

def check_admin_role(user_claims):
    """Check if user has admin role"""
    roles = user_claims.get("roles", [])
    is_admin = "TenantAdmin" in roles
    
    # For development/testing, also allow if no roles are present
    if USE_SIMPLE_AUTH and not roles:
        print("Warning: No roles found in token, allowing admin access for development")
        return True
    
    return is_admin

def get_tenant_id_from_claims(user_claims):
    """Extract tenant ID from user claims"""
    return user_claims.get("tid", "default")

# Health check endpoint
@app.get("/health")
async def health():
    auth_mode = "simple" if USE_SIMPLE_AUTH else "production"
    return {
        "status": "healthy", 
        "message": "AllFind API is running",
        "auth_mode": auth_mode
    }

# Simple search endpoint for testing
@app.post("/search")
async def search(req: SearchRequest, user_claims=Depends(current_auth_dependency)):
    # Mock search results
    mock_results = [
        {
            "title": "Teams Integration Guide",
            "snippet": "Learn how to integrate AllFind with Microsoft Teams...",
            "score": 0.95
        },
        {
            "title": "Sample Document",
            "snippet": "This is a sample document for testing search functionality...",
            "score": 0.87
        }
    ]
    
    return {
        "query": req.query,
        "user": user_claims.get("name", "Unknown"),
        "results": mock_results
    }

# Admin Settings Endpoints (NOW USING LIVE DATA)
@app.get("/admin/settings")
async def get_admin_settings(user_claims=Depends(current_auth_dependency)):
    """Get current admin settings"""
    if not check_admin_role(user_claims):
        user_roles = user_claims.get("roles", [])
        print(f"Access denied for user {user_claims.get('preferred_username', 'unknown')}, roles: {user_roles}")
        raise HTTPException(status_code=403, detail="TenantAdmin role required")
    
    tenant_id = get_tenant_id_from_claims(user_claims)
    print(f"Admin settings accessed by {user_claims.get('preferred_username', 'unknown')} for tenant {tenant_id}")
    
    # Get live settings from storage
    settings = get_tenant_settings(tenant_id)
    
    return {
        "region": settings.get("region", "eastus"),
        "retentionDays": settings.get("retentionDays", 90)
    }

@app.patch("/admin/settings")
async def update_admin_settings(settings: AdminSettings, user_claims=Depends(current_auth_dependency)):
    """Update admin settings"""
    if not check_admin_role(user_claims):
        raise HTTPException(status_code=403, detail="TenantAdmin role required")
    
    tenant_id = get_tenant_id_from_claims(user_claims)
    print(f"Admin settings updated by {user_claims.get('preferred_username', 'unknown')} for tenant {tenant_id}")
    
    # Update live settings in storage
    updated_settings = update_tenant_settings(tenant_id, settings.model_dump())
    
    return {
        "region": updated_settings.get("region", "eastus"),
        "retentionDays": updated_settings.get("retentionDays", 90),
        "lastModified": updated_settings.get("lastModified")
    }

# Webhooks Endpoint (NOW USING LIVE DATA)
@app.get("/admin/webhooks")
async def get_webhooks(user_claims=Depends(current_auth_dependency)):
    """Get active webhook subscriptions"""
    if not check_admin_role(user_claims):
        raise HTTPException(status_code=403, detail="TenantAdmin role required")
    
    tenant_id = get_tenant_id_from_claims(user_claims)
    print(f"Webhook subscriptions accessed by {user_claims.get('preferred_username', 'unknown')} for tenant {tenant_id}")
    
    # Get live webhook data
    webhook_data = get_webhook_subscriptions(tenant_id)
    
    return webhook_data

# Usage Endpoint (NOW USING LIVE DATA)
@app.get("/admin/usage")
async def get_usage(user_claims=Depends(current_auth_dependency)):
    """Get usage statistics and costs"""
    if not check_admin_role(user_claims):
        raise HTTPException(status_code=403, detail="TenantAdmin role required")
    
    tenant_id = get_tenant_id_from_claims(user_claims)
    print(f"Usage statistics accessed by {user_claims.get('preferred_username', 'unknown')} for tenant {tenant_id}")
    
    # Get live usage statistics
    usage_stats = get_usage_statistics(tenant_id)
    
    return usage_stats

# Audit Log Endpoint (NOW USING LIVE DATA)
@app.get("/admin/auditlog")
async def get_audit_log(from_date: str, to_date: str, user_claims=Depends(current_auth_dependency)):
    """Download audit log as CSV"""
    if not check_admin_role(user_claims):
        raise HTTPException(status_code=403, detail="TenantAdmin role required")
    
    tenant_id = get_tenant_id_from_claims(user_claims)
    print(f"Audit log accessed by {user_claims.get('preferred_username', 'unknown')} for tenant {tenant_id}, dates: {from_date} to {to_date}")
    
    # Generate live audit log CSV
    csv_content = generate_audit_csv(from_date, to_date, tenant_id)
    
    return PlainTextResponse(content=csv_content, media_type="text/csv")

# Get user info endpoint
@app.get("/me")
async def get_user_info(user_claims=Depends(current_auth_dependency)):
    return {
        "user_id": user_claims.get("sub"),
        "name": user_claims.get("name"),
        "email": user_claims.get("preferred_username"),
        "tenant": user_claims.get("tid"),
        "roles": user_claims.get("roles", [])
    }

# Additional endpoints for testing the live data functionality

@app.get("/admin/debug/settings")
async def debug_all_settings(user_claims=Depends(current_auth_dependency)):
    """Debug endpoint to see all tenant settings"""
    if not check_admin_role(user_claims):
        raise HTTPException(status_code=403, detail="TenantAdmin role required")
    
    # Read the settings file directly for debugging
    try:
        with open("tenant_settings.json", "r") as f:
            all_settings = json.load(f)
        return all_settings
    except Exception as e:
        return {"error": str(e)}

@app.get("/admin/debug/webhooks")
async def debug_all_webhooks(user_claims=Depends(current_auth_dependency)):
    """Debug endpoint to see all webhook subscriptions"""
    if not check_admin_role(user_claims):
        raise HTTPException(status_code=403, detail="TenantAdmin role required")
    
    # Read the webhooks file directly for debugging
    try:
        with open("webhook_subscriptions.json", "r") as f:
            all_webhooks = json.load(f)
        return all_webhooks
    except Exception as e:
        return {"error": str(e)} 