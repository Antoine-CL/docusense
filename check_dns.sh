#!/bin/bash
echo "🔍 Checking DNS records for AllFind domains..."
echo ""
echo "📱 Frontend (app.allfind.ai):"
nslookup app.allfind.ai || echo "❌ Not configured yet"
echo ""
echo "🔗 API (api.allfind.ai):"  
nslookup api.allfind.ai || echo "❌ Not configured yet"
echo ""
echo "🌐 WWW (www.allfind.ai):"
nslookup www.allfind.ai || echo "❌ Not configured yet"
echo ""
echo "✅ Expected values:"
echo "   app.allfind.ai → proud-sand-00e715010.1.azurestaticapps.net"
echo "   api.allfind.ai → allfind-api-prod.azurewebsites.net"
echo "   www.allfind.ai → proud-sand-00e715010.1.azurestaticapps.net"
