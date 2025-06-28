#!/usr/bin/env python3
"""
Microsoft Graph Webhook Handler for Real-time Document Ingestion
"""

import os
import json
import hmac
import hashlib
import requests
from typing import List, Dict
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from datetime import datetime, timedelta
import asyncio

from graph_client import graph_client
from ingest_local import extract_text, chunk_text
from embedding import embed_text
from azure_search_client import get_search_client

load_dotenv()

app = FastAPI()

# Webhook validation token (set in environment)
WEBHOOK_CLIENT_STATE = os.getenv("WEBHOOK_CLIENT_STATE", "your-secret-state")

@app.post("/api/webhooks/graph")
async def handle_graph_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle Microsoft Graph webhook notifications"""
    
    # Handle validation token (initial subscription handshake)
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        print(f"🔐 Webhook validation requested: {validation_token}")
        return {"validationToken": validation_token}
    
    # Validate webhook for actual notifications
    validation_result = await validate_webhook(request)
    if not validation_result:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Parse notification
    body = await request.json()
    notifications = body.get("value", [])
    
    # Process each notification in background
    for notification in notifications:
        background_tasks.add_task(process_file_change, notification)
    
    return {"status": "accepted"}

async def validate_webhook(request: Request) -> bool:
    """Validate webhook request authenticity for notifications"""
    
    # Verify client state for actual notifications
    try:
        body = await request.json()
        notifications = body.get("value", [])
        
        for notification in notifications:
            client_state = notification.get("clientState")
            if client_state != WEBHOOK_CLIENT_STATE:
                print(f"❌ Invalid client state: {client_state}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Webhook validation error: {e}")
        return False

async def process_file_change(notification: Dict):
    """Process a file change notification using delta query"""
    
    try:
        resource = notification.get("resource", "")
        change_type = notification.get("changeType", "")
        
        print(f"📢 Webhook: {change_type} - {resource}")
        
        # Use delta query to get actual changes (ChatGPT's recommendation)
        # The notification doesn't contain the file data, just tells us something changed
        if "/drives/" in resource:
            parts = resource.split("/")
            drive_id = parts[2]
            
            # Query for delta changes in this drive
            await process_drive_delta(drive_id)
                
    except Exception as e:
        print(f"❌ Error processing webhook notification: {e}")

async def process_drive_delta(drive_id: str):
    """Process delta changes for a specific drive"""
    
    try:
        headers = graph_client.get_headers()
        
        # Get delta changes (files that have changed since last check)
        delta_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/delta"
        params = {
            "$select": "id,name,size,lastModifiedDateTime,webUrl,file,deleted"
        }
        
        response = requests.get(delta_url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            changes = data.get("value", [])
            
            print(f"📊 Processing {len(changes)} delta changes")
            
            for item in changes:
                if "deleted" in item:
                    # File was deleted
                    item_id = item.get("id")
                    await remove_file_from_index(drive_id, item_id)
                elif "file" in item:
                    # File was created or updated
                    item_id = item.get("id")
                    last_modified = item.get("lastModifiedDateTime")
                    
                    # Check if we already processed this version (idempotency)
                    if not await is_already_processed(drive_id, item_id, last_modified):
                        await ingest_single_file(drive_id, item_id)
                        await mark_as_processed(drive_id, item_id, last_modified)
        else:
            print(f"❌ Delta query failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Error processing drive delta: {e}")

# Simple in-memory cache for processed files (production should use Redis/database)
processed_files_cache = {}

async def is_already_processed(drive_id: str, item_id: str, last_modified: str) -> bool:
    """Check if file version was already processed (idempotency)"""
    cache_key = f"{drive_id}_{item_id}"
    cached_timestamp = processed_files_cache.get(cache_key)
    return cached_timestamp == last_modified

async def mark_as_processed(drive_id: str, item_id: str, last_modified: str):
    """Mark file version as processed"""
    cache_key = f"{drive_id}_{item_id}"
    processed_files_cache[cache_key] = last_modified

async def ingest_single_file(drive_id: str, item_id: str):
    """Ingest a single file that was created or updated"""
    
    try:
        # Get file info
        file_info = graph_client.get_file_info(drive_id, item_id)
        if not file_info:
            print(f"⚠️  Could not get file info for {item_id}")
            return
        
        file_name = file_info.get("name", "Unknown")
        file_ext = os.path.splitext(file_name)[1].lower()
        
        # Check if supported file type
        supported_extensions = {'.pdf', '.docx', '.pptx', '.txt'}
        if file_ext not in supported_extensions:
            print(f"⚠️  Skipping unsupported file type: {file_name}")
            return
        
        print(f"📄 Processing updated file: {file_name}")
        
        # Download file
        temp_path = graph_client.download_file(drive_id, item_id)
        if not temp_path:
            print(f"⚠️  Failed to download {file_name}")
            return
        
        # Extract text
        content = extract_text(temp_path)
        if not content.strip():
            print(f"⚠️  No text extracted from {file_name}")
            os.unlink(temp_path)
            return
        
        # Remove existing chunks for this file
        await remove_file_from_index(drive_id, item_id)
        
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
                    "last_modified": file_info.get("lastModifiedDateTime")
                }
                
                docs.append(doc)
                
            except Exception as e:
                print(f"❌ Error processing chunk from {file_name}: {e}")
        
        # Upload to search index
        if docs:
            search_client.upload_documents(documents=docs)
            print(f"✅ Indexed {len(docs)} chunks from {file_name}")
        
        # Clean up temp file
        os.unlink(temp_path)
        
    except Exception as e:
        print(f"❌ Error ingesting file {item_id}: {e}")

async def remove_file_from_index(drive_id: str, item_id: str):
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
            print(f"🗑️  Removed {len(doc_ids)} chunks from search index")
            
    except Exception as e:
        print(f"❌ Error removing file from index: {e}")

# Webhook subscription management
class WebhookManager:
    """Manage Microsoft Graph webhook subscriptions"""
    
    def __init__(self):
        self.subscriptions = []
    
    def create_subscription(self, drive_id: str, notification_url: str, tenant_id: str = None) -> Dict:
        """Create a webhook subscription for a drive"""
        
        # Include tenant ID in notification URL for multi-tenant routing
        if tenant_id and "?" not in notification_url:
            notification_url += f"?tenant={tenant_id}"
        elif tenant_id:
            notification_url += f"&tenant={tenant_id}"
        
        # Use tenant-specific client state if provided
        client_state = f"docusense-{tenant_id}-webhook" if tenant_id else WEBHOOK_CLIENT_STATE
        
        subscription_data = {
            "changeType": "created,updated,deleted",
            "notificationUrl": notification_url,
            "resource": f"/drives/{drive_id}/root",
            "expirationDateTime": (datetime.utcnow() + timedelta(days=3)).isoformat() + "Z",
            "clientState": client_state
        }
        
        try:
            headers = graph_client.get_headers()
            response = requests.post(
                "https://graph.microsoft.com/v1.0/subscriptions",
                headers=headers,
                json=subscription_data
            )
            
            if response.status_code == 201:
                subscription = response.json()
                self.subscriptions.append(subscription)
                print(f"✅ Created webhook subscription: {subscription['id']}")
                return subscription
            else:
                print(f"❌ Failed to create subscription: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating webhook subscription: {e}")
            return None
    
    def renew_subscription(self, subscription_id: str):
        """Renew a webhook subscription before it expires"""
        
        renewal_data = {
            "expirationDateTime": (datetime.utcnow() + timedelta(days=3)).isoformat() + "Z"
        }
        
        try:
            headers = graph_client.get_headers()
            response = requests.patch(
                f"https://graph.microsoft.com/v1.0/subscriptions/{subscription_id}",
                headers=headers,
                json=renewal_data
            )
            
            if response.status_code == 200:
                print(f"✅ Renewed webhook subscription: {subscription_id}")
                return True
            else:
                print(f"❌ Failed to renew subscription: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error renewing webhook subscription: {e}")
            return False

# Initialize webhook manager
webhook_manager = WebhookManager()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002) 