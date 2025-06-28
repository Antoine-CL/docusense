# Large File Handling in DocuSense

DocuSense now supports processing files of various sizes with different strategies based on file size.

## 📊 File Size Limits & Processing Methods

| File Size    | Processing Method | Location                          | Notes                          |
| ------------ | ----------------- | --------------------------------- | ------------------------------ |
| ≤ 50MB       | Standard          | Azure Function                    | In-memory processing           |
| 51MB - 200MB | Streaming         | Azure Function                    | Temp file + chunked processing |
| 201MB - 1GB  | Queue-based       | Service Bus + Background Function | Asynchronous processing        |
| > 1GB        | Not supported     | -                                 | Consider file splitting        |

## 🔧 Configuration

### Environment Variables

Add these to your Azure Function configuration:

```bash
# Optional: Service Bus for large files (>200MB)
SERVICE_BUS_CONNECTION_STRING="Endpoint=sb://your-namespace.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=your-key"
```

### Azure Resources Required

For **200MB+ files**, you need:

1. **Azure Service Bus Namespace**

   ```bash
   az servicebus namespace create --name docusense-sb --resource-group docusense-rg --location eastus
   ```

2. **Service Bus Queue**

   ```bash
   az servicebus queue create --name large-file-processing --namespace-name docusense-sb --resource-group docusense-rg
   ```

3. **Premium Function App** (for background processing)
   ```bash
   az functionapp create --name docusense-large-processor --resource-group docusense-rg --plan docusense-premium --runtime python --runtime-version 3.11
   ```

## 🚀 How It Works

### Standard Processing (≤50MB)

- File downloaded to memory
- Text extracted immediately
- Embeddings generated
- Indexed in real-time

### Streaming Processing (51-200MB)

- File streamed to temporary disk storage
- Text extracted from temp file
- Embeddings generated in batches
- Temp file cleaned up automatically

### Queue-based Processing (201MB-1GB)

- File metadata sent to Service Bus queue
- Background Azure Function processes file
- Uses blob storage for temporary files
- Chunked processing with optimized memory usage

## 📈 Performance Characteristics

| Method      | Processing Time | Memory Usage                  | Reliability         |
| ----------- | --------------- | ----------------------------- | ------------------- |
| Standard    | ~5-10 seconds   | High (file size + embeddings) | Excellent           |
| Streaming   | ~30-60 seconds  | Low (8MB chunks)              | Excellent           |
| Queue-based | ~2-10 minutes   | Very Low                      | Good (with retries) |

## ⚙️ Advanced Configuration

### Adjust Size Limits

In `large_file_handler.py`:

```python
# Increase streaming limit to 300MB
MAX_LARGE_FILE_SIZE = 300 * 1024 * 1024

# Increase queue threshold to 500MB
# In queue_based_processor.py:
def should_use_queue_processing(file_size: int) -> bool:
    return file_size > 500 * 1024 * 1024
```

### Optimize for Your Use Case

**For mostly small files (≤10MB):**

- Keep current settings
- Consider reducing streaming threshold

**For frequent large files (100MB+):**

- Set up Service Bus queue
- Consider Premium Function App plan
- Enable Application Insights monitoring

**For very large files (500MB+):**

- Consider Azure Batch or Container Instances
- Implement file chunking at source
- Use Azure Blob Storage for temporary files

## 🔍 Monitoring & Troubleshooting

### Key Metrics to Monitor

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
   | summarize count() by bin(timestamp, 1h)
   ```

3. **Memory Usage by File Size**
   ```kusto
   performanceCounters
   | where counter == "Memory Available Bytes"
   | join traces on timestamp
   | where message contains "Processing file"
   ```

### Common Issues

**"File too large" warnings:**

- Check if Service Bus is configured for 200MB+ files
- Verify Function App has sufficient resources

**Memory errors:**

- Files near the size threshold may still cause issues
- Consider lowering thresholds or upgrading Function App plan

**Queue processing delays:**

- Check Service Bus queue depth
- Verify background Function App is running
- Review Application Insights for errors

## 🛠️ Deployment Updates

Update your `deploy_webhooks.py` script:

```python
# Add Service Bus creation
def create_service_bus_resources():
    """Create Service Bus namespace and queue for large files"""
    try:
        # Create namespace
        run_command([
            "az", "servicebus", "namespace", "create",
            "--name", f"{FUNCTION_APP_NAME}-sb",
            "--resource-group", RESOURCE_GROUP,
            "--location", LOCATION
        ])

        # Create queue
        run_command([
            "az", "servicebus", "queue", "create",
            "--name", "large-file-processing",
            "--namespace-name", f"{FUNCTION_APP_NAME}-sb",
            "--resource-group", RESOURCE_GROUP
        ])

        print("✅ Service Bus resources created")

    except Exception as e:
        print(f"❌ Error creating Service Bus: {e}")
```

This comprehensive large file handling system ensures DocuSense can process documents of various sizes efficiently while maintaining system stability and performance.
