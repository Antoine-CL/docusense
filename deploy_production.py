#!/usr/bin/env python3
"""
Production deployment script for DocuSense.
Deploys the complete infrastructure to Azure.
"""

import subprocess
import json
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return the result."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        sys.exit(1)

def get_azure_resources():
    """Get existing Azure resource details."""
    print("📋 Gathering existing Azure resources...")
    
    # Get OpenAI details
    openai_endpoint = run_command(
        "az cognitiveservices account show --name docusense-azure-open-ai --resource-group DocuSense --query 'properties.endpoint' --output tsv",
        "Getting Azure OpenAI endpoint"
    )
    
    openai_key = run_command(
        "az cognitiveservices account keys list --name docusense-azure-open-ai --resource-group DocuSense --query 'key1' --output tsv",
        "Getting Azure OpenAI API key"
    )
    
    # Get tenant ID
    tenant_id = run_command(
        "az account show --query tenantId --output tsv",
        "Getting Azure tenant ID"
    )
    
    # Azure AD app IDs (from our previous setup)
    api_client_id = "1c709570-f530-46ac-a366-db21f372cd53"  # DocuSense-API
    spa_client_id = "be330402-0ba6-4ba0-8cf8-66e2e44018f9"  # DocuSense SPA
    
    return {
        "openai_endpoint": openai_endpoint,
        "openai_key": openai_key,
        "tenant_id": tenant_id,
        "api_client_id": api_client_id,
        "spa_client_id": spa_client_id
    }

def deploy_infrastructure(resources):
    """Deploy the Bicep template with gathered parameters."""
    print("🚀 Deploying DocuSense infrastructure...")
    
    # We need a client secret for the API app - let's create one
    print("🔑 Creating client secret for API app...")
    client_secret_result = run_command(
        f"az ad app credential reset --id {resources['api_client_id']} --query password --output tsv",
        "Creating client secret"
    )
    
    # Prepare deployment parameters
    params = [
        f"envName=prod",
        f"openAiApiKey={resources['openai_key']}",
        f"openAiEndpoint={resources['openai_endpoint']}",
        f"graphClientId={resources['api_client_id']}",
        f"graphClientSecret={client_secret_result}",
        f"tenantId={resources['tenant_id']}",
        f"adminEmail=antoine@wonderlabs.ca"  # Update this to your email
    ]
    
    # Deploy the Bicep template
    deployment_cmd = f"az deployment group create --resource-group DocuSense --template-file docusense.bicep --parameters {' '.join(params)}"
    
    print("📦 Deploying infrastructure (this may take 5-10 minutes)...")
    result = run_command(deployment_cmd, "Deploying Bicep template")
    
    # Parse deployment outputs
    outputs = json.loads(result)['properties']['outputs']
    
    return {
        "api_url": outputs['apiEndpoint']['value'],
        "spa_url": outputs['spaUrl']['value'],
        "function_url": outputs['functionEndpoint']['value'],
        "webhook_url": outputs['webhookUrl']['value'],
        "search_endpoint": outputs['searchEndpoint']['value']
    }

def update_environment_files(resources, deployment_outputs):
    """Update environment files with production URLs."""
    print("📝 Updating environment files...")
    
    # Update backend .env
    backend_env = f"""# Production Environment Configuration
# Azure AD Configuration
AAD_TENANT_ID={resources['tenant_id']}
AAD_CLIENT_ID={resources['api_client_id']}

# Auth Mode (production)
USE_SIMPLE_AUTH=false

# Azure Resources
AZURE_SEARCH_ENDPOINT={deployment_outputs['search_endpoint']}
AZURE_OPENAI_ENDPOINT={resources['openai_endpoint']}
"""
    
    with open("docusense-backend/.env.prod", "w") as f:
        f.write(backend_env)
    
    # Update frontend .env
    frontend_env = f"""# Production Environment Configuration
REACT_APP_API_BASE={deployment_outputs['api_url']}
REACT_APP_SPACLIENT_ID={resources['spa_client_id']}
REACT_APP_TENANT_ID={resources['tenant_id']}
REACT_APP_API_CLIENT_ID={resources['api_client_id']}
REACT_APP_USE_PROD_AUTH=true
"""
    
    with open("docusense-frontend/.env.production", "w") as f:
        f.write(frontend_env)
    
    print("✅ Environment files updated")

def main():
    """Main deployment function."""
    print("🚀 DocuSense Production Deployment")
    print("=" * 50)
    
    # Check if logged into Azure
    try:
        run_command("az account show", "Checking Azure login")
    except:
        print("❌ Please run 'az login' first")
        sys.exit(1)
    
    # Gather resources
    resources = get_azure_resources()
    
    # Deploy infrastructure
    deployment_outputs = deploy_infrastructure(resources)
    
    # Update environment files
    update_environment_files(resources, deployment_outputs)
    
    print("\n🎉 Deployment Complete!")
    print("=" * 50)
    print(f"📱 Frontend URL: {deployment_outputs['spa_url']}")
    print(f"🔗 API URL: {deployment_outputs['api_url']}")
    print(f"🪝 Webhook URL: {deployment_outputs['webhook_url']}")
    print(f"🔍 Search Endpoint: {deployment_outputs['search_endpoint']}")
    
    print("\n📋 Next Steps:")
    print("1. 🌐 Set up custom domains:")
    print(f"   - Point app.docusense.ai → {deployment_outputs['spa_url']}")
    print(f"   - Point api.docusense.ai → {deployment_outputs['api_url']}")
    print("2. 🚀 Deploy code using GitHub Actions")
    print("3. 📊 Monitor alerts in Azure Portal")
    
    print("\n✅ All Production Blockers Resolved!")

if __name__ == "__main__":
    main() 