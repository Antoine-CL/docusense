#!/usr/bin/env python3
"""
Automated deployment script for DocuSense webhook system.
Minimizes manual intervention by using Azure CLI for all operations.
"""

import os
import json
import subprocess
import sys
import time
from pathlib import Path

# Load environment variables from .env file
def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

# Load environment variables
load_env_file()

# Configuration
RESOURCE_GROUP = "docusense-rg"
LOCATION = "eastus"
FUNCTION_APP_NAME = "docusense-webhooks"
STORAGE_ACCOUNT_NAME = "docusensewebhookstorage"
APP_SERVICE_PLAN = "docusense-plan"

# Required environment variables
REQUIRED_ENV_VARS = [
    "TENANT_ID",
    "CLIENT_ID", 
    "CLIENT_SECRET",
    "AZURE_SEARCH_SERVICE_NAME",
    "AZURE_SEARCH_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY"
]

def run_command(cmd, check=True, capture_output=True):
    """Run a command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {cmd}")
        print(f"Error output: {result.stderr}")
        sys.exit(1)
    return result

def check_prerequisites():
    """Check that all prerequisites are met."""
    print("🔍 Checking prerequisites...")
    
    # Check Azure CLI
    try:
        run_command("az --version")
        print("✅ Azure CLI is installed")
    except:
        print("❌ Azure CLI not found. Please install it first.")
        sys.exit(1)
    
    # Check if logged in
    result = run_command("az account show", check=False)
    if result.returncode != 0:
        print("❌ Not logged into Azure. Please run 'az login' first.")
        sys.exit(1)
    print("✅ Logged into Azure")
    
    # Check environment variables
    missing_vars = []
    for var in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these in your environment or .env file")
        sys.exit(1)
    print("✅ All environment variables are set")

def create_resource_group():
    """Create the resource group if it doesn't exist."""
    print(f"🏗️  Creating resource group: {RESOURCE_GROUP}")
    run_command(f"az group create --name {RESOURCE_GROUP} --location {LOCATION}")
    print("✅ Resource group created/verified")

def create_storage_account():
    """Create storage account for Azure Functions."""
    print(f"💾 Creating storage account: {STORAGE_ACCOUNT_NAME}")
    
    # Check if storage account exists
    result = run_command(f"az storage account show --name {STORAGE_ACCOUNT_NAME} --resource-group {RESOURCE_GROUP}", check=False)
    if result.returncode == 0:
        print("✅ Storage account already exists")
        return
    
    run_command(f"""az storage account create \\
        --name {STORAGE_ACCOUNT_NAME} \\
        --resource-group {RESOURCE_GROUP} \\
        --location {LOCATION} \\
        --sku Standard_LRS""")
    print("✅ Storage account created")

def create_app_service_plan():
    """Create App Service Plan for Azure Functions."""
    print(f"📋 Creating App Service Plan: {APP_SERVICE_PLAN}")
    
    # Check if plan exists
    result = run_command(f"az appservice plan show --name {APP_SERVICE_PLAN} --resource-group {RESOURCE_GROUP}", check=False)
    if result.returncode == 0:
        print("✅ App Service Plan already exists")
        return
    
    run_command(f"""az appservice plan create \\
        --name {APP_SERVICE_PLAN} \\
        --resource-group {RESOURCE_GROUP} \\
        --location {LOCATION} \\
        --sku Y1 \\
        --is-linux""")
    print("✅ App Service Plan created")

def create_function_app():
    """Create the Azure Function App."""
    print(f"⚡ Creating Function App: {FUNCTION_APP_NAME}")
    
    # Check if function app exists
    result = run_command(f"az functionapp show --name {FUNCTION_APP_NAME} --resource-group {RESOURCE_GROUP}", check=False)
    if result.returncode == 0:
        print("✅ Function App already exists")
        return
    
    run_command(f"""az functionapp create \\
        --name {FUNCTION_APP_NAME} \\
        --resource-group {RESOURCE_GROUP} \\
        --storage-account {STORAGE_ACCOUNT_NAME} \\
        --plan {APP_SERVICE_PLAN} \\
        --runtime python \\
        --runtime-version 3.11 \\
        --functions-version 4 \\
        --os-type Linux""")
    print("✅ Function App created")

def configure_function_app():
    """Configure the Function App with environment variables."""
    print("🔧 Configuring Function App settings...")
    
    # Prepare app settings
    settings = []
    for var in REQUIRED_ENV_VARS:
        settings.extend(["--settings", f"{var}={os.getenv(var)}"])
    
    # Add additional settings
    additional_settings = {
        "FUNCTIONS_WORKER_RUNTIME": "python",
        "ENABLE_ORYX_BUILD": "true",
        "SCM_DO_BUILD_DURING_DEPLOYMENT": "true",
        "WEBSITE_RUN_FROM_PACKAGE": "1",
        "WEBHOOK_CLIENT_STATE": "docusense-webhook-secret"
    }
    
    for key, value in additional_settings.items():
        settings.extend(["--settings", f"{key}={value}"])
    
    cmd = f"az functionapp config appsettings set --name {FUNCTION_APP_NAME} --resource-group {RESOURCE_GROUP} " + " ".join(settings)
    run_command(cmd)
    print("✅ Function App configured")

