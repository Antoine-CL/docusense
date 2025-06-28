#!/usr/bin/env python3
"""
DocuSense Infrastructure Deployment
Uses Bicep template for Infrastructure-as-Code deployment
"""

import os
import sys
import json
import subprocess
from pathlib import Path

def run_command(cmd, check=True):
    """Run a command and return the result."""
    print(f"🔧 Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if check and result.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        print(f"Error: {result.stderr}")
        sys.exit(1)
    
    return result

def get_required_parameters():
    """Get required parameters for deployment."""
    
    print("📋 DocuSense Infrastructure Deployment")
    print("=" * 50)
    
    # Environment
    env_name = input("Environment (dev/stage/prod) [dev]: ").strip() or "dev"
    
    # Resource Group
    resource_group = input(f"Resource Group [docusense-{env_name}-rg]: ").strip() or f"docusense-{env_name}-rg"
    
    # Location
    location = input("Azure Region [eastus]: ").strip() or "eastus"
    
    # Search SKU
    print("\nAzure AI Search SKUs:")
    print("  basic    - $250/month, 2GB storage, 15M docs")
    print("  standard - $1000/month, 25GB storage, 50M docs")
    print("  standard3- $6000/month, 1TB storage, 200M docs")
    search_sku = input("Search SKU [standard]: ").strip() or "standard"
    
    # Function SKU
    print("\nFunction App SKUs:")
    print("  Y1  - Consumption (pay-per-use)")
    print("  EP1 - Premium ($200/month, better performance)")
    func_sku = input("Function SKU [Y1]: ").strip() or "Y1"
    
    # Get secrets
    print("\n🔐 Required Secrets:")
    
    openai_endpoint = input("Azure OpenAI Endpoint: ").strip()
    if not openai_endpoint:
        print("❌ Azure OpenAI Endpoint is required")
        sys.exit(1)
    
    openai_key = input("Azure OpenAI API Key: ").strip()
    if not openai_key:
        print("❌ Azure OpenAI API Key is required")
        sys.exit(1)
    
    graph_client_id = input("Microsoft Graph Client ID: ").strip()
    if not graph_client_id:
        print("❌ Microsoft Graph Client ID is required")
        sys.exit(1)
    
    graph_client_secret = input("Microsoft Graph Client Secret: ").strip()
    if not graph_client_secret:
        print("❌ Microsoft Graph Client Secret is required")
        sys.exit(1)
    
    tenant_id = input("Azure AD Tenant ID: ").strip()
    if not tenant_id:
        print("❌ Azure AD Tenant ID is required")
        sys.exit(1)
    
    return {
        "envName": env_name,
        "resourceGroup": resource_group,
        "location": location,
        "searchSku": search_sku,
        "funcSku": func_sku,
        "openAiEndpoint": openai_endpoint,
        "openAiApiKey": openai_key,
        "graphClientId": graph_client_id,
        "graphClientSecret": graph_client_secret,
        "tenantId": tenant_id
    }

def create_resource_group(resource_group, location):
    """Create resource group if it doesn't exist."""
    print(f"📦 Creating resource group: {resource_group}")
    
    # Check if exists
    result = run_command(f"az group show --name {resource_group}", check=False)
    if result.returncode == 0:
        print("✅ Resource group already exists")
        return
    
    # Create resource group
    run_command(f"az group create --name {resource_group} --location {location}")
    print("✅ Resource group created")

def deploy_infrastructure(params):
    """Deploy infrastructure using Bicep template."""
    print("🚀 Deploying infrastructure...")
    
    bicep_file = "docusense.bicep"
    if not Path(bicep_file).exists():
        print(f"❌ Bicep template not found: {bicep_file}")
        sys.exit(1)
    
    # Build deployment command
    cmd = f"""az deployment group create \\
        --resource-group {params['resourceGroup']} \\
        --template-file {bicep_file} \\
        --parameters envName={params['envName']} \\
                    location={params['location']} \\
                    searchSku={params['searchSku']} \\
                    funcSku={params['funcSku']} \\
                    openAiEndpoint={params['openAiEndpoint']} \\
                    openAiApiKey={params['openAiApiKey']} \\
                    graphClientId={params['graphClientId']} \\
                    graphClientSecret={params['graphClientSecret']} \\
                    tenantId={params['tenantId']}"""
    
    result = run_command(cmd)
    
    # Parse outputs
    if result.stdout:
        try:
            deployment_result = json.loads(result.stdout)
            outputs = deployment_result.get("properties", {}).get("outputs", {})
            
            # Save outputs to file
            output_file = f"deployment-outputs-{params['envName']}.json"
            with open(output_file, 'w') as f:
                json.dump(outputs, f, indent=2)
            
            print("✅ Infrastructure deployed successfully!")
            print(f"📄 Outputs saved to: {output_file}")
            
            return outputs
            
        except json.JSONDecodeError:
            print("⚠️  Could not parse deployment outputs")
            return {}
    
    return {}

def display_deployment_summary(outputs):
    """Display deployment summary."""
    print("\n" + "=" * 60)
    print("🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    
    if outputs:
        print("\n📋 Deployment Outputs:")
        for key, value in outputs.items():
            if isinstance(value, dict) and "value" in value:
                print(f"  {key}: {value['value']}")
    
    print("\n🔗 Next Steps:")
    print("1. Deploy Function App code:")
    print("   cd docusense-backend")
    print("   func azure functionapp publish <function-app-name>")
    
    print("\n2. Deploy API backend:")
    print("   cd docusense-backend")
    print("   az webapp up --name <api-app-name> --resource-group <rg>")
    
    print("\n3. Deploy React frontend:")
    print("   cd docusense-frontend")
    print("   npm run build")
    print("   az staticwebapp deploy --name <static-app-name> --source-location ./build")
    
    print("\n4. Set up webhooks:")
    print("   python setup_webhooks.py")
    
    print("\n5. Create search index:")
    print("   python create_index.py")

def main():
    """Main deployment function."""
    try:
        # Check Azure CLI
        result = run_command("az --version", check=False)
        if result.returncode != 0:
            print("❌ Azure CLI not found. Please install: https://aka.ms/installazurecli")
            sys.exit(1)
        
        # Check login
        result = run_command("az account show", check=False)
        if result.returncode != 0:
            print("❌ Not logged into Azure. Please run: az login")
            sys.exit(1)
        
        # Get parameters
        params = get_required_parameters()
        
        # Create resource group
        create_resource_group(params["resourceGroup"], params["location"])
        
        # Deploy infrastructure
        outputs = deploy_infrastructure(params)
        
        # Show summary
        display_deployment_summary(outputs)
        
    except KeyboardInterrupt:
        print("\n❌ Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Deployment failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 