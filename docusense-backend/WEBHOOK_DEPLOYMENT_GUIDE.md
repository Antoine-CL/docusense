# DocuSense Webhook Deployment Guide

This guide walks through deploying real-time document ingestion using Microsoft Graph webhooks and Azure Functions.

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   SharePoint    │───▶│  Graph Webhook   │───▶│  Azure Function │
│   File Upload   │    │  Notification    │    │  HTTP Trigger   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Delta Query    │
                                               │  File Processing│
                                               │  Search Indexing│
                                               └─────────────────┘
```

## Prerequisites

- Azure subscription with Function Apps enabled
- Microsoft Graph API permissions configured
- Azure AI Search service running
- DocuSense backend code deployed

## Step 1: Deploy Azure Functions

### Create Function App

```bash
# Create resource group
az group create --name docusense-rg --location "East US"

# Create storage account for functions
az storage account create \
  --name docusensefunctions \
  --resource-group docusense-rg \
  --location "East US" \
  --sku Standard_LRS

# Create Function App
az functionapp create \
  --resource-group docusense-rg \
  --consumption-plan-location "East US" \
  --runtime python \
  --runtime-version 3.9 \
  --functions-version 4 \
  --name docusense-webhooks \
  --storage-account docusensefunctions
```

### Configure Function App Settings

```bash
# Set environment variables
az functionapp config appsettings set \
  --resource-group docusense-rg \
  --name docusense-webhooks \
  --settings \
    "AAD_CLIENT_ID=your-client-id" \
    "AAD_TENANT_ID=your-tenant-id" \
    "AAD_CLIENT_SECRET=your-client-secret" \
    "AZURE_SEARCH_ENDPOINT=your-search-endpoint" \
    "AZURE_SEARCH_API_KEY=your-search-key" \
    "AZURE_SEARCH_INDEX_NAME=docusense-index" \
    "AZURE_OPENAI_ENDPOINT=your-openai-endpoint" \
    "AZURE_OPENAI_API_KEY=your-openai-key" \
    "WEBHOOK_CLIENT_STATE=your-secret-validation-token"
```

## Step 2: Deploy Functions

### Function Structure

```
docusense-functions/
├── webhook-handler/
│   ├── function.json
│   └── __init__.py (contains azure_function_webhook.py code)
├── subscription-renewal/
│   ├── function.json
│   └── __init__.py (contains renewal_function.py code)
├── requirements.txt
└── host.json
```

### webhook-handler/function.json

```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "authLevel": "anonymous",
      "type": "httpTrigger",
      "direction": "in",
      "name": "req",
      "methods": ["post"]
    },
    {
      "type": "http",
      "direction": "out",
      "name": "$return"
    }
  ]
}
```

### subscription-renewal/function.json

```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "name": "mytimer",
      "type": "timerTrigger",
      "direction": "in",
      "schedule": "0 0 2 * * *"
    }
  ]
}
```

### requirements.txt

```
azure-functions
azure-search-documents
azure-identity
requests
python-dotenv
openai
PyPDF2
python-docx
python-pptx
msal
```

### Deploy Functions

```bash
# Package and deploy
func azure functionapp publish docusense-webhooks --python
```

## Step 3: Setup Webhook Subscriptions

### Get Function URL

```bash
# Get the webhook function URL
az functionapp function show \
  --resource-group docusense-rg \
  --name docusense-webhooks \
  --function-name webhook-handler \
  --query "invokeUrlTemplate" -o tsv
```

### Create Subscriptions

```bash
# Set the webhook URL
export WEBHOOK_URL="https://docusense-webhooks.azurewebsites.net/api/webhook-handler"

# Run setup script
python setup_webhooks.py setup
```

## Step 4: Multi-tenant Considerations

### Tenant Isolation

For multi-tenant SaaS, you need to:

1. **Store tenant-specific subscriptions**

```python
# Example tenant subscription mapping
tenant_subscriptions = {
    "tenant1-id": ["subscription1-id", "subscription2-id"],
    "tenant2-id": ["subscription3-id", "subscription4-id"]
}
```

2. **Provision subscriptions per tenant**

```python
def provision_tenant_webhooks(tenant_id: str, drives: List[str]):
    """Create webhook subscriptions for a new tenant"""
    subscriptions = []

    for drive_id in drives:
        subscription = create_subscription(
            drive_id=drive_id,
            notification_url=f"{WEBHOOK_URL}?tenant={tenant_id}"
        )
        subscriptions.append(subscription["id"])

    # Store mapping
    store_tenant_subscriptions(tenant_id, subscriptions)
```

3. **Process notifications with tenant context**

```python
def process_notification_with_tenant(notification: Dict, tenant_id: str):
    """Process notification with tenant isolation"""

    # Use tenant-specific search index
    search_client = get_tenant_search_client(tenant_id)

    # Process with tenant context
    # ... rest of processing logic
