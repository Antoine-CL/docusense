#!/bin/bash
echo "⏳ Waiting for DNS propagation..."
echo "This will check every 30 seconds until DNS is ready"
echo ""

while true; do
    echo "🔍 Checking DNS records..."
    
    # Check app subdomain
    if nslookup app.allfind.ai > /dev/null 2>&1; then
        echo "✅ app.allfind.ai - Ready!"
        APP_READY=true
    else
        echo "⏳ app.allfind.ai - Still propagating..."
        APP_READY=false
    fi
    
    # Check api subdomain  
    if nslookup api.allfind.ai > /dev/null 2>&1; then
        echo "✅ api.allfind.ai - Ready!"
        API_READY=true
    else
        echo "⏳ api.allfind.ai - Still propagating..."
        API_READY=false
    fi
    
    # Check www subdomain
    if nslookup www.allfind.ai > /dev/null 2>&1; then
        echo "✅ www.allfind.ai - Ready!"
        WWW_READY=true
    else
        echo "⏳ www.allfind.ai - Still propagating..."
        WWW_READY=false
    fi
    
    # Check if all are ready
    if [ "$APP_READY" = true ] && [ "$API_READY" = true ] && [ "$WWW_READY" = true ]; then
        echo ""
        echo "🎉 All DNS records are ready!"
        echo "✅ app.allfind.ai → proud-sand-00e715010.1.azurestaticapps.net"
        echo "✅ api.allfind.ai → allfind-api-prod.azurewebsites.net"
        echo "✅ www.allfind.ai → proud-sand-00e715010.1.azurestaticapps.net"
        echo ""
        echo "🚀 Ready to configure custom domains in Azure!"
        break
    fi
    
    echo "⏳ Waiting 30 seconds..."
    sleep 30
    echo ""
done
