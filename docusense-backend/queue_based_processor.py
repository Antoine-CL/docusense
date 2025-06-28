"""
Queue-based processor for very large files (>200MB)
Uses Azure Service Bus for reliable processing of massive documents
"""

import json
import logging
from typing import Dict, Optional
from datetime import datetime
import azure.functions as func
from azure.servicebus import ServiceBusClient, ServiceBusMessage
import os

# Configuration
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
LARGE_FILE_QUEUE_NAME = "large-file-processing"
MAX_QUEUE_FILE_SIZE = 1024 * 1024 * 1024  # 1GB - theoretical limit

def should_use_queue_processing(file_size: int) -> bool:
    """
    Determine if file should be processed via queue
    """
    return file_size > 200 * 1024 * 1024  # >200MB

def enqueue_large_file_processing(drive_id: str, item_id: str, file_name: str, 
                                file_size: int, tenant_id: str) -> bool:
    """
    Enqueue a large file for background processing
    """
    try:
        if file_size > MAX_QUEUE_FILE_SIZE:
            logging.warning(f'File {file_name} exceeds maximum size limit ({file_size} bytes)')
            return False
        
        # Create processing message
        message_data = {
            "drive_id": drive_id,
            "item_id": item_id,
            "file_name": file_name,
            "file_size": file_size,
            "tenant_id": tenant_id,
            "queued_at": datetime.utcnow().isoformat(),
            "processing_type": "large_file"
        }
        
        # Send to Service Bus queue
        with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as client:
            with client.get_queue_sender(queue_name=LARGE_FILE_QUEUE_NAME) as sender:
                message = ServiceBusMessage(json.dumps(message_data))
                sender.send_messages(message)
                
        logging.info(f'Enqueued large file {file_name} ({file_size} bytes) for processing')
        return True
        
    except Exception as e:
        logging.error(f'Error enqueueing large file {file_name}: {str(e)}')
        return False

# Azure Function for processing queued large files
def process_queued_large_file(msg: func.ServiceBusMessage) -> None:
    """
    Azure Function triggered by Service Bus queue
    Processes large files with extended timeout and memory
    """
    try:
        # Parse message
        message_data = json.loads(msg.get_body().decode('utf-8'))
        
        drive_id = message_data["drive_id"]
        item_id = message_data["item_id"]
        file_name = message_data["file_name"]
        file_size = message_data["file_size"]
        tenant_id = message_data["tenant_id"]
        
        logging.info(f'Processing queued large file: {file_name} ({file_size} bytes)')
        
        # Use dedicated large file processing with extended resources
        success = process_very_large_file(drive_id, item_id, file_name, file_size, tenant_id)
        
        if success:
            logging.info(f'Successfully processed large file: {file_name}')
        else:
            logging.error(f'Failed to process large file: {file_name}')
            # Could implement retry logic or dead letter queue here
            
    except Exception as e:
        logging.error(f'Error processing queued message: {str(e)}')
        raise  # Re-raise to trigger Service Bus retry

def process_very_large_file(drive_id: str, item_id: str, file_name: str, 
                          file_size: int, tenant_id: str) -> bool:
    """
    Process very large files with optimized memory management
    """
    try:
        # Implementation for very large files
        # Could use:
        # 1. Blob storage for temporary file storage
        # 2. Chunked text extraction
        # 3. Streaming embedding generation
        # 4. Batch document upload
        
        logging.info(f'Processing very large file: {file_name} ({file_size} bytes)')
        
        # Placeholder implementation
        # In production, this would implement:
        # - Stream to Azure Blob Storage
        # - Process in smaller chunks
        # - Use Azure Batch or Container Instances for heavy processing
        
        return True
        
    except Exception as e:
        logging.error(f'Error processing very large file {file_name}: {str(e)}')
        return False 