#!/bin/bash

echo "🚀 Clean AllFind Deployment"
echo "=========================="

echo "1. Deploying to AllFind resource group..."
az deployment group create \
  --resource-group AllFind \
  --template-file allfind.bicep \
  --parameters envName=prod \
  --verbose

echo "2. Listing deployed resources..."
az resource list --resource-group AllFind --output table

echo "3. Getting deployment outputs..."
az deployment group show \
  --resource-group AllFind \
  --name allfind \
  --query properties.outputs 