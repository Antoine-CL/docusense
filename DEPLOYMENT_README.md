# DocuSense Production Deployment Guide

## 🚀 Quick Start

DocuSense now uses **Infrastructure-as-Code** with Azure Bicep for production-ready deployments. This addresses all ChatGPT recommendations for enterprise deployment.

### 1. Prerequisites

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login

# Install Azure Functions Core Tools (for manual deployment)
npm install -g azure-functions-core-tools@4 --unsafe-perm true
```

### 2. One-Command Deployment

```bash
# Clone and deploy
git clone <your-repo>
cd docusense
python deploy.py
```

The script will prompt for:

- Environment (dev/stage/prod)
- Azure region
- Search SKU (basic/standard/standard3)
- Required secrets (OpenAI, Graph API)

## 🏗️ Architecture Overview

### Infrastructure Components

| Component           | Purpose            | Size Limits     | Cost             |
| ------------------- | ------------------ | --------------- | ---------------- |
| **Azure Functions** | Webhook processing | Files ≤200MB    | ~$50/month       |
| **Service Bus**     | Large file queue   | Files 200MB-1GB | ~$10/month       |
| **Azure AI Search** | Vector storage     | 15M-200M docs   | $250-$6000/month |
| **App Service**     | FastAPI backend    | API requests    | ~$100/month      |
| **Static Web App**  | React frontend     | Static hosting  | Free-$10/month   |
| **Key Vault**       | Secret management  | Secure storage  | ~$3/month        |

### File Processing Tiers (ChatGPT Recommendations)

| File Size | Method        | Location                       | Processing Time | Notes                   |
| --------- | ------------- | ------------------------------ | --------------- | ----------------------- |
| ≤ 50MB    | In-memory     | Azure Function                 | 5-10 seconds    | Standard processing     |
| 51-200MB  | Streaming     | Azure Function                 | 30-60 seconds   | Temp file + chunked     |
| 201MB-1GB | Queue-based   | Service Bus + Premium Function | 2-10 minutes    | Async processing        |
| > 1GB     | Not supported | -                              | -               | Consider file splitting |

## 📋 Deployment Options

### Option 1: Interactive Deployment (Recommended)

```bash
python deploy.py
```

**Prompts for:**

- Environment selection
- Resource configuration
- All required secrets
- Automatic resource creation

### Option 2: Bicep Template Direct

```bash
# Create resource group
az group create -n docusense-prod-rg -l eastus

# Deploy infrastructure
az deployment group create \
  -g docusense-prod-rg \
  -f docusense.bicep \
  -p envName=prod \
     searchSku=standard \
     funcSku=Y1 \
     openAiEndpoint="https://your-openai.openai.azure.com/" \
     openAiApiKey="your-key" \
     graphClientId="your-client-id" \
     graphClientSecret="your-secret" \
     tenantId="your-tenant-id"
```

### Option 3: GitHub Actions CI/CD

1. **Set Repository Secrets:**

   ```
   AZURE_CREDENTIALS         # Service principal JSON
   AZURE_OPENAI_ENDPOINT     # OpenAI endpoint
   AZURE_OPENAI_API_KEY      # OpenAI key
   GRAPH_CLIENT_ID           # Graph app registration
   GRAPH_CLIENT_SECRET       # Graph client secret
   AZURE_TENANT_ID           # Your tenant ID
   ```

2. **Push to trigger deployment:**
   ```bash
   git push origin main     # Deploys to prod
   git push origin develop  # Deploys to dev
   ```

## 🔧 Configuration

### Environment Variables

The Bicep template automatically configures:

```bash
# Function App Settings
FUNCTIONS_WORKER_RUNTIME=python
FUNCTIONS_WORKER_PROCESS_COUNT=1  # ChatGPT: Avoid parallel large downloads
WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT=10

# DocuSense Settings
AZURE_SEARCH_ENDPOINT=https://docusensesearch{suffix}.search.windows.net
AZURE_SEARCH_INDEX_NAME=docusense-index
AZURE_OPENAI_ENDPOINT={your-endpoint}
AZURE_CLIENT_ID={graph-client-id}
AZURE_TENANT_ID={tenant-id}

# Large File Processing
SERVICE_BUS_CONNECTION_STRING={auto-generated}
WEBHOOK_CLIENT_STATE=docusense-webhook-secret-{suffix}
```

### Search Index Tiers

**Basic ($250/month):**

- 2GB storage, 15M documents
- Good for small teams (<100 users)

**Standard ($1000/month):**

- 25GB storage, 50M documents
- Recommended for most deployments

**Standard3 ($6000/month):**

- 1TB storage, 200M documents
- Enterprise scale

## 📊 Cost Optimization (ChatGPT Recommendations)

### File Type Filtering

Automatic filtering prevents costly processing:

```python
# Supported types (will process)
.pdf, .docx, .pptx, .txt, .xlsx, .md

