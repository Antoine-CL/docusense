# DocuSense Azure AD Setup Guide

This guide walks you through setting up Azure AD authentication and Microsoft Graph API access for DocuSense.

## 🔐 Step 1: Azure AD App Registration

### 1.1 Create App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**
4. Fill in the details:
   - **Name**: `DocuSense-API`
   - **Supported account types**: `Accounts in this organizational directory only (Single tenant)`
   - **Redirect URI**: Leave blank for now
5. Click **Register**

### 1.2 Record Application Details

After registration, note down these values from the **Overview** page:

- **Application (client) ID**: Copy this value
- **Directory (tenant) ID**: Copy this value

### 1.3 Create Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Add description: `DocuSense API Secret`
4. Set expiration: `24 months` (or as per your policy)
5. Click **Add**
6. **⚠️ IMPORTANT**: Copy the secret **Value** immediately (it won't be shown again)

### 1.4 Configure API Permissions

1. Go to **API permissions**
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Choose **Application permissions**
5. Add these permissions:
   - `Files.Read.All` - Read files in all site collections
   - `Sites.Read.All` - Read items in all site collections
   - `User.Read.All` - Read all users' profiles (optional)
6. Click **Add permissions**
7. **⚠️ CRITICAL**: Click **Grant admin consent** and confirm

### 1.5 Expose an API (for frontend integration)

1. Go to **Expose an API**
2. Click **Set** next to Application ID URI
3. Accept the default or customize: `api://your-client-id`
4. Click **Add a scope**:
   - **Scope name**: `api.access`
   - **Admin consent display name**: `Access DocuSense API`
   - **Admin consent description**: `Allows access to DocuSense search functionality`
   - **State**: `Enabled`
5. Click **Add scope**

## 🔧 Step 2: Update Environment Configuration

### 2.1 Update .env file

Replace the placeholder values in your `.env` file:

```bash
# Replace these values with your actual Azure AD app details
AAD_CLIENT_ID=your-application-client-id-here
AAD_TENANT_ID=your-directory-tenant-id-here
AAD_CLIENT_SECRET=your-client-secret-value-here
```

### 2.2 Verify Configuration

Run this command to test your Azure AD setup:

```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('Client ID:', os.getenv('AAD_CLIENT_ID'))
print('Tenant ID:', os.getenv('AAD_TENANT_ID'))
print('Secret set:', 'Yes' if os.getenv('AAD_CLIENT_SECRET') else 'No')
"
```

## 🧪 Step 3: Test the Setup

### 3.1 Test Graph API Connection

```bash
python ingest_onedrive.py
```

This will test:

- ✅ Token acquisition
- ✅ Drive access
- ✅ File listing permissions

### 3.2 Test API Endpoints

**Health Check (no auth required):**

```bash
curl -X GET "http://127.0.0.1:8001/health"
```

**Protected Search (requires token):**

```bash
curl -X POST "http://127.0.0.1:8001/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
# Should return: {"detail":"Not authenticated"}
```

**Unprotected Search (for testing):**

```bash
curl -X POST "http://127.0.0.1:8001/search-test" \
  -H "Content-Type: application/json" \
  -d '{"query": "Teams integration"}'
```

## 🔑 Step 4: Get Access Token (for testing)

### 4.1 Using PowerShell (Windows)

```powershell
$clientId = "your-client-id"
$tenantId = "your-tenant-id"
$clientSecret = "your-client-secret"
$scope = "api://your-client-id/api.access"

$body = @{
    client_id = $clientId
    client_secret = $clientSecret
    scope = $scope
    grant_type = "client_credentials"
}

$response = Invoke-RestMethod -Uri "https://login.microsoftonline.com/$tenantId/oauth2/v2.0/token" -Method Post -Body $body
$token = $response.access_token
Write-Host "Token: $token"
```

### 4.2 Using curl (Linux/Mac)

```bash
curl -X POST "https://login.microsoftonline.com/YOUR_TENANT_ID/oauth2/v2.0/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET&scope=api://YOUR_CLIENT_ID/api.access&grant_type=client_credentials"
```

### 4.3 Test with Token

```bash
curl -X POST "http://127.0.0.1:8001/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"query": "Teams integration"}'
```

## 📁 Step 5: OneDrive Integration

### 5.1 Test OneDrive Access

```bash
python ingest_onedrive.py
```

### 5.2 Run OneDrive Ingestion

Once authentication is working, the script will:

1. List available drives
2. Find supported documents (PDF, DOCX, PPTX, TXT)
3. Download and process files
4. Create embeddings and index in Azure Search

## 🚀 Step 6: Teams App Packaging & Publishing

### 6.1 Production CORS Configuration

Update your FastAPI `main.py` to support production origins:

```python
# main.py - Add production origins to CORS
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
```

### 6.2 Build React for Production

```bash
cd docusense-frontend
npm run build
```

This creates an optimized production build in the `build/` folder.

### 6.3 Deploy Frontend to Azure Static Web Apps

1. **Create Azure Static Web App**:

   - Go to [Azure Portal](https://portal.azure.com)
   - Create new **Static Web App**
   - Connect to your GitHub repository
   - Set build folder: `docusense-frontend/build`

2. **Update CORS with actual URL**:
   - Replace `docusense-web.azurestaticapps.net` with your actual Static Web App URL
   - Restart FastAPI backend

### 6.4 Deploy Backend to Azure

**Option A: Azure Container Apps**

```bash
# Build and deploy container
az containerapp up --name docusense-api --resource-group your-rg --source .
```

**Option B: Azure App Service**

```bash
# Deploy to App Service
az webapp up --name docusense-api --resource-group your-rg
```

### 6.5 Create Teams Manifest

Create `teams-manifest/manifest.json`:

```json
{
  "$schema": "https://developer.microsoft.com/en-us/json-schemas/teams/v1.16/MicrosoftTeams.schema.json",
  "manifestVersion": "1.16",
  "version": "1.0.0",
  "id": "your-spa-client-id",
  "packageName": "com.yourcompany.docusense",
  "developer": {
    "name": "Your Company",
    "websiteUrl": "https://yourcompany.com",
    "privacyUrl": "https://yourcompany.com/privacy",
    "termsOfUseUrl": "https://yourcompany.com/terms"
  },
  "icons": {
    "color": "icon-color.png",
    "outline": "icon-outline.png"
  },
  "name": {
    "short": "DocuSense",
    "full": "DocuSense Document Search"
  },
  "description": {
    "short": "AI-powered document search for Teams",
    "full": "Search your organization's documents using semantic AI search directly within Microsoft Teams."
  },
  "accentColor": "#6264A7",
  "staticTabs": [
    {
      "entityId": "docusense-search",
      "name": "Search",
      "contentUrl": "https://your-static-web-app.azurestaticapps.net/search",
      "websiteUrl": "https://your-static-web-app.azurestaticapps.net",
      "scopes": ["personal", "team"]
    }
  ],
  "permissions": ["identity", "messageTeamMembers"],
  "validDomains": [
    "your-static-web-app.azurestaticapps.net",
    "login.microsoftonline.com"
  ],
  "webApplicationInfo": {
    "id": "your-spa-client-id",
    "resource": "api://your-api-client-id",
    "scopes": ["api.access"]
  }
}
```

### 6.6 Teams Developer Portal Setup

1. **Go to [Teams Developer Portal](https://dev.teams.microsoft.com/)**
2. **Create new app** or **Import manifest**
3. **Configure app details**:
   - Upload icons (32x32 and 192x192 PNG)
   - Set valid domains
   - Configure static tabs
4. **Set permissions**:
   - Add `webApplicationInfo` section
   - Configure OAuth scopes
5. **Download app package** (.zip file)

### 6.7 Test in Teams

1. **Sideload the app**:

   - In Teams, go to **Apps** → **Manage your apps**
   - Click **Upload an app** → **Upload a custom app**
   - Select your app package (.zip)

2. **Test functionality**:
   - Add the app to a team or use personally
   - Verify authentication flow
   - Test document search

### 6.8 Publish to Teams Store

1. **Prepare for submission**:

   - Complete all required manifest fields
   - Add comprehensive app description
   - Include privacy policy and terms of use
   - Test thoroughly in multiple tenants

2. **Submit to Partner Center**:
   - Create Partner Center account
   - Submit app for Microsoft validation
   - Address any feedback from review team

## 🔧 Step 7: Multi-Tenant Configuration

### 7.1 Update Azure AD App Registration

For multi-tenant SaaS deployment:

1. **Change supported account types**:

   - Go to **Authentication** in your Azure AD app
   - Change to **Accounts in any organizational directory (Any Azure AD directory - Multitenant)**

2. **Add production redirect URIs**:

   - `https://your-static-web-app.azurestaticapps.net/auth`
   - `https://*.teams.microsoft.com/auth`

3. **Publisher verification**:
   - Complete publisher verification process
   - Required for Teams Store publication

### 7.2 Customer Onboarding Flow

When customers install your Teams app:

1. **Admin consent required** for organization-wide permissions
2. **Automatic user access** once admin consents
3. **No per-user role assignment** needed

## 🚀 Step 8: Production Checklist

- [ ] Backend deployed to Azure (Container Apps/App Service)
- [ ] Frontend deployed to Azure Static Web Apps
- [ ] CORS configured for production domains
- [ ] Azure AD app configured for multi-tenant
- [ ] Teams manifest created and validated
- [ ] App tested in Teams environment
- [ ] Privacy policy and terms of use published
- [ ] Publisher verification completed
- [ ] App submitted to Teams Store (optional)

## 📞 Support

For deployment issues:

- Check Azure service logs
- Verify environment variables
- Test authentication flows
- Monitor API response codes

## 🔍 Troubleshooting

### Common Issues

**"Failed to acquire token"**

- Check client ID, tenant ID, and secret
- Verify secret hasn't expired
- Ensure no extra spaces in .env values

**"No drives accessible"**

- Verify API permissions are granted
- Check admin consent was given
- Ensure Files.Read.All and Sites.Read.All are present

**"Invalid token"**

- Check token hasn't expired (1 hour default)
- Verify audience matches your client ID
- Ensure correct scope is requested

### Logs and Debugging

- Check FastAPI logs for detailed error messages
- Use Azure AD logs in Azure Portal
- Enable debug logging in MSAL if needed

## 📞 Support

If you encounter issues, check:

1. Azure AD app registration settings
2. API permissions and admin consent
3. Environment variable configuration
4. Network connectivity to Azure services
