#!/usr/bin/env python3
"""
AllFind Production Deployment Script
Deploys with clean, branded resource names
"""

import subprocess
import json
import os
import sys
from datetime import datetime

def run_command(cmd, check=True):
    """Run a command and return the result"""
    print(f"🔧 Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"❌ Command failed: {result.stderr}")
        sys.exit(1)
    return result

def main():
    print("🚀 AllFind Production Deployment")
    print("=" * 50)
    
    # Configuration
    config = {
        "resourceGroup": "AllFind",
        "location": "canadaeast", 
        "appName": "allfind",
        "staticWebApp": "allfind-ui",
        "appService": "allfind-api", 
        "functionApp": "allfind-func",
        "searchService": "allfind-search",
        "keyVault": "allfind-vault"
    }
    
    print(f"📋 Configuration:")
    for key, value in config.items():
        print(f"   {key}: {value}")
    print()
    
    # Check if logged into Azure
    print("🔐 Checking Azure login...")
    result = run_command("az account show", check=False)
    if result.returncode != 0:
        print("❌ Not logged into Azure. Please run: az login")
        sys.exit(1)
    
    account = json.loads(result.stdout)
    print(f"✅ Logged in as: {account['user']['name']}")
    print(f"   Subscription: {account['name']}")
    print()
    
    # Get existing Azure AD apps
    print("🔍 Finding existing Azure AD applications...")
    api_app = run_command("az ad app list --display-name 'DocuSense-API' --query '[0].appId' -o tsv")
    spa_app = run_command("az ad app list --display-name 'DocuSense' --query '[0].appId' -o tsv")
    tenant_id = account['tenantId']
    
    if not api_app.stdout.strip() or not spa_app.stdout.strip():
        print("❌ Azure AD apps not found. Please run setup_azure_ad_local.sh first")
        sys.exit(1)
        
    print(f"✅ API App ID: {api_app.stdout.strip()}")
    print(f"✅ SPA App ID: {spa_app.stdout.strip()}")
    print()
    
    # Create resource group
    print(f"📦 Creating resource group: {config['resourceGroup']}")
    run_command(f"az group create --name {config['resourceGroup']} --location {config['location']}")
    
    # Get OpenAI resource
    print("🤖 Finding OpenAI resource...")
    openai_result = run_command("az cognitiveservices account list --query \"[]\" -o json")
    all_accounts = json.loads(openai_result.stdout)
    
    # Find OpenAI account
    openai_info = None
    for account in all_accounts:
        if account.get('kind') == 'OpenAI':
            openai_info = {
                'name': account['name'],
                'resourceGroup': account['resourceGroup'],
                'endpoint': account['properties']['endpoint']
            }
            break
    
    if not openai_info:
        print("❌ No OpenAI resource found. Please create one first.")
        sys.exit(1)
        
    print(f"✅ OpenAI: {openai_info['name']}")
    print()
    
    # Deploy Bicep template with new names
    print("🏗️  Deploying AllFind infrastructure...")
    
    # Get OpenAI API key
    print("🔑 Getting OpenAI API key...")
    openai_key_result = run_command(f"az cognitiveservices account keys list --name {openai_info['name']} --resource-group {openai_info['resourceGroup']} --query 'key1' -o tsv")
    openai_key = openai_key_result.stdout.strip()
    
    # Create client secret for API app
    print("🔐 Creating client secret for API app...")
    secret_result = run_command(f"az ad app credential reset --id {api_app.stdout.strip()} --query 'password' -o tsv")
    client_secret = secret_result.stdout.strip()
    
    bicep_params = {
        "envName": "prod",
        "location": config["location"],
        "openAiApiKey": openai_key,
        "openAiEndpoint": openai_info["endpoint"],
        "graphClientId": api_app.stdout.strip(),
        "graphClientSecret": client_secret,
        "tenantId": tenant_id,
        "adminEmail": "admin@allfind.ai"
    }
    
    # Create parameter string
    param_string = " ".join([f"{k}={v}" for k, v in bicep_params.items()])
    
    deploy_cmd = f"""
    az deployment group create \\
        --resource-group {config['resourceGroup']} \\
        --template-file allfind.bicep \\
        --parameters {param_string}
    """
    
    print("📋 Deployment command:")
    print(deploy_cmd)
    print()
    
    # Create updated Bicep file with clean names
    print("📝 Creating AllFind Bicep template...")
    
    # Read existing bicep and update names
    with open('docusense.bicep', 'r') as f:
        bicep_content = f.read()
    
    # Replace resource names
    bicep_content = bicep_content.replace('docusense', 'allfind')
    bicep_content = bicep_content.replace('DocuSense', 'AllFind')
    
    with open('allfind.bicep', 'w') as f:
        f.write(bicep_content)
    
    print("✅ Created allfind.bicep with clean resource names")
    print()
    
    # Expected resource URLs after deployment
    print("🌐 After deployment, your resources will be:")
    print(f"   Frontend: https://allfind-ui.azurestaticapps.net")
    print(f"   API:      https://allfind-api.azurewebsites.net") 
    print(f"   Search:   https://allfind-search.search.windows.net")
    print()
    
    print("🎯 Custom domains will be:")
    print(f"   app.allfind.ai → allfind-ui.azurestaticapps.net")
    print(f"   api.allfind.ai → allfind-api.azurewebsites.net")
    print()
    
    # Ask for confirmation
    response = input("🚀 Deploy AllFind infrastructure? (y/N): ")
    if response.lower() != 'y':
        print("❌ Deployment cancelled")
        sys.exit(0)
    
    # Deploy
    result = run_command(deploy_cmd)
    
    if result.returncode == 0:
        print("✅ AllFind infrastructure deployed successfully!")
        print()
        print("🎯 Next steps:")
        print("1. Add DNS records at your domain registrar")
        print("2. Configure custom domains in Azure")
        print("3. Deploy application code")
        print("4. Update branding from DocuSense to AllFind")
    else:
        print("❌ Deployment failed")
        print(result.stderr)

if __name__ == "__main__":
    main() 