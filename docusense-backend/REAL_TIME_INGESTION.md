# Real-time Document Ingestion for DocuSense

This document explains how to implement automatic document ingestion when new files are uploaded to SharePoint/OneDrive.

## Overview

DocuSense supports multiple approaches for real-time document ingestion:

1. **Microsoft Graph Webhooks** (Recommended for production)
2. **Scheduled Polling** (Current approach)
3. **Azure Functions with Event Grid** (Enterprise option)
4. **Hybrid Approach** (Best of both worlds)

## 1. Microsoft Graph Webhooks (Real-time)

### How it Works

- Subscribe to Microsoft Graph notifications for file changes
- Receive HTTP POST requests when files are created/updated/deleted
- Process changes immediately (seconds after upload)

### Advantages

- ✅ **Real-time**: Instant processing of new documents
- ✅ **Efficient**: Only processes changed files
- ✅ **Comprehensive**: Handles create, update, delete events
- ✅ **Scalable**: Works across all SharePoint sites and OneDrive

### Requirements

- Public webhook endpoint (HTTPS required)
- Webhook subscriptions need renewal every 2-3 days
- Proper webhook validation and security

### Implementation

#### Step 1: Deploy Webhook Handler

```bash
# Run the webhook handler service
python webhook_handler.py
```

#### Step 2: Setup Webhook Subscriptions

```bash
# Set your public webhook URL
export WEBHOOK_URL="https://your-allfind-api.azurewebsites.net/api/webhooks/graph"

# Create subscriptions for all drives
python setup_webhooks.py setup

# List active subscriptions
python setup_webhooks.py list

# Clean up subscriptions
python setup_webhooks.py cleanup
```

#### Step 3: Environment Variables

```bash
# Add to .env file
WEBHOOK_URL=https://your-allfind-api.azurewebsites.net/api/webhooks/graph
WEBHOOK_CLIENT_STATE=your-secret-validation-token
```

### Production Deployment

#### Azure Container Apps (Recommended)

```yaml
# container-app.yaml
properties:
  configuration:
    ingress:
      external: true
      targetPort: 8002
  template:
    containers:
      - name: webhook-handler
        image: your-registry/docusense-webhook:latest
        env:
          - name: WEBHOOK_URL
            value: "https://your-webhook-app.azurecontainerapps.io/api/webhooks/graph"
```

#### Azure App Service

```bash
# Deploy webhook handler
az webapp create --resource-group docusense-rg --plan docusense-plan --name docusense-webhooks
az webapp config appsettings set --resource-group docusense-rg --name docusense-webhooks --settings WEBHOOK_URL="https://docusense-webhooks.azurewebsites.net/api/webhooks/graph"
```

## 2. Scheduled Polling (Current)

### How it Works

- Run ingestion script on a schedule (e.g., every 15 minutes)
- Check for files modified since last run
- Process all changed files

### Advantages

- ✅ **Simple**: No webhook complexity
- ✅ **Reliable**: No webhook expiration issues
- ✅ **Easy to deploy**: Just schedule the existing script

### Disadvantages

- ❌ **Delayed**: 15-minute delay before indexing
- ❌ **Inefficient**: May process same files multiple times
- ❌ **Resource usage**: Runs even when no changes

### Implementation

#### Azure Functions (Timer Trigger)

```python
import azure.functions as func
from datetime import datetime, timedelta
import subprocess

def main(mytimer: func.TimerRequest) -> None:
    """Run every 15 minutes"""
    logging.info('Starting scheduled document ingestion')

    # Run the ingestion script
    result = subprocess.run(['python', 'ingest_onedrive.py'],
                          capture_output=True, text=True)

    if result.returncode == 0:
        logging.info('Ingestion completed successfully')
    else:
        logging.error(f'Ingestion failed: {result.stderr}')
```

#### Cron Job (Linux/Mac)

```bash
# Add to crontab (every 15 minutes)
*/15 * * * * cd /path/to/docusense-backend && python ingest_onedrive.py >> /var/log/docusense-ingestion.log 2>&1
```

#### Windows Task Scheduler

```batch
# Create scheduled task
schtasks /create /tn "DocuSense Ingestion" /tr "python C:\path\to\docusense-backend\ingest_onedrive.py" /sc minute /mo 15
```

