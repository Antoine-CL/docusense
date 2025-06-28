#!/usr/bin/env python3
"""
DocuSense Deployment Verification Script
Validates the CI/CD setup and deployment structure
"""
import os
import json
import sys
from pathlib import Path

def check_file(path, description):
    """Check if a file exists and is not empty"""
    if not os.path.exists(path):
        print(f"❌ {description}: {path} (missing)")
        return False
    
    if os.path.getsize(path) == 0:
        print(f"⚠️  {description}: {path} (empty)")
        return False
    
    print(f"✅ {description}: {path}")
    return True

def check_directory(path, description):
    """Check if a directory exists"""
    if not os.path.isdir(path):
        print(f"❌ {description}: {path} (missing)")
        return False
    
    print(f"✅ {description}: {path}")
    return True

def check_json_file(path, description, required_keys=None):
    """Check if a JSON file exists and has required keys"""
    if not check_file(path, description):
        return False
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        
        if required_keys:
            missing_keys = [key for key in required_keys if key not in data]
            if missing_keys:
                print(f"⚠️  {description}: Missing keys {missing_keys}")
                return False
        
        return True
    except json.JSONDecodeError:
        print(f"❌ {description}: Invalid JSON")
        return False

def main():
    print("🔍 DocuSense Deployment Verification")
    print("====================================")
    print()
    
    # Check project structure
    print("📁 Project Structure:")
    all_good = True
    
    # Core directories
    all_good &= check_directory("docusense-frontend", "Frontend directory")
    all_good &= check_directory("docusense-backend", "Backend directory")
    all_good &= check_directory("docusense-functions", "Functions directory")
    all_good &= check_directory(".github/workflows", "GitHub workflows")
    all_good &= check_directory("tests", "Tests directory")
    
    print()
    
    # Frontend files
    print("🌐 Frontend Files:")
    all_good &= check_file("docusense-frontend/package.json", "Frontend package.json")
    all_good &= check_file("docusense-frontend/src/App.tsx", "React App component")
    all_good &= check_file("docusense-frontend/src/pages/AdminPage.tsx", "Admin page component")
    
    print()
    
    # Backend files
    print("🐍 Backend Files:")
    all_good &= check_file("docusense-backend/main_live.py", "Live backend server")
    all_good &= check_file("docusense-backend/tenant_settings.py", "Tenant settings module")
    all_good &= check_file("docusense-backend/webhook_manager.py", "Webhook manager module")
    all_good &= check_file("docusense-backend/usage_analytics.py", "Usage analytics module")
    all_good &= check_file("docusense-backend/audit_logger.py", "Audit logger module")
    
    print()
    
    # Azure Functions structure
    print("⚡ Azure Functions:")
    all_good &= check_json_file("docusense-functions/host.json", "Functions host config", 
                               ["version", "functionTimeout"])
    all_good &= check_file("docusense-functions/requirements.txt", "Functions requirements")
    
    # Webhook function
    all_good &= check_directory("docusense-functions/webhook", "Webhook function directory")
    all_good &= check_json_file("docusense-functions/webhook/function.json", "Webhook function config",
                               ["bindings"])
    all_good &= check_file("docusense-functions/webhook/__init__.py", "Webhook function code")
    
    # Renewal function
    all_good &= check_directory("docusense-functions/renewal", "Renewal function directory")
    all_good &= check_json_file("docusense-functions/renewal/function.json", "Renewal function config",
                               ["bindings"])
    all_good &= check_file("docusense-functions/renewal/__init__.py", "Renewal function code")
    
    # Shared modules
    all_good &= check_file("docusense-functions/graph_client.py", "Graph client module")
    all_good &= check_file("docusense-functions/azure_search_client.py", "Search client module")
    
    print()
    
    # CI/CD files
    print("🚀 CI/CD Configuration:")
    all_good &= check_file(".github/workflows/deploy-chatgpt.yml", "Streamlined CI/CD workflow")
    all_good &= check_file("docusense.bicep", "Infrastructure template")
    all_good &= check_file("setup_github_secrets.sh", "Secrets setup script")
    
    print()
    
    # Test files
    print("🧪 Testing:")
    all_good &= check_file("tests/test_admin_endpoints.py", "Admin endpoints tests")
    
    print()
    
    # Documentation
    print("📚 Documentation:")
    all_good &= check_file("CI_CD_IMPLEMENTATION.md", "CI/CD documentation")
    
    print()
    
    # Validate workflow file
    print("🔧 Workflow Validation:")
    workflow_path = ".github/workflows/deploy-chatgpt.yml"
    if os.path.exists(workflow_path):
        with open(workflow_path, 'r') as f:
            content = f.read()
        
        required_sections = [
            "Deploy-DocuSense",
            "azure/login@v1",
            "azure-functions-core-tools",
            "func azure functionapp publish",
            "pytest"
        ]
        
        for section in required_sections:
            if section in content:
                print(f"✅ Workflow contains: {section}")
            else:
                print(f"❌ Workflow missing: {section}")
                all_good = False
    
    print()
    
    # Final summary
    if all_good:
        print("🎉 All checks passed!")
        print("✅ Your DocuSense deployment is ready for CI/CD")
        print()
        print("📋 Next steps:")
        print("1. Run: ./setup_github_secrets.sh")
        print("2. Push to main branch to trigger deployment")
        print("3. Monitor deployment in GitHub Actions")
        return 0
    else:
        print("❌ Some checks failed!")
        print("Please fix the issues above before deploying")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 