# Production Authentication Setup

## 🎯 **You're Absolutely Right!**

You should be able to test the production authentication flow locally. This guide shows you how to set up and test the real Azure AD authentication that will be used in production.

## 🔄 **Dual Authentication Architecture**

DocuSense now supports both authentication modes:

### 1. **Simple Auth (Development)**

- Mock authentication for rapid development
- No Azure AD setup required
- Bypasses JWT validation
- Perfect for feature development

### 2. **Production Auth (Azure AD)**

- Real JWT token validation
- Full Azure AD integration
- Multi-tenant support
- Identical to production behavior

## 🚀 **Quick Setup**

### Option A: Automated Setup (Recommended)

```bash
# 1. Set up Azure AD app registrations automatically
./setup_azure_ad_local.sh

# 2. Toggle to production auth mode
./toggle_auth_mode.sh
# Choose option 2 (Production Auth)

# 3. Restart servers to apply changes
```

### Option B: Manual Setup

1. **Create Azure AD App Registrations** (see detailed steps below)
2. **Update Environment Files** with your app registration details
3. **Toggle Auth Mode** using the scripts or manually

## 📋 **Detailed Setup Steps**

### 1. **Azure AD App Registrations**

You need two app registrations:

#### **API App Registration** (Backend)

```bash
# Create API app
az ad app create \
  --display-name "DocuSense-API-Local" \
  --identifier-uris "api://docusense-api-local"

# Add API scope "api.access"
# Add app role "TenantAdmin"
```

#### **SPA App Registration** (Frontend)

```bash
# Create SPA app
az ad app create \
  --display-name "DocuSense-SPA-Local" \
  --spa-redirect-uris "http://localhost:3000" "http://localhost:3000/auth"

# Add API permissions to call your API
# Add Microsoft Graph User.Read permission
```

### 2. **Environment Configuration**

#### **Frontend** (`.env.local`)

```env
REACT_APP_API_BASE=http://localhost:8001

# Azure AD Configuration
REACT_APP_SPACLIENT_ID=your-spa-client-id
REACT_APP_TENANT_ID=your-tenant-id
REACT_APP_API_CLIENT_ID=your-api-client-id

# Enable production auth
REACT_APP_USE_PROD_AUTH=true
```

#### **Backend** (`.env`)

```env
# Use production auth
USE_SIMPLE_AUTH=false

# Azure AD Configuration
AAD_TENANT_ID=your-tenant-id
AAD_CLIENT_ID=your-api-client-id
AUTH_DEBUG=true
```

### 3. **Grant Admin Consent**

**Critical Step**: In Azure Portal:

1. Go to **Azure Active Directory** → **App Registrations**
2. Find your **SPA app** → **API Permissions**
3. Click **"Grant admin consent for [Tenant]"**

Without this, authentication will fail!

## 🔧 **Testing Both Modes**

### **Current Status Check**

```bash
# Check what mode you're in
curl http://localhost:8001/health | jq .auth_mode

# View configuration
./toggle_auth_mode.sh
# Choose option 3 (Show current status)
```

### **Switch Between Modes**

```bash
# Quick toggle
./toggle_auth_mode.sh

# Manual toggle
# For Simple Auth:
echo "USE_SIMPLE_AUTH=true" > docusense-backend/.env
echo "REACT_APP_USE_PROD_AUTH=false" >> docusense-frontend/.env.local

# For Production Auth:
echo "USE_SIMPLE_AUTH=false" > docusense-backend/.env
echo "REACT_APP_USE_PROD_AUTH=true" >> docusense-frontend/.env.local
```

## 🔍 **How Authentication Works**

### **Frontend Logic**

```typescript
// Check auth mode from environment
const isLocalDev = process.env.REACT_APP_API_BASE?.includes('localhost');
const useProdAuth = process.env.REACT_APP_USE_PROD_AUTH === 'true';
const shouldUseAuth = !isLocalDev || useProdAuth;

if (shouldUseAuth) {
  // Use MSAL for Azure AD authentication
  const response = await instance.acquireTokenSilent({...});
  headers.Authorization = `Bearer ${response.accessToken}`;
} else {
  // No auth header needed (simple auth)
}
```

