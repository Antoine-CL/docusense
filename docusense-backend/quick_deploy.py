#!/usr/bin/env python3
"""
One-command deployment script for DocuSense webhooks.
Handles all prerequisites and deployment automatically.
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, check=True):
    """Run a command and return the result."""
    print(f"🔧 {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        sys.exit(1)
    return result

def check_azure_login():
    """Check if user is logged into Azure."""
    result = run_command("az account show", check=False)
    if result.returncode != 0:
        print("🔐 Please log into Azure...")
        run_command("az login")
        print("✅ Azure login successful")
    else:
        print("✅ Already logged into Azure")

def check_env_file():
    """Check if .env file exists and has required variables."""
    env_file = Path(".env")
    if not env_file.exists():
        print("📝 No .env file found. Let's set up your environment...")
        run_command("python3 setup_env.py")
    else:
        print("✅ Found .env file")

def main():
    """Main deployment function."""
    print("🚀 DocuSense Quick Deploy")
    print("=" * 40)
    print("This will deploy your webhook system with minimal manual steps!")
    print()
    
    # Check prerequisites
    print("1️⃣ Checking prerequisites...")
    check_env_file()
    check_azure_login()
    
    # Deploy
    print("\n2️⃣ Starting deployment...")
    run_command("python3 deploy_webhooks.py")
    
    print("\n🎉 Deployment complete!")
    print("Check webhook_config.json for your webhook URL")

if __name__ == "__main__":
    main()
