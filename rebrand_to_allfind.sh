#!/bin/bash
# AllFind Rebranding Script
set -e

echo "🔄 Starting AllFind Rebranding Process"

# Update key backend files
sed -i '' 's/DocuSense/AllFind/g' docusense-backend/main_live.py
sed -i '' 's/DocuSense/AllFind/g' docusense-backend/main.py
sed -i '' 's/DocuSense/AllFind/g' docusense-backend/main_simple.py

# Update Bicep template
sed -i '' 's/DocuSense/AllFind/g' docusense.bicep

# Update GitHub workflow
sed -i '' 's/Deploy DocuSense/Deploy AllFind/g' .github/workflows/deploy.yml

echo "✅ Key rebranding complete!"