# Skipped types (saves bandwidth)
.zip, .mp4, .jpg, .exe, .db
```

### Embedding Cost Estimates

| File Type  | Size  | Est. Tokens  | Cost   |
| ---------- | ----- | ------------ | ------ |
| PDF        | 100MB | ~150K tokens | ~$15   |
| Word Doc   | 50MB  | ~75K tokens  | ~$7.50 |
| PowerPoint | 200MB | ~100K tokens | ~$10   |

### Cost Monitoring Queries

```kusto
// Daily processing costs
traces
| where message contains "Est. cost:"
| extend Cost = todouble(extract(@"Est\. cost: \$([0-9\.]+)", 1, message))
| summarize TotalCost = sum(Cost) by bin(timestamp, 1d)
```

## 🔍 Monitoring & Troubleshooting

### Key Metrics Dashboard

1. **File Processing Success Rate**

   ```kusto
   traces
   | where message contains "Successfully indexed"
   | summarize count() by bin(timestamp, 1h)
   ```

2. **Large File Queue Depth**

   ```kusto
   traces
   | where message contains "Enqueued large file"
   | summarize count() by bin(timestamp, 5m)
   ```

3. **Memory Usage Alerts**
   - Function timeout errors
   - Out of memory exceptions
   - Large file processing failures

### Common Issues

**"File too large" warnings:**

- Check Service Bus configuration
- Verify Premium Function App for >200MB files

**Webhook validation failures:**

- Verify client state matches deployment
- Check Microsoft Graph permissions

**Search index capacity:**

- Monitor document count vs tier limits
- Consider upgrading Search SKU

## 🛡️ Security Features

### Managed Identity RBAC

- Function App: Search Index Data Contributor
- API App: Search Index Data Reader
- No hardcoded connection strings

### Key Vault Integration

- All secrets stored securely
- Automatic rotation support
- Access policies by managed identity

### Multi-Tenant Isolation

- Tenant-aware document IDs
- Filtered search results
- Isolated webhook processing

## 🔄 Updates & Maintenance

### Infrastructure Updates

```bash
# Update infrastructure
az deployment group create \
  -g docusense-prod-rg \
  -f docusense.bicep \
  -p envName=prod  # Same parameters
```

### Application Updates

```bash
# Update Function App
cd docusense-backend
func azure functionapp publish <function-app-name>

# Update API Backend
az webapp up --name <api-app-name>

# Update Frontend
cd docusense-frontend
npm run build
az staticwebapp deploy --name <static-app-name> --source-location ./build
```

## 📈 Scaling Recommendations

### Small Teams (<100 users)

- Basic Search SKU
- Y1 Function App (Consumption)
- Free Static Web App

### Medium Teams (100-1000 users)

- Standard Search SKU
- EP1 Function App (Premium)
- Standard Static Web App

### Enterprise (1000+ users)

- Standard3 Search SKU
- EP2 Function App (Premium)
- Multiple regions
- Dedicated Service Bus namespace

## 🚀 Next Steps

1. **Deploy infrastructure:** `python deploy.py`
2. **Verify deployment:** Check all outputs in Azure Portal
3. **Test file processing:** Upload test documents
4. **Configure Teams app:** Use output URLs in manifest
5. **Set up monitoring:** Import dashboard from `monitoring_dashboard.json`
6. **Test alerts:** Upload large file to trigger telemetry
7. **Plan scaling:** Monitor usage and upgrade tiers as needed

## 📊 Production Monitoring (ChatGPT Implementation)

### Automatic Monitoring Setup

The Bicep template automatically creates:

- **Application Insights** with custom metrics
- **Log Analytics Workspace** for centralized logging
- **Alert Rules** for critical failures
- **Diagnostic Settings** for all services
- **Action Groups** for email notifications

### Key Metrics Tracked

| Metric               | Purpose                     | Alert Threshold   |
| -------------------- | --------------------------- | ----------------- |
| `IndexingDurationMs` | File processing performance | > 8 seconds       |
| `FileSizeBytes`      | File size distribution      | Informational     |
| `EmbeddingCostUSD`   | Processing cost tracking    | > $100/day        |
| Webhook success rate | Integration health          | < 95%             |
| Queue backlog        | Large file processing       | > 500 messages    |
| Search throttling    | Service limits              | > 10 events/15min |

### Production KQL Queries

**Webhook Failure Investigation:**

```kusto
requests
| where cloud_RoleName contains "docusense"
| where name contains "webhook"
| where success == false
| project timestamp, url, resultCode, duration, customDimensions
| order by timestamp desc
```

**Cost Analysis by Tenant:**

```kusto
customEvents
| where name == "file_processing_success"
| extend cost = todouble(customDimensions.estimated_cost_usd)
| extend tenant = tostring(customDimensions.tenant_id)
| summarize total_cost = sum(cost), file_count = count() by tenant
| order by total_cost desc
```

**Large File Processing Stats:**

```kusto
customEvents
| where name startswith "file_processing"
| extend file_size = todouble(customDimensions.file_size)
| extend processing_method = tostring(customDimensions.processing_method)
| where file_size > 50000000
| summarize success_rate = (countif(name == "file_processing_success") * 100.0) / count() by processing_method
```

## 📞 Support

For deployment issues:

1. Check deployment outputs in `deployment-outputs-{env}.json`
2. Review Azure Portal resource status
3. Check Application Insights logs
4. Verify all required secrets are set

The Bicep template ensures **idempotent deployments** - you can run it multiple times safely to update configuration or recover from failures.
