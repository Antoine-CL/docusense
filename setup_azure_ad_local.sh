#!/bin/bash
# Setup Azure AD for Local Production Auth Testing
# This script helps you configure the Azure AD app registrations needed for local testing

set -e

echo "🔐 DocuSense Azure AD Local Setup"
echo "=================================="
echo
echo "This script will help you set up Azure AD authentication for local testing."
echo

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI (az) is required but not installed."
    echo "   Install it from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check Azure authentication
echo "🔍 Checking Azure authentication..."
if ! az account show &> /dev/null; then
    echo "❌ Please authenticate with Azure first:"
    echo "   az login"
    exit 1
fi

echo "✅ Azure CLI authenticated"
echo

# Get tenant information
TENANT_ID=$(az account show --query tenantId -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "📋 Current Azure Context:"
echo "   Tenant ID: $TENANT_ID"
echo "   Subscription: $SUBSCRIPTION_ID"
echo

# Create API App Registration
echo "🔧 Creating API App Registration..."
API_APP_NAME="DocuSense-API-Local"

# Check if app already exists
EXISTING_API_APP=$(az ad app list --display-name "$API_APP_NAME" --query "[0].appId" -o tsv 2>/dev/null || echo "")

if [[ -n "$EXISTING_API_APP" && "$EXISTING_API_APP" != "null" ]]; then
    echo "   Found existing API app: $EXISTING_API_APP"
    API_CLIENT_ID="$EXISTING_API_APP"
else
    echo "   Creating new API app registration..."
    
    # Create the API app registration
    API_CLIENT_ID=$(az ad app create \
        --display-name "$API_APP_NAME" \
        --identifier-uris "api://docusense-api-local" \
        --query appId -o tsv)
    
    echo "   Created API app: $API_CLIENT_ID"
    
    # Add API scope
    echo "   Adding API scope..."
    az ad app update --id "$API_CLIENT_ID" --set api.oauth2PermissionScopes='[
        {
            "adminConsentDescription": "Access DocuSense API",
            "adminConsentDisplayName": "Access DocuSense API",
            "id": "'$(uuidgen)'",
            "isEnabled": true,
            "type": "User",
            "userConsentDescription": "Access DocuSense API",
            "userConsentDisplayName": "Access DocuSense API",
            "value": "api.access"
        }
    ]'
    
    # Add app roles
    echo "   Adding app roles..."
    az ad app update --id "$API_CLIENT_ID" --set appRoles='[
        {
            "allowedMemberTypes": ["User"],
            "description": "Tenant Administrator",
            "displayName": "Tenant Admin",
            "id": "'$(uuidgen)'",
            "isEnabled": true,
            "value": "TenantAdmin"
        }
    ]'
fi

# Create SPA App Registration
echo "🌐 Creating SPA App Registration..."
SPA_APP_NAME="DocuSense-SPA-Local"

# Check if app already exists
EXISTING_SPA_APP=$(az ad app list --display-name "$SPA_APP_NAME" --query "[0].appId" -o tsv 2>/dev/null || echo "")

if [[ -n "$EXISTING_SPA_APP" && "$EXISTING_SPA_APP" != "null" ]]; then
    echo "   Found existing SPA app: $EXISTING_SPA_APP"
    SPA_CLIENT_ID="$EXISTING_SPA_APP"
else
    echo "   Creating new SPA app registration..."
    
    # Create the SPA app registration
    SPA_CLIENT_ID=$(az ad app create \
        --display-name "$SPA_APP_NAME" \
        --spa-redirect-uris "http://localhost:3000" "http://localhost:3000/auth" \
        --query appId -o tsv)
    
    echo "   Created SPA app: $SPA_CLIENT_ID"
    
    # Configure API permissions
    echo "   Configuring API permissions..."
    
    # Add permission to call our API
    az ad app permission add \
        --id "$SPA_CLIENT_ID" \
        --api "$API_CLIENT_ID" \
        --api-permissions "$(az ad app show --id "$API_CLIENT_ID" --query "api.oauth2PermissionScopes[0].id" -o tsv)=Scope"
    
    # Add Microsoft Graph permissions
    az ad app permission add \
        --id "$SPA_CLIENT_ID" \
        --api 00000003-0000-0000-c000-000000000000 \
        --api-permissions e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope  # User.Read
fi

# Update environment files
echo "📝 Updating environment files..."

# Update frontend .env.local
cat > docusense-frontend/.env.local << EOF
REACT_APP_API_BASE=http://localhost:8001

# Azure AD Configuration for Local Testing
REACT_APP_SPACLIENT_ID=$SPA_CLIENT_ID
REACT_APP_TENANT_ID=$TENANT_ID
REACT_APP_API_CLIENT_ID=$API_CLIENT_ID

# Set to true to test production auth locally
REACT_APP_USE_PROD_AUTH=false
EOF

# Update backend .env
cat > docusense-backend/.env << EOF
# Authentication Mode (set to false to use production JWT auth)
USE_SIMPLE_AUTH=true

# Azure AD Configuration for Production Auth
AAD_TENANT_ID=$TENANT_ID
AAD_CLIENT_ID=$API_CLIENT_ID

# Optional: Enable debug logging for auth
AUTH_DEBUG=true
EOF

echo "✅ Environment files updated"
echo

# Summary
echo "🎉 Setup Complete!"
echo "=================="
echo
echo "✅ Azure AD App Registrations:"
echo "   API App ID: $API_CLIENT_ID"
echo "   SPA App ID: $SPA_CLIENT_ID"
echo "   Tenant ID: $TENANT_ID"
echo
echo "✅ Environment files updated:"
echo "   Frontend: docusense-frontend/.env.local"
echo "   Backend: docusense-backend/.env"
echo
echo "🔧 Testing Options:"
echo "   1. Simple Auth (Current): Both servers will use mock auth"
echo "   2. Production Auth: Set environment variables and restart servers"
echo
echo "📋 To test production auth locally:"
echo "   1. Set REACT_APP_USE_PROD_AUTH=true in docusense-frontend/.env.local"
echo "   2. Set USE_SIMPLE_AUTH=false in docusense-backend/.env"
echo "   3. Restart both frontend and backend servers"
echo "   4. You'll be prompted to sign in with your Azure AD account"
echo
echo "🔑 Admin Access:"
echo "   To test admin features, assign the 'TenantAdmin' role to your user:"
echo "   1. Go to Azure Portal → Azure Active Directory → App Registrations"
echo "   2. Find '$API_APP_NAME' → App roles → Assign users"
echo "   3. Assign yourself the 'Tenant Admin' role"
echo
echo "🌐 Redirect URIs configured:"
echo "   - http://localhost:3000"
echo "   - http://localhost:3000/auth"
echo
echo "⚠️  Important: Grant admin consent for API permissions in Azure Portal"
echo "   Go to: Azure Portal → App Registrations → $SPA_APP_NAME → API permissions → Grant admin consent"
echo 