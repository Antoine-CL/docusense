from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from azure_search_client import search_docs
from auth_verified import auth_dependency, lenient_auth_dependency
from datetime import datetime, timedelta
import json

app = FastAPI(title="AllFind API", version="1.0.0")

# Add CORS middleware for development and production
origins = [
    "http://localhost:3000",                         # Local development
    "https://docusense-web.azurestaticapps.net",     # Azure Static Web Apps (update with actual URL)
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

# Mock data for admin endpoints (replace with actual database/storage in production)
MOCK_ADMIN_SETTINGS = {
    "region": "eastus",
    "retentionDays": 90
}

MOCK_WEBHOOKS = [
    {
        "id": "12345678-1234-1234-1234-123456789012",
        "resource": "/me/drive/root",
        "changeType": "created,updated,deleted",
        "notificationUrl": "https://your-webhook-endpoint.com/webhook",
        "expirationDateTime": (datetime.now() + timedelta(days=2)).isoformat() + "Z",
        "clientState": "tenant-abc123"
    },
    {
        "id": "87654321-4321-4321-4321-210987654321",
        "resource": "/sites/root/drives/b!abc123/root",
        "changeType": "created,updated,deleted",
        "notificationUrl": "https://your-webhook-endpoint.com/webhook",
        "expirationDateTime": (datetime.now() + timedelta(hours=12)).isoformat() + "Z",
        "clientState": "tenant-abc123"
    }
]

MOCK_USAGE_DATA = {
    "documentsIndexed": 1247,
    "totalEmbeddings": 15623,
    "searchRequests": 892,
    "storageUsedMB": 2847,
    "estimatedMonthlyCost": 127.45,
    "lastUpdated": datetime.now().isoformat() + "Z"
}

def check_admin_role(user_claims):
    """Check if user has admin role"""
    roles = user_claims.get("roles", [])
    
    # Check for TenantAdmin role
    is_admin = "TenantAdmin" in roles
    
    # For development/testing, also allow if no roles are present (fallback)
    # In production, remove this fallback and require proper role assignment
    if not roles:
        print("Warning: No roles found in token, allowing admin access for development")
        return True
    
    return is_admin

# Health check endpoint (no auth required)
@app.get("/health")
async def health():
    return {"status": "healthy", "message": "AllFind API is running"}

# Protected search endpoint (requires Azure AD token with specific scope)
@app.post("/search", dependencies=[Depends(auth_dependency)])
async def search(req: SearchRequest, user_claims=Depends(auth_dependency)):
    results = search_docs(req.query)
    
    return {
        "query": req.query,
        "user": user_claims.get("name", user_claims.get("preferred_username", "Unknown")),
        "results": [
            {
                "title": match["metadata"].get("title") if "metadata" in match else None,
                "snippet": match["metadata"].get("snippet") if "metadata" in match else None,
                "score": match["score"]
            } for match in results
        ]
    }

# Lenient search endpoint (accepts Graph API tokens for testing)
@app.post("/search-auth")
async def search_with_auth(req: SearchRequest, user_claims=Depends(lenient_auth_dependency)):
    results = search_docs(req.query)
    
    return {
        "query": req.query,
        "user": user_claims.get("name", user_claims.get("preferred_username", "Unknown")),
        "token_type": "Graph API" if user_claims.get("aud") == "https://graph.microsoft.com" else "Custom API",
        "results": [
            {
                "title": match["metadata"].get("title") if "metadata" in match else None,
                "snippet": match["metadata"].get("snippet") if "metadata" in match else None,
                "score": match["score"]
            } for match in results
        ]
    }

# Admin Settings Endpoints
@app.get("/admin/settings", dependencies=[Depends(lenient_auth_dependency)])
async def get_admin_settings(user_claims=Depends(lenient_auth_dependency)):
    """Get current admin settings"""
    if not check_admin_role(user_claims):
        user_roles = user_claims.get("roles", [])
        print(f"Access denied for user {user_claims.get('preferred_username', 'unknown')}, roles: {user_roles}")
        raise HTTPException(status_code=403, detail="TenantAdmin role required")
    
    print(f"Admin settings accessed by {user_claims.get('preferred_username', 'unknown')}")
    return MOCK_ADMIN_SETTINGS

@app.patch("/admin/settings", dependencies=[Depends(lenient_auth_dependency)])
async def update_admin_settings(settings: AdminSettings, user_claims=Depends(lenient_auth_dependency)):
    """Update admin settings"""
    if not check_admin_role(user_claims):
        raise HTTPException(status_code=403, detail="Admin role required")
    
    # Update mock settings
    MOCK_ADMIN_SETTINGS.update(settings.dict())
    
    # In production, this would trigger background reprocessing
    print(f"Admin settings updated: {settings.dict()}")
    
    return MOCK_ADMIN_SETTINGS

# Webhooks Endpoint
@app.get("/admin/webhooks", dependencies=[Depends(lenient_auth_dependency)])
async def get_webhooks(user_claims=Depends(lenient_auth_dependency)):
    """Get active webhook subscriptions"""
    if not check_admin_role(user_claims):
        raise HTTPException(status_code=403, detail="Admin role required")
    
    return {"subscriptions": MOCK_WEBHOOKS}

# Usage Endpoint
@app.get("/admin/usage", dependencies=[Depends(lenient_auth_dependency)])
async def get_usage(user_claims=Depends(lenient_auth_dependency)):
    """Get usage statistics and costs"""
    if not check_admin_role(user_claims):
        raise HTTPException(status_code=403, detail="Admin role required")
    
    return MOCK_USAGE_DATA

# Audit Log Endpoint
@app.get("/admin/auditlog", dependencies=[Depends(lenient_auth_dependency)])
async def get_audit_log(from_date: str, to_date: str, user_claims=Depends(lenient_auth_dependency)):
    """Download audit log as CSV"""
    if not check_admin_role(user_claims):
        raise HTTPException(status_code=403, detail="Admin role required")
    
    # Generate mock CSV data
    csv_content = "timestamp,event_type,user,details,result\n"
    csv_content += f"{datetime.now().isoformat()},search,john.doe@example.com,\"query: teams integration\",success\n"
    csv_content += f"{(datetime.now() - timedelta(hours=1)).isoformat()},document_ingestion,system,\"file: sample_document.txt\",success\n"
    csv_content += f"{(datetime.now() - timedelta(hours=2)).isoformat()},authentication,jane.smith@example.com,\"login via Teams\",success\n"
    csv_content += f"{(datetime.now() - timedelta(hours=3)).isoformat()},admin_settings,admin@example.com,\"changed region to westeurope\",success\n"
    csv_content += f"{(datetime.now() - timedelta(hours=4)).isoformat()},search,bob.wilson@example.com,\"query: quarterly report\",success\n"
    
    return PlainTextResponse(content=csv_content, media_type="text/csv")

# Test endpoint for development (no auth required - remove in production)
# @app.post("/search-test")
# async def search_test(req: SearchRequest):
#     """Test endpoint without authentication - remove in production"""
#     results = search_docs(req.query)
#     
#     return [
#         {
#             "title": match["metadata"].get("title") if "metadata" in match else None,
#             "snippet": match["metadata"].get("snippet") if "metadata" in match else None,
#             "score": match["score"]
#         } for match in results
#     ]

# Get user info endpoint (requires auth)
@app.get("/me", dependencies=[Depends(lenient_auth_dependency)])
async def get_user_info(user_claims=Depends(lenient_auth_dependency)):
    return {
        "user_id": user_claims.get("sub"),
        "name": user_claims.get("name"),
        "email": user_claims.get("preferred_username"),
        "tenant": user_claims.get("tid"),
        "audience": user_claims.get("aud"),
        "token_type": "Graph API" if user_claims.get("aud") == "https://graph.microsoft.com" else "Custom API",
        "scopes": user_claims.get("scp", "").split() if user_claims.get("scp") else user_claims.get("roles", [])
    }
