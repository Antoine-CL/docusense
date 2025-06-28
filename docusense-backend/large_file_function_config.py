"""
Configuration for large file processing Azure Function
Implements ChatGPT recommendations for handling 200MB-1GB files
"""

import os
import json

# ChatGPT: Large file Function App configuration
LARGE_FILE_FUNCTION_CONFIG = {
    # Function App settings
    "FUNCTIONS_WORKER_PROCESS_COUNT": "1",  # ChatGPT: Avoid parallel 1GB downloads
    "FUNCTIONS_EXTENSION_VERSION": "~4",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "PYTHON_VERSION": "3.11",
    
    # Timeout settings (Premium/Dedicated plan required)
    "functionTimeout": "00:10:00",  # ChatGPT: 10 minute timeout for large files
    
    # Scale settings
    "WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT": "1",  # Limit concurrent instances
    
    # Memory optimization
    "WEBSITE_MEMORY_LIMIT_MB": "1536",  # 1.5GB memory for large file processing
    
    # Storage settings
    "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING": None,  # Set during deployment
    "WEBSITE_CONTENTSHARE": None,  # Set during deployment
    
    # Application settings
    "AZURE_SEARCH_ENDPOINT": None,  # Set during deployment
    "AZURE_SEARCH_KEY": None,       # Set during deployment
    "AZURE_OPENAI_ENDPOINT": None,  # Set during deployment
    "AZURE_OPENAI_KEY": None,       # Set during deployment
    "AZURE_CLIENT_ID": None,        # Set during deployment
    "AZURE_CLIENT_SECRET": None,    # Set during deployment
    "AZURE_TENANT_ID": None,        # Set during deployment
    
    # Service Bus for queue processing
    "SERVICE_BUS_CONNECTION_STRING": None,  # Set during deployment
    
    # Monitoring
    "APPINSIGHTS_INSTRUMENTATIONKEY": None,  # Set during deployment
    "APPLICATIONINSIGHTS_CONNECTION_STRING": None,  # Set during deployment
}

def create_large_file_function_app_config() -> dict:
    """
    Create Function App configuration for large file processing
    """
    
    # Host.json configuration for large file processing
    host_json = {
        "version": "2.0",
        "functionTimeout": "00:10:00",  # 10 minutes
        "extensions": {
            "serviceBus": {
                "maxConcurrentCalls": 1,  # Process one large file at a time
                "prefetchCount": 0,
                "autoRenewTimeout": "00:05:00"
            },
            "http": {
                "routePrefix": "api",
                "maxOutstandingRequests": 5,
                "maxConcurrentRequests": 1  # Limit concurrent requests
            }
        },
        "logging": {
            "applicationInsights": {
                "samplingSettings": {
                    "isEnabled": True,
                    "maxTelemetryItemsPerSecond": 20
                }
            }
        },
        "retry": {
            "strategy": "exponentialBackoff",
            "maxRetryCount": 3,
            "minimumInterval": "00:00:02",
            "maximumInterval": "00:00:10"
        }
    }
    
    # Requirements.txt for large file processing
    requirements_txt = """
azure-functions==1.15.0
azure-search-documents==11.4.0
azure-servicebus==7.11.0
azure-identity==1.15.0
azure-storage-blob==12.19.0
requests==2.31.0
msal==1.25.0
PyJWT==2.8.0
cryptography==41.0.8
python-docx==1.1.0
PyPDF2==3.0.1
openpyxl==3.1.2
python-pptx==0.6.23
"""
    
    return {
        "host_json": host_json,
        "requirements_txt": requirements_txt,
        "app_settings": LARGE_FILE_FUNCTION_CONFIG
    }