### **Backend Logic**

```python
# Environment-based auth selection
USE_SIMPLE_AUTH = os.getenv("USE_SIMPLE_AUTH", "false").lower() == "true"

def get_auth_dependency():
    if USE_SIMPLE_AUTH:
        return simple_auth_dependency  # Mock auth
    else:
        return lenient_auth_dependency  # Real JWT validation
```

## 🎮 **User Experience**

### **Simple Auth Mode**

- ✅ No sign-in required
- ✅ Instant access to all features
- ✅ Mock user: "Test User"
- ✅ Mock roles: ["TenantAdmin"]

### **Production Auth Mode**

- 🔐 Azure AD sign-in popup
- 🔐 Real user authentication
- 🔐 JWT token validation
- 🔐 Role-based access control
- 🔐 Multi-tenant support

## 📊 **Visual Indicators**

The frontend shows your current auth status:

```
🔧 Simple Auth (Local Development)
🔐 Authenticated as John Doe
🔑 Production Auth (Not Signed In)
```

Plus detailed configuration info in the blue info panel.

## 🚨 **Troubleshooting**

### **Common Issues**

#### **"Invalid token" errors**

- ✅ Check Azure AD app registration configuration
- ✅ Verify redirect URIs include `http://localhost:3000`
- ✅ Ensure admin consent is granted
- ✅ Check tenant ID and client IDs match

#### **"Missing permission" errors**

- ✅ Add API permissions in Azure Portal
- ✅ Grant admin consent
- ✅ Verify API scope is "api.access"

#### **CORS errors**

- ✅ Backend CORS already configured for localhost:3000
- ✅ Check browser network tab for actual error

#### **Frontend not using auth**

- ✅ Verify `REACT_APP_USE_PROD_AUTH=true` in `.env.local`
- ✅ Restart React dev server after env changes
- ✅ Check browser console for MSAL errors

### **Debug Commands**

```bash
# Check backend auth mode
curl http://localhost:8001/health

# Check frontend environment
# Open browser console and type:
console.log(process.env)

# Check JWT token (in browser console after login)
localStorage.getItem('msal.token.keys')
```

## 🎯 **Why This Proves Production Will Work**

### **1. Identical Code Paths**

- Same JWT validation logic (`auth_verified.py`)
- Same MSAL configuration (`authConfig.ts`)
- Same token acquisition flow
- Same role-based access control

### **2. Real Azure AD Integration**

- Actual app registrations
- Real JWT tokens
- Proper signature validation
- Multi-tenant architecture

### **3. Production Environment Variables**

- Same configuration pattern
- Same environment variable names
- Same fallback logic

### **4. Comprehensive Testing**

```bash
# Test both modes work
./toggle_auth_mode.sh  # Switch to simple
curl http://localhost:8001/search  # Should work

./toggle_auth_mode.sh  # Switch to production
curl http://localhost:8001/search  # Should require auth
```

## 📈 **Production Deployment Confidence**

When you deploy to production:

1. **Frontend**: Environment variables automatically switch to production URLs
2. **Backend**: `USE_SIMPLE_AUTH` defaults to `false` (production auth)
3. **Azure AD**: Same app registrations, different redirect URIs
4. **JWT Validation**: Identical code, different issuer URLs

The authentication flow you test locally **IS** the production flow!

## 🎉 **Summary**

You now have:

- ✅ **Dual auth modes** (simple + production)
- ✅ **Quick toggle scripts** for easy testing
- ✅ **Automated Azure AD setup**
- ✅ **Visual auth status indicators**
- ✅ **Comprehensive troubleshooting**
- ✅ **Production confidence** through identical code paths

Test both modes to verify the production authentication works exactly as expected!
