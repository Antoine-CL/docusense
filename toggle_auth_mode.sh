#!/bin/bash
# Quick toggle between simple and production auth modes

set -e

echo "🔄 DocuSense Auth Mode Toggle"
echo "============================="
echo

# Check current mode
CURRENT_BACKEND_MODE=$(grep "USE_SIMPLE_AUTH=" docusense-backend/.env 2>/dev/null | cut -d'=' -f2 || echo "true")
CURRENT_FRONTEND_MODE=$(grep "REACT_APP_USE_PROD_AUTH=" docusense-frontend/.env.local 2>/dev/null | cut -d'=' -f2 || echo "false")

echo "📋 Current Configuration:"
echo "   Backend: $([ "$CURRENT_BACKEND_MODE" = "true" ] && echo "Simple Auth" || echo "Production Auth")"
echo "   Frontend: $([ "$CURRENT_FRONTEND_MODE" = "true" ] && echo "Production Auth" || echo "Simple Auth")"
echo

# Ask user what they want to do
echo "What would you like to do?"
echo "1. Switch to Simple Auth (Development Mode)"
echo "2. Switch to Production Auth (Azure AD Mode)"
echo "3. Show current status"
echo

read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        echo "🔧 Switching to Simple Auth..."
        
        # Update backend
        sed -i '' 's/USE_SIMPLE_AUTH=.*/USE_SIMPLE_AUTH=true/' docusense-backend/.env
        
        # Update frontend
        sed -i '' 's/REACT_APP_USE_PROD_AUTH=.*/REACT_APP_USE_PROD_AUTH=false/' docusense-frontend/.env.local
        
        echo "✅ Switched to Simple Auth mode"
        echo "   - No Azure AD sign-in required"
        echo "   - Mock authentication for development"
        echo "   - Restart servers to apply changes"
        ;;
    2)
        echo "🔐 Switching to Production Auth..."
        
        # Check if Azure AD is configured
        TENANT_ID=$(grep "REACT_APP_TENANT_ID=" docusense-frontend/.env.local 2>/dev/null | cut -d'=' -f2 || echo "")
        if [[ -z "$TENANT_ID" || "$TENANT_ID" == "your-tenant-id-here" ]]; then
            echo "❌ Azure AD not configured!"
            echo "   Run ./setup_azure_ad_local.sh first to configure Azure AD"
            exit 1
        fi
        
        # Update backend
        sed -i '' 's/USE_SIMPLE_AUTH=.*/USE_SIMPLE_AUTH=false/' docusense-backend/.env
        
        # Update frontend
        sed -i '' 's/REACT_APP_USE_PROD_AUTH=.*/REACT_APP_USE_PROD_AUTH=true/' docusense-frontend/.env.local
        
        echo "✅ Switched to Production Auth mode"
        echo "   - Azure AD sign-in required"
        echo "   - Real JWT token validation"
        echo "   - Restart servers to apply changes"
        ;;
    3)
        echo "📊 Current Status:"
        echo "   Backend Simple Auth: $CURRENT_BACKEND_MODE"
        echo "   Frontend Prod Auth: $CURRENT_FRONTEND_MODE"
        
        if [[ -f "docusense-frontend/.env.local" ]]; then
            echo
            echo "📝 Frontend Configuration:"
            grep "REACT_APP_" docusense-frontend/.env.local | sed 's/^/   /'
        fi
        
        if [[ -f "docusense-backend/.env" ]]; then
            echo
            echo "📝 Backend Configuration:"
            grep -E "(USE_SIMPLE_AUTH|AAD_)" docusense-backend/.env | sed 's/^/   /'
        fi
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo
echo "🔄 Next Steps:"
echo "   1. Restart backend: cd docusense-backend && python -m uvicorn main_live:app --reload --port 8001"
echo "   2. Restart frontend: cd docusense-frontend && npm start"
echo "   3. Check /health endpoint to confirm auth mode" 