def create_function_files():
    """Create the Azure Function files."""
    print("📁 Creating Azure Function files...")
    
    # Create function directory
    func_dir = Path("webhook_function")
    func_dir.mkdir(exist_ok=True)
    
    # Create host.json
    host_json = {
        "version": "2.0",
        "functionTimeout": "00:05:00",
        "extensions": {
            "http": {
                "routePrefix": ""
            }
        }
    }
    
    with open(func_dir / "host.json", "w") as f:
        json.dump(host_json, f, indent=2)
    
    # Create requirements.txt
    requirements = """
azure-functions
fastapi
uvicorn
requests
PyJWT
cryptography
azure-search-documents==11.*
msal>=1.25.0
python-multipart
"""
    
    with open(func_dir / "requirements.txt", "w") as f:
        f.write(requirements.strip())
    
    # Create function.json for webhook handler
    webhook_dir = func_dir / "webhook_handler"
    webhook_dir.mkdir(exist_ok=True)
    
    function_json = {
        "scriptFile": "__init__.py",
        "bindings": [
            {
                "authLevel": "function",
                "type": "httpTrigger",
                "direction": "in",
                "name": "req",
                "methods": ["get", "post"]
            },
            {
                "type": "http",
                "direction": "out",
                "name": "$return"
            }
        ]
    }
    
    with open(webhook_dir / "function.json", "w") as f:
        json.dump(function_json, f, indent=2)
    
    # Copy enhanced webhook handler code
    with open("azure_function_webhook_enhanced.py", "r") as src:
        content = src.read()
    
    with open(webhook_dir / "__init__.py", "w") as dst:
        dst.write(content)
    
    # Create function.json for renewal function
    renewal_dir = func_dir / "renewal_function"
    renewal_dir.mkdir(exist_ok=True)
    
    renewal_function_json = {
        "scriptFile": "__init__.py",
        "bindings": [
            {
                "name": "mytimer",
                "type": "timerTrigger",
                "direction": "in",
                "schedule": "0 0 */1 * * *"
            }
        ]
    }
    
    with open(renewal_dir / "function.json", "w") as f:
        json.dump(renewal_function_json, f, indent=2)
    
    # Copy renewal function code
    with open("renewal_function.py", "r") as src:
        content = src.read()
    
    with open(renewal_dir / "__init__.py", "w") as dst:
        dst.write(content)
    
    print("✅ Function files created")

def deploy_functions():
    """Deploy the functions to Azure."""
    print("🚀 Deploying functions...")
    
    # Create deployment package
    os.chdir("webhook_function")
    run_command("zip -r ../function_app.zip .")
    os.chdir("..")
    
    # Deploy to Azure
    run_command(f"""az functionapp deployment source config-zip \\
        --name {FUNCTION_APP_NAME} \\
        --resource-group {RESOURCE_GROUP} \\
        --src function_app.zip""")
    
    print("✅ Functions deployed")
    
    # Wait for deployment to complete
    print("⏳ Waiting for deployment to complete...")
    time.sleep(30)

def get_function_urls():
    """Get the function URLs."""
    print("🔗 Getting function URLs...")
    
    # Get function keys
    keys_result = run_command(f"""az functionapp keys list \\
        --name {FUNCTION_APP_NAME} \\
        --resource-group {RESOURCE_GROUP}""")
    
    keys_data = json.loads(keys_result.stdout)
    function_key = keys_data.get("functionKeys", {}).get("default")
    
    webhook_url = f"https://{FUNCTION_APP_NAME}.azurewebsites.net/api/webhook_handler?code={function_key}"
    
    print(f"✅ Webhook URL: {webhook_url}")
    
    # Save to config file
    config = {
        "webhook_url": webhook_url,
        "function_app_name": FUNCTION_APP_NAME,
        "resource_group": RESOURCE_GROUP
    }
    
    with open("webhook_config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    return webhook_url

def setup_webhooks(webhook_url):
    """Setup webhook subscriptions using our existing script."""
    print("🔔 Setting up webhook subscriptions...")
    
    # Set the webhook URL environment variable
    os.environ["WEBHOOK_URL"] = webhook_url
    
    # Run the setup script
    run_command("python setup_webhooks.py", capture_output=False)
    print("✅ Webhook subscriptions created")

def cleanup_temp_files():
    """Clean up temporary files."""
    print("🧹 Cleaning up temporary files...")
    
    import shutil
    
    # Remove temp directories and files
    if os.path.exists("webhook_function"):
        shutil.rmtree("webhook_function")
    if os.path.exists("function_app.zip"):
        os.remove("function_app.zip")
    
    print("✅ Cleanup complete")

def main():
    """Main deployment function."""
    print("🚀 Starting automated DocuSense webhook deployment...")
    print("=" * 60)
    
    try:
        check_prerequisites()
        create_resource_group()
        create_storage_account()
        create_app_service_plan()
        create_function_app()
        configure_function_app()
        create_function_files()
        deploy_functions()
        webhook_url = get_function_urls()
        setup_webhooks(webhook_url)
        cleanup_temp_files()
        
        print("=" * 60)
        print("🎉 Deployment completed successfully!")
        print(f"📋 Function App: {FUNCTION_APP_NAME}")
        print(f"🔗 Webhook URL: {webhook_url}")
        print("📄 Configuration saved to webhook_config.json")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n❌ Deployment cancelled by user")
        cleanup_temp_files()
        sys.exit(1)
    except Exception as e:
        print(f"❌ Deployment failed: {str(e)}")
        cleanup_temp_files()
        sys.exit(1)

if __name__ == "__main__":
    main()
