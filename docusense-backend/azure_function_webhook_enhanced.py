import azure.functions as func
import json
import logging
import os
import requests
from typing import Dict, List
from datetime import datetime

# Import your existing modules
from graph_client import graph_client
from ingest_local import extract_text, chunk_text
from embedding import embed_text
from azure_search_client import get_search_client
from large_file_handler import ingest_file_with_size_handling, can_process_file_size
from queue_based_processor import should_use_queue_processing, enqueue_large_file_processing
from file_type_filter import should_process_file, log_file_decision, get_estimated_processing_cost
from telemetry import logger, track_performance, log_info, log_error

# Configuration
WEBHOOK_CLIENT_STATE = os.getenv("WEBHOOK_CLIENT_STATE", "docusense-webhook-secret")

@track_performance("webhook_processing")
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function HTTP trigger for Microsoft Graph webhooks - Enhanced version"""
    
    log_info('Graph webhook notification received')
    
    try:
        # Handle validation token (initial subscription handshake)
        # ChatGPT: Must respond with plain text, not JSON
        validation_token = req.params.get('validationToken')
        if validation_token:
            logging.info(f'Webhook validation requested: {validation_token}')
            return func.HttpResponse(
                validation_token,
                status_code=200,
                mimetype="text/plain"
            )
        
        # Parse notification body
        try:
            req_body = req.get_json()
        except ValueError:
            logging.error('Invalid JSON in request body')
            return func.HttpResponse("Invalid JSON", status_code=400)
        
        if not req_body:
            logging.error('Empty request body')
            return func.HttpResponse("Empty body", status_code=400)
        
        # ChatGPT: Handle batch notifications - Graph sends arrays
        notifications = req_body.get("value", [])
        if not notifications:
            logging.warning('No notifications in request body')
            return func.HttpResponse("No notifications", status_code=400)
        
        logging.info(f'Processing {len(notifications)} notifications')
        
        # Validate and process each notification
        for notification in notifications:
            # ChatGPT: Critical clientState validation
            client_state = notification.get("clientState")
            tenant_id = validate_client_state(client_state)
            
            if tenant_id is None:
                log_error('Invalid client state', client_state=client_state)
                return func.HttpResponse("Unauthorized", status_code=401)
            
            # Add tenant context for processing
            notification["tenant_id"] = tenant_id
            
            # Log webhook event with telemetry
            logger.log_webhook_event("notification_received", notification)
            
            # ChatGPT: Use queue-based processing for robustness
            # For now, process directly but structure for queue migration
            process_notification_sync(notification)
        
        return func.HttpResponse(
            json.dumps({"status": "accepted", "processed": len(notifications)}),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logging.error(f'Error processing webhook: {str(e)}')
        return func.HttpResponse("Internal error", status_code=500)

def validate_client_state(client_state: str) -> str:
    """
    Validate client state and extract tenant ID if multi-tenant format
    Returns tenant_id or None if invalid
    """
    if not client_state:
        return None
    
    # Single-tenant format
    if client_state == WEBHOOK_CLIENT_STATE:
        return "default"
    
    # Multi-tenant format: docusense-{tenant_id}-webhook
    if client_state.startswith("docusense-") and client_state.endswith("-webhook"):
        tenant_id = client_state[10:-8]  # Extract tenant ID
        if tenant_id:  # Ensure tenant ID is not empty
            return tenant_id
    
    return None

def process_notification_sync(notification: Dict):
    """
    Process a single Graph notification synchronously
    ChatGPT: Structure this for easy migration to queue-based processing
    """
    try:
        resource = notification.get("resource", "")
        change_type = notification.get("changeType", "")
        tenant_id = notification.get("tenant_id", "default")
        
        logging.info(f'Processing {change_type} notification for {resource} (tenant: {tenant_id})')
        
        # Extract drive ID from resource path
        if "/drives/" in resource:
            parts = resource.split("/")
            if len(parts) >= 3:
                drive_id = parts[2]
                
                # ChatGPT: Call delta API to get actual changes
                process_drive_delta(drive_id, tenant_id)
            else:
                logging.error(f'Invalid resource path format: {resource}')
        else:
            logging.warning(f'Unsupported resource type: {resource}')
        
    except Exception as e:
        logging.error(f'Error processing notification: {str(e)}')

def process_drive_delta(drive_id: str, tenant_id: str):
    """
    ChatGPT: Use delta query to get actual file changes
    Process changes and handle large files within memory limits
    """
    try:
        headers = graph_client.get_headers()
        
        # Get delta changes with specific fields to minimize response size
        delta_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/delta"
        params = {
            "$select": "id,name,size,lastModifiedDateTime,webUrl,file,deleted,parentReference"
        }
        
        response = requests.get(delta_url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            changes = data.get("value", [])
            
            logging.info(f'Processing {len(changes)} delta changes for tenant {tenant_id}')
            
            for item in changes:
                try:
                    process_single_item_change(item, drive_id, tenant_id)
                except Exception as e:
                    logging.error(f'Error processing item {item.get("id", "unknown")}: {str(e)}')
                    # Continue processing other items
            
            # Handle pagination if needed
            next_link = data.get("@odata.nextLink")
            if next_link:
                logging.info(f'Delta query has more pages, consider implementing pagination')
                
        else:
            logging.error(f'Delta query failed: {response.status_code} - {response.text}')
            
    except Exception as e:
        logging.error(f'Error processing drive delta: {str(e)}')

def process_single_item_change(item: Dict, drive_id: str, tenant_id: str):
    """Process a single file change from delta query"""
    
    item_id = item.get("id")
    if not item_id:
        logging.warning('Item missing ID, skipping')
        return
    
    if "deleted" in item:
        # File was deleted
        logging.info(f'File deleted: {item_id}')
        remove_file_from_index(drive_id, item_id, tenant_id)
        
    elif "file" in item:
        # File was created or updated
        file_name = item.get("name", "Unknown")
        file_size = item.get("size", 0)
        last_modified = item.get("lastModifiedDateTime")
        mime_type = item.get("file", {}).get("mimeType")
        
        # ChatGPT: Check file type before processing to save bandwidth
        should_process, reason = should_process_file(file_name, mime_type, file_size)
        log_file_decision(file_name, file_size, mime_type, should_process, reason)
        
        if not should_process:
            return  # Skip this file
        
        # Determine processing method based on file size
        if should_use_queue_processing(file_size):
            # Files >200MB go to queue for background processing
            success = enqueue_large_file_processing(drive_id, item_id, file_name, file_size, tenant_id)
            if success:
                logging.info(f'Large file {file_name} ({file_size} bytes) enqueued for background processing')
            else:
                logging.error(f'Failed to enqueue large file {file_name}')
            return
        
        # Check if file can be processed immediately (up to 200MB with streaming)
        can_process, method = can_process_file_size(file_size)
        if not can_process:
            logging.warning(f'File {file_name} too large ({file_size} bytes), maximum supported is 1GB via queue')
            return
        
        # File type already checked above, proceed with processing
            # Check idempotency
            if not is_already_processed(drive_id, item_id, last_modified, tenant_id):
                # Prepare file metadata for telemetry
                file_meta = {
                    "file_name": file_name,
                    "file_size": file_size,
                    "tenant_id": tenant_id,
                    "drive_id": drive_id,
                    "item_id": item_id,
                    "processing_method": method,
                    "estimated_cost": get_estimated_processing_cost(file_size, file_name.split('.')[-1] if '.' in file_name else 'unknown')
                }
                
                log_info(f'Processing file: {file_name} ({method} method, tenant: {tenant_id})')
                
                start_time = time.time()
                success = ingest_file_with_size_handling(drive_id, item_id, file_name, file_size, tenant_id)
                duration_ms = (time.time() - start_time) * 1000
                
                if success:
                    mark_as_processed(drive_id, item_id, last_modified, tenant_id)
                    logger.log_file_processing("file_indexed", file_meta, duration_ms)
                else:
                    logger.log_file_processing("file_failed", file_meta, duration_ms, error=Exception("Processing failed"))
            else:
                log_info(f'File {file_name} already processed, skipping')

# ChatGPT: Idempotency cache (production should use Redis/database)
processed_files_cache = {}

def is_already_processed(drive_id: str, item_id: str, last_modified: str, tenant_id: str) -> bool:
    """Check if file version was already processed (idempotency)"""
    cache_key = f"{tenant_id}_{drive_id}_{item_id}"
    cached_timestamp = processed_files_cache.get(cache_key)
    return cached_timestamp == last_modified

def mark_as_processed(drive_id: str, item_id: str, last_modified: str, tenant_id: str):
    """Mark file version as processed"""
    cache_key = f"{tenant_id}_{drive_id}_{item_id}"
    processed_files_cache[cache_key] = last_modified

def ingest_single_file(drive_id: str, item_id: str, file_name: str, tenant_id: str):
    """
    Ingest a single file with tenant context
    ChatGPT: Stream download to /tmp for large files
    """
    temp_path = None
    
    try:
        logging.info(f'Ingesting file: {file_name} (tenant: {tenant_id})')
        
        # Download file to temporary location
        temp_path = graph_client.download_file(drive_id, item_id)
        if not temp_path:
            logging.error(f'Failed to download {file_name}')
            return
        
        # Extract text content
        content = extract_text(temp_path)
        if not content.strip():
            logging.warning(f'No text extracted from {file_name}')
            return
        
        # Remove existing chunks for this file (handle updates)
        remove_file_from_index(drive_id, item_id, tenant_id)
        
        # Create new chunks and embeddings
        search_client = get_search_client()
        docs = []
        
        for snippet, chunk_idx in chunk_text(content):
            try:
                embedding = embed_text(snippet)
                
                # Include tenant context in document
                doc = {
                    "id": f"{tenant_id}_{drive_id}_{item_id}_{chunk_idx}",
                    "title": file_name,
                    "content": snippet,
                    "chunk": chunk_idx,
                    "vector": embedding,
                    "source_drive_id": drive_id,
                    "source_item_id": item_id,
                    "tenant_id": tenant_id,
                    "last_modified": datetime.utcnow().isoformat()
                }
                
                docs.append(doc)
                
            except Exception as e:
                logging.error(f'Error processing chunk from {file_name}: {str(e)}')
        
        # Upload to search index
        if docs:
            search_client.upload_documents(documents=docs)
            logging.info(f'Indexed {len(docs)} chunks from {file_name} (tenant: {tenant_id})')
        
    except Exception as e:
        logging.error(f'Error ingesting file {item_id}: {str(e)}')
    
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logging.warning(f'Failed to clean up temp file {temp_path}: {str(e)}')

def remove_file_from_index(drive_id: str, item_id: str, tenant_id: str):
    """Remove all chunks for a deleted file from the search index"""
    
    try:
        search_client = get_search_client()
        
        # Search for all documents from this file for this tenant
        filter_query = f"source_drive_id eq '{drive_id}' and source_item_id eq '{item_id}' and tenant_id eq '{tenant_id}'"
        
        results = search_client.search(
            search_text="*",
            filter=filter_query
        )
        
        # Delete all chunks
        doc_ids = [doc["id"] for doc in results]
        if doc_ids:
            search_client.delete_documents(documents=[{"id": doc_id} for doc_id in doc_ids])
            logging.info(f'Removed {len(doc_ids)} chunks from search index (tenant: {tenant_id})')
            
    except Exception as e:
        logging.error(f'Error removing file from index: {str(e)}')

# ChatGPT: Future enhancement - Queue-based processing
def enqueue_notification_for_processing(notification: Dict):
    """
    Future enhancement: Enqueue notification for async processing
    This would use Azure Service Bus or Storage Queue
    """
    # Example implementation:
    # queue_client = ServiceBusClient.from_connection_string(connection_string)
    # queue_client.send_message(json.dumps(notification))
    pass

def process_notification_from_queue(queue_message: str):
    """
    Future enhancement: Process notification from queue
    This would be triggered by a separate Azure Function
    """
    # Example implementation:
    # notification = json.loads(queue_message)
    # process_notification_sync(notification)
    pass 