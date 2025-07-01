#!/usr/bin/env python3
"""
Clean AllFind Deployment Script
Deploys AllFind to a clean AllFind resource group with proper naming
"""

import subprocess
import json
import sys

def run_command(cmd, description):
    """Run a command and return the result"""
    print(f"🔄 {description}")
    print(f"   Command: {cmd}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Error: {result.stderr}")
            return None
        print(f"✅ Success")
        return result.stdout
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def main():
    print("🚀 Starting Clean AllFind Deployment")
    print("=" * 50)
    
    # 1. Ensure AllFind resource group exists
    print("\n1. Creating AllFind Resource Group")
    run_command(
        "az group create --name AllFind --location canadaeast",
        "Creating AllFind resource group in Canada East"
    )
    
    # 2. Deploy Bicep template
    print("\n2. Deploying AllFind Infrastructure")
    result = run_command(
        "az deployment group create --resource-group AllFind --template-file allfind.bicep --parameters envName=prod",
        "Deploying AllFind Bicep template"
    )
    
    if result:
        # Parse deployment outputs
        try:
            deployment_data = json.loads(result)
            outputs = deployment_data.get('properties', {}).get('outputs', {})
            
            static_url = outputs.get('staticWebAppUrl', {}).get('value', '')
            api_url = outputs.get('apiUrl', {}).get('value', '')
            function_url = outputs.get('functionAppUrl', {}).get('value', '')
            
            print(f"\n🎉 AllFind Deployment Complete!")
            print(f"📱 Frontend: {static_url}")
            print(f"🔗 API: {api_url}")
            print(f"⚡ Functions: {function_url}")
            
            # 3. Update DNS records
            print(f"\n3. DNS Configuration Required:")
            print(f"   Add these CNAME records in Namecheap:")
            print(f"   app.allfind.ai → {static_url.replace('https://', '')}")
            print(f"   api.allfind.ai → {api_url.replace('https://', '')}")
            
        except Exception as e:
            print(f"⚠️ Could not parse deployment outputs: {e}")
    
    # 4. List all resources
    print("\n4. AllFind Resources Created:")
    run_command(
        "az resource list --resource-group AllFind --output table",
        "Listing AllFind resources"
    )

if __name__ == "__main__":
    main() 