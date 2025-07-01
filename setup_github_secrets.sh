#!/bin/bash
# AllFind GitHub Secrets Setup Helper
# This script helps configure the required secrets for CI/CD deployment

set -e

echo "🔐 AllFind GitHub Secrets Setup"
echo "==============================="
echo

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is required but not installed."
    echo "   Install it from: https://cli.github.com/"
    exit 1
fi

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI (az) is required but not installed."
    echo "   Install it from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Verify GitHub authentication
echo "🔍 Checking GitHub authentication..."
if ! gh auth status &> /dev/null; then
    echo "❌ Please authenticate with GitHub first:"
    echo "   gh auth login"
    exit 1
fi

# Verify Azure authentication
echo "🔍 Checking Azure authentication..."
if ! az account show &> /dev/null; then
    echo "❌ Please authenticate with Azure first:"
    echo "   az login"
    exit 1
fi

echo "✅ Prerequisites verified"
echo

# Get repository information
REPO_OWNER=$(gh repo view --json owner --jq .owner.login)
REPO_NAME=$(gh repo view --json name --jq .name)
echo "📦 Repository: $REPO_OWNER/$REPO_NAME"
echo

# Create service principal for CI/CD
echo "🔧 Creating Azure service principal..."
SP_NAME="AllFind-CI-CD-$(date +%s)"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

echo "   Creating service principal: $SP_NAME"
SP_JSON=$(az ad sp create-for-rbac \
    --name "$SP_NAME" \
    --role contributor \
    --scopes "/subscriptions/$SUBSCRIPTION_ID" \
    --sdk-auth)

echo "✅ Service principal created"

# Set AZURE_CREDENTIALS secret
echo "🔑 Setting AZURE_CREDENTIALS secret..."
gh secret set AZURE_CREDENTIALS --body "$SP_JSON"
echo "✅ AZURE_CREDENTIALS secret set"

# Get API base URL
echo
echo "🌐 API Base URL Configuration"
echo "Please provide your API base URL (e.g., https://allfind-api-prod.azurewebsites.net):"
read -p "API_BASE_URL: " API_BASE_URL

if [[ -z "$API_BASE_URL" ]]; then
    echo "⚠️  Using default: https://allfind-api-prod.azurewebsites.net"
    API_BASE_URL="https://allfind-api-prod.azurewebsites.net"
fi

gh secret set API_BASE_URL --body "$API_BASE_URL"
echo "✅ API_BASE_URL secret set"

# Static Web App deployment token
echo
echo "🌐 Static Web App Configuration"
echo "To get the SWA_DEPLOY_TOKEN:"
echo "1. Go to Azure Portal"
echo "2. Navigate to your Static Web App"
echo "3. Go to 'Deployment tokens' under 'Settings'"
echo "4. Copy the deployment token"
echo
read -p "SWA_DEPLOY_TOKEN: " SWA_TOKEN

if [[ -z "$SWA_TOKEN" ]]; then
    echo "⚠️  SWA_DEPLOY_TOKEN not provided. You can set it later with:"
    echo "   gh secret set SWA_DEPLOY_TOKEN --body 'YOUR_TOKEN_HERE'"
else
    gh secret set SWA_DEPLOY_TOKEN --body "$SWA_TOKEN"
    echo "✅ SWA_DEPLOY_TOKEN secret set"
fi

# Summary
echo
echo "🎉 Setup Complete!"
echo "=================="
echo
echo "✅ Secrets configured:"
echo "   - AZURE_CREDENTIALS (service principal)"
echo "   - API_BASE_URL ($API_BASE_URL)"
if [[ -n "$SWA_TOKEN" ]]; then
    echo "   - SWA_DEPLOY_TOKEN (configured)"
else
    echo "   - SWA_DEPLOY_TOKEN (⚠️  needs manual setup)"
fi
echo
echo "🚀 Your CI/CD pipeline is ready!"
echo "   Push to main branch to trigger deployment"
echo
echo "📋 Next steps:"
echo "   1. Verify secrets in GitHub repo settings"
echo "   2. Test deployment with: gh workflow run deploy-chatgpt.yml"
echo "   3. Monitor deployment in Actions tab"
echo
echo "🔧 Troubleshooting:"
echo "   - View secrets: gh secret list"
echo "   - Delete secret: gh secret delete SECRET_NAME"
echo "   - View workflows: gh workflow list"
echo

# Cleanup reminder
echo "🧹 Service Principal Info:"
echo "   Name: $SP_NAME"
echo "   To remove later: az ad sp delete --id \$(az ad sp show --display-name '$SP_NAME' --query appId -o tsv)"
echo 