## 3. Azure Functions with Event Grid (Enterprise)

### How it Works

- Use Azure Event Grid to capture SharePoint events
- Trigger Azure Functions for processing
- Leverage Azure's native event system

### Advantages

- ✅ **Enterprise-grade**: Built on Azure's event infrastructure
- ✅ **Scalable**: Automatic scaling based on load
- ✅ **Integrated**: Native Azure service integration

### Disadvantages

- ❌ **Complex**: Requires Azure Event Grid setup
- ❌ **Cost**: Additional Azure services
- ❌ **SharePoint-specific**: Limited to SharePoint (not personal OneDrive)

## 4. Hybrid Approach (Recommended)

Combine webhooks with scheduled polling for maximum reliability:

### Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   SharePoint    │───▶│  Graph Webhooks  │───▶│  Immediate      │
│   File Upload   │    │  (Real-time)     │    │  Processing     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Fallback       │
                       │   Scheduled      │
                       │   Polling        │
                       │   (Every hour)   │
                       └──────────────────┘
```

### Implementation

1. **Primary**: Use webhooks for real-time processing
2. **Backup**: Run scheduled polling every hour to catch missed events
3. **Deduplication**: Use file modification timestamps to avoid reprocessing

```python
# Enhanced ingestion with deduplication
def ingest_with_deduplication(drive_id: str, item_id: str):
    # Check if file was already processed recently
    last_processed = get_last_processed_time(drive_id, item_id)
    file_info = graph_client.get_file_info(drive_id, item_id)

    if file_info and file_info.get('lastModifiedDateTime') > last_processed:
        # Process the file
        ingest_single_file(drive_id, item_id)
        update_last_processed_time(drive_id, item_id)
    else:
        print(f"Skipping {item_id} - already processed")
```

## Security Considerations

### Webhook Security

```python
# Validate webhook authenticity
def validate_webhook_signature(request_body: str, signature: str) -> bool:
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        request_body.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)
```

### Required Permissions

```json
{
  "requiredResourceAccess": [
    {
      "resourceAppId": "00000003-0000-0000-c000-000000000000",
      "resourceAccess": [
        {
          "id": "df021288-bdef-4463-88db-98f22de89214",
          "type": "Role"
        }
      ]
    }
  ]
}
```

## Monitoring and Troubleshooting

### Webhook Health Check

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "active_subscriptions": len(webhook_manager.subscriptions),
        "last_notification": get_last_notification_time()
    }
```

### Common Issues

1. **Webhook Expiration**

   - Subscriptions expire every 2-3 days
   - Implement automatic renewal
   - Monitor expiration dates

2. **Webhook Validation Failures**

   - Ensure HTTPS endpoint
   - Validate client state
   - Check webhook URL accessibility

3. **Permission Issues**
   - Verify app permissions
   - Check admin consent
   - Test with Graph Explorer

## Deployment Checklist

### Pre-deployment

- [ ] Set up public webhook endpoint
- [ ] Configure environment variables
- [ ] Test webhook validation
- [ ] Verify app permissions

### Deployment

- [ ] Deploy webhook handler service
- [ ] Create webhook subscriptions
- [ ] Set up monitoring
- [ ] Configure log aggregation

### Post-deployment

- [ ] Test file upload scenarios
- [ ] Monitor webhook notifications
- [ ] Verify search index updates
- [ ] Set up subscription renewal

## Cost Considerations

| Approach   | Azure Costs                | Complexity | Latency |
| ---------- | -------------------------- | ---------- | ------- |
| Webhooks   | Container Apps + Storage   | Medium     | Seconds |
| Scheduled  | Function Apps              | Low        | Minutes |
| Event Grid | Event Grid + Functions     | High       | Seconds |
| Hybrid     | Container Apps + Functions | High       | Seconds |

## Conclusion

For DocuSense production deployment, we recommend:

1. **Start with webhooks** for real-time processing
2. **Add scheduled polling** as backup (every hour)
3. **Monitor webhook health** and renewal
4. **Scale based on usage** patterns

This approach provides the best balance of real-time performance, reliability, and operational simplicity.
