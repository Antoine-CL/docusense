# DocuSense Quick Deploy 🚀

## One-Command Deployment

Deploy your DocuSense webhook system with a single command:

```bash
python3 quick_deploy.py
```

That's it! The script will:

1. ✅ Check if you have a `.env` file (create one if needed)
2. ✅ Check if you're logged into Azure (prompt login if needed)
3. ✅ Create all Azure resources (Function App, Storage, etc.)
4. ✅ Deploy the webhook functions
5. ✅ Set up webhook subscriptions
6. ✅ Save configuration to `webhook_config.json`

## Manual Steps (if preferred)

### Step 1: Environment Setup

```bash
python3 setup_env.py
```

### Step 2: Azure Login

```bash
az login
```

### Step 3: Deploy

```bash
python3 deploy_webhooks.py
```

## What Gets Created

- **Resource Group**: `docusense-rg`
- **Function App**: `docusense-webhooks`
- **Storage Account**: `docusensewebhookstorage`
- **App Service Plan**: `docusense-plan`

## Configuration

The deployment uses these environment variables:

- `TENANT_ID` - Your Azure AD tenant ID
- `CLIENT_ID` - DocuSense-API app registration client ID
- `CLIENT_SECRET` - DocuSense-API app registration client secret
- `AZURE_SEARCH_SERVICE_NAME` - Your Azure AI Search service name
- `AZURE_SEARCH_API_KEY` - Your Azure AI Search admin key
- `AZURE_OPENAI_ENDPOINT` - Your Azure OpenAI endpoint
- `AZURE_OPENAI_API_KEY` - Your Azure OpenAI API key

## Output

After successful deployment:

- `webhook_config.json` - Contains your webhook URL and resource info
- Webhook subscriptions are automatically created for your tenant
- Real-time document ingestion is active

## Troubleshooting

If deployment fails:

1. Check your `.env` file has all required variables
2. Ensure you're logged into Azure: `az account show`
3. Verify your app registration has the required permissions
4. Check Azure resource naming conflicts (names must be globally unique)

## Clean Up

To remove all resources:

```bash
az group delete --name docusense-rg --yes --no-wait
```

## Support

Check these files for detailed documentation:

- `WEBHOOK_DEPLOYMENT_GUIDE.md` - Detailed deployment guide
- `REAL_TIME_INGESTION.md` - How the webhook system works
- `SETUP_GUIDE.md` - Complete project setup guide