def get_deployment_commands(resource_group: str, function_app_name: str) -> list:
    """
    Get Azure CLI commands for deploying large file processor
    """
    
    commands = [
        # Create Premium App Service Plan (required for 10min timeout)
        [
            "az", "functionapp", "plan", "create",
            "--name", f"{function_app_name}-premium",
            "--resource-group", resource_group,
            "--location", "eastus",
            "--sku", "EP1",  # Elastic Premium
            "--is-linux", "true"
        ],
        
        # Create Function App
        [
            "az", "functionapp", "create",
            "--name", f"{function_app_name}-large",
            "--resource-group", resource_group,
            "--plan", f"{function_app_name}-premium",
            "--runtime", "python",
            "--runtime-version", "3.11",
            "--functions-version", "4",
            "--os-type", "Linux"
        ],
        
        # Configure app settings
        [
            "az", "functionapp", "config", "appsettings", "set",
            "--name", f"{function_app_name}-large",
            "--resource-group", resource_group,
            "--settings",
            "FUNCTIONS_WORKER_PROCESS_COUNT=1",
            "WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT=1"
        ]
    ]
    
    return commands

def create_large_file_processor_function() -> str:
    """
    Create the Azure Function code for processing large files
    """
    
    function_code = '''
import azure.functions as func
import json
import logging
from queue_based_processor import process_queued_large_file

def main(msg: func.ServiceBusMessage) -> None:
    """
    Azure Function triggered by Service Bus queue for large file processing
    ChatGPT: Configured with FUNCTIONS_WORKER_PROCESS_COUNT=1 and 10min timeout
    """
    
    logging.info(f'Large file processor triggered: {msg.get_body().decode("utf-8")}')
    
    try:
        # Process the large file
        process_queued_large_file(msg)
        
    except Exception as e:
        logging.error(f'Error in large file processor: {str(e)}')
        raise  # Re-raise to trigger Service Bus retry
'''
    
    return function_code

# Monitoring queries for large file processing
MONITORING_QUERIES = {
    "large_file_processing_success_rate": """
        traces
        | where message contains "Successfully processed large file"
        | summarize SuccessCount = count() by bin(timestamp, 1h)
        | join kind=fullouter (
            traces
            | where message contains "Failed to process large file"
            | summarize FailureCount = count() by bin(timestamp, 1h)
        ) on timestamp
        | extend SuccessRate = SuccessCount * 100.0 / (SuccessCount + FailureCount)
        | project timestamp, SuccessCount, FailureCount, SuccessRate
    """,
    
    "large_file_queue_depth": """
        traces
        | where message contains "Enqueued large file"
        | summarize EnqueuedCount = count() by bin(timestamp, 5m)
        | join kind=fullouter (
            traces
            | where message contains "Processing queued large file"
            | summarize ProcessedCount = count() by bin(timestamp, 5m)
        ) on timestamp
        | extend QueueDepth = EnqueuedCount - ProcessedCount
        | project timestamp, EnqueuedCount, ProcessedCount, QueueDepth
    """,
    
    "large_file_processing_costs": """
        traces
        | where message contains "Est. cost:"
        | extend CostMatch = extract(@"Est\. cost: \$([0-9\.]+)", 1, message)
        | where isnotnull(CostMatch)
        | extend Cost = todouble(CostMatch)
        | summarize TotalCost = sum(Cost), FileCount = count() by bin(timestamp, 1d)
        | project timestamp, TotalCost, FileCount, AvgCostPerFile = TotalCost / FileCount
    """
}

def get_monitoring_dashboard_config() -> dict:
    """
    Get Azure Dashboard configuration for monitoring large file processing
    """
    
    return {
        "queries": MONITORING_QUERIES,
        "alerts": {
            "large_file_failure_rate": {
                "threshold": 10,  # Alert if >10% failure rate
                "frequency": "5m",
                "severity": "Warning"
            },
            "large_file_queue_backup": {
                "threshold": 50,  # Alert if queue depth >50
                "frequency": "5m", 
                "severity": "Critical"
            },
            "daily_processing_cost": {
                "threshold": 100,  # Alert if daily cost >$100
                "frequency": "1d",
                "severity": "Warning"
            }
        }
    } 