```

## Step 5: Monitoring and Alerting

### Application Insights

```bash
# Enable Application Insights
az monitor app-insights component create \
  --app docusense-webhooks \
  --location "East US" \
  --resource-group docusense-rg

# Link to Function App
az functionapp config appsettings set \
  --resource-group docusense-rg \
  --name docusense-webhooks \
  --settings "APPINSIGHTS_INSTRUMENTATIONKEY=your-insights-key"
```

### Health Monitoring

```python
# Add health check endpoint
@app.route('/health')
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "subscriptions": count_active_subscriptions(),
        "last_notification": get_last_notification_time()
    }
```

### Alerts

```bash
# Create alert for failed webhooks
az monitor metrics alert create \
  --name "Webhook Failures" \
  --resource-group docusense-rg \
  --scopes "/subscriptions/your-sub/resourceGroups/docusense-rg/providers/Microsoft.Web/sites/docusense-webhooks" \
  --condition "count 'requests/failed' > 5" \
  --description "Alert when webhook failures exceed 5 in 5 minutes"
```

## Step 6: Testing

### Local Testing

```bash
# Test webhook handler locally
func start --python

# Simulate webhook notification
curl -X POST http://localhost:7071/api/webhook-handler \
  -H "Content-Type: application/json" \
  -d '{
    "value": [{
      "clientState": "your-secret-validation-token",
      "resource": "/drives/your-drive-id/items/your-item-id",
      "changeType": "created"
    }]
  }'
```

### Production Testing

```bash
# Test validation token
curl "https://docusense-webhooks.azurewebsites.net/api/webhook-handler?validationToken=test123"

# Should return: {"validationToken": "test123"}
```

## Step 7: Fallback Polling (Hybrid Approach)

### Create Polling Function

```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "name": "mytimer",
      "type": "timerTrigger",
      "direction": "in",
      "schedule": "0 */30 * * * *"
    }
  ]
}
```

```python
def main(mytimer: func.TimerRequest) -> None:
    """Fallback polling every 30 minutes"""

    logging.info('Starting fallback document polling')

    # Run existing ingestion script as backup
    import subprocess
    result = subprocess.run(['python', 'ingest_onedrive.py'],
                          capture_output=True, text=True)

    if result.returncode == 0:
        logging.info('Fallback polling completed successfully')
    else:
        logging.error(f'Fallback polling failed: {result.stderr}')
```

## Security Checklist

- [ ] **Webhook validation**: Verify `clientState` on all notifications
- [ ] **HTTPS only**: Ensure webhook endpoint uses HTTPS
- [ ] **Authentication**: Validate Graph API tokens
- [ ] **Rate limiting**: Implement request throttling
- [ ] **Error handling**: Graceful failure and retry logic
- [ ] **Logging**: Comprehensive audit trail
- [ ] **Secrets management**: Use Azure Key Vault for sensitive data

## Performance Optimization

### Batch Processing

```python
# Process multiple files in batches
async def process_batch(files: List[Dict], batch_size: int = 5):
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        await asyncio.gather(*[ingest_single_file(f) for f in batch])
```

### Caching

```python
# Use Redis for processed file cache
import redis

redis_client = redis.Redis(host='your-redis-host')

def is_already_processed(drive_id: str, item_id: str, last_modified: str) -> bool:
    cache_key = f"{drive_id}_{item_id}"
    cached_timestamp = redis_client.get(cache_key)
    return cached_timestamp and cached_timestamp.decode() == last_modified
```

## Cost Optimization

| Component                  | Estimated Monthly Cost | Notes                     |
| -------------------------- | ---------------------- | ------------------------- |
| Function App (Consumption) | $5-20                  | Based on executions       |
| Application Insights       | $5-15                  | Based on telemetry volume |
| Storage Account            | $1-5                   | Function storage          |
| **Total**                  | **$11-40**             | For typical usage         |

## Troubleshooting

### Common Issues

1. **Webhook validation fails**

   - Check `clientState` matches exactly
   - Verify HTTPS endpoint is accessible
   - Ensure response format is correct

2. **Subscriptions expire**

   - Check renewal function is running
   - Verify Graph API permissions
   - Monitor expiration dates

3. **Files not processing**
   - Check delta query responses
   - Verify file download permissions
   - Monitor function logs

### Debug Commands

```bash
# Check function logs
az functionapp log tail --resource-group docusense-rg --name docusense-webhooks

# List active subscriptions
python setup_webhooks.py list

# Test Graph API access
python -c "from graph_client import graph_client; print(graph_client.list_drives())"
```

## Next Steps

1. Deploy the webhook functions to Azure
2. Create webhook subscriptions for your drives
3. Test with file uploads to SharePoint
4. Monitor function execution and performance
5. Scale based on usage patterns

The webhook-based approach transforms DocuSense from batch processing to real-time document indexing, providing users with immediate access to newly uploaded documents!
