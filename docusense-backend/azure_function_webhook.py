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

# Configuration
WEBHOOK_CLIENT_STATE = os.getenv("WEBHOOK_CLIENT_STATE", "docusense-webhook-secret")

def main(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function HTTP trigger for Microsoft Graph webhooks"""
    
    logging.info('Graph webhook notification received')
    
    try:
        # Handle validation token (initial subscription handshake)
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
        
        # Validate client state
        notifications = req_body.get("value", [])
        for notification in notifications:
            client_state = notification.get("clientState")
            
            # Support both single-tenant and multi-tenant client states
            valid_client_states = [
                WEBHOOK_CLIENT_STATE,  # Original format
                # Multi-tenant format: docusense-{tenant_id}-webhook
            ]
            
            # Check if it's a multi-tenant client state
            is_valid = False
            tenant_id = None
            
            if client_state == WEBHOOK_CLIENT_STATE:
                is_valid = True
            elif client_state and client_state.startswith("docusense-") and client_state.endswith("-webhook"):
                # Extract tenant ID from client state
                tenant_id = client_state[10:-8]  # Remove "docusense-" and "-webhook"
                is_valid = True
            
            if not is_valid:
                logging.error(f'Invalid client state: {client_state}')
                return func.HttpResponse("Unauthorized", status_code=401)
            
            # Store tenant ID in notification for later processing
            if tenant_id:
                notification["tenant_id"] = tenant_id
        
        # Process notifications
        for notification in notifications:
            process_notification(notification)
        
        return func.HttpResponse(
            json.dumps({"status": "accepted"}),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logging.error(f'Error processing webhook: {str(e)}')
        return func.HttpResponse("Internal error", status_code=500)

def process_notification(notification: Dict):
    """Process a single Graph notification"""
    
    try:
        resource = notification.get("resource", "")
        change_type = notification.get("changeType", "")
        
        logging.info(f'Processing {change_type} notification for {resource}')
        
        # Extract drive ID from resource
        if "/drives/" in resource:
            parts = resource.split("/")
            drive_id = parts[2]
            
            # Use delta query to get actual changes
            process_drive_delta(drive_id)
        
    except Exception as e:
        logging.error(f'Error processing notification: {str(e)}')

def process_drive_delta(drive_id: str):
    """Process delta changes for a drive"""
    
    try:
        headers = graph_client.get_headers()
        
        # Get delta changes
        delta_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/delta"
        params = {
            "$select": "id,name,size,lastModifiedDateTime,webUrl,file,deleted"
        }
        
        response = requests.get(delta_url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            changes = data.get("value", [])
            
            logging.info(f'Processing {len(changes)} delta changes')
            
            for item in changes:
                if "deleted" in item:
                    # File was deleted
                    item_id = item.get("id")
                    remove_file_from_index(drive_id, item_id)
                elif "file" in item:
                    # File was created or updated
                    item_id = item.get("id")
                    file_name = item.get("name", "Unknown")
                    
                    # Check if supported file type
                    file_ext = os.path.splitext(file_name)[1].lower()
                    supported_extensions = {'.pdf', '.docx', '.pptx', '.txt'}
                    
                    if file_ext in supported_extensions:
                        ingest_single_file(drive_id, item_id, file_name)
                    else:
                        logging.info(f'Skipping unsupported file type: {file_name}')
        else:
            logging.error(f'Delta query failed: {response.status_code} - {response.text}')
            
    except Exception as e:
        logging.error(f'Error processing drive delta: {str(e)}')

def ingest_single_file(drive_id: str, item_id: str, file_name: str):
    """Ingest a single file"""
    
    try:
        logging.info(f'Ingesting file: {file_name}')
        
        # Download file
        temp_path = graph_client.download_file(drive_id, item_id)
        if not temp_path:
            logging.error(f'Failed to download {file_name}')
            return
        
        # Extract text
        content = extract_text(temp_path)
        if not content.strip():
            logging.warning(f'No text extracted from {file_name}')
            os.unlink(temp_path)
            return
        
        # Remove existing chunks for this file
        remove_file_from_index(drive_id, item_id)
        
        # Create new chunks and embeddings
        search_client = get_search_client()
        docs = []
        
        for snippet, chunk_idx in chunk_text(content):
            try:
                embedding = embed_text(snippet)
                
                doc = {
                    "id": f"{drive_id}_{item_id}_{chunk_idx}",
                    "title": file_name,
                    "content": snippet,
                    "chunk": chunk_idx,
                    "vector": embedding,
                    "source_drive_id": drive_id,
                    "source_item_id": item_id,
                    "last_modified": datetime.utcnow().isoformat()
                }
                
                docs.append(doc)
                
            except Exception as e:
                logging.error(f'Error processing chunk from {file_name}: {str(e)}')
        
        # Upload to search index
        if docs:
            search_client.upload_documents(documents=docs)
            logging.info(f'Indexed {len(docs)} chunks from {file_name}')
        
        # Clean up temp file
        os.unlink(temp_path)
        
    except Exception as e:
        logging.error(f'Error ingesting file {item_id}: {str(e)}')

def remove_file_from_index(drive_id: str, item_id: str):
    """Remove all chunks for a deleted file from the search index"""
    
    try:
        search_client = get_search_client()
        
        # Search for all documents from this file
        results = search_client.search(
            search_text="*",
            filter=f"source_drive_id eq '{drive_id}' and source_item_id eq '{item_id}'"
        )
        
        # Delete all chunks
        doc_ids = [doc["id"] for doc in results]
        if doc_ids:
            search_client.delete_documents(documents=[{"id": doc_id} for doc_id in doc_ids])
            logging.info(f'Removed {len(doc_ids)} chunks from search index')
            
    except Exception as e:
        logging.error(f'Error removing file from index: {str(e)}') 