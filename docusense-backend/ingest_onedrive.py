import os
import uuid
from typing import List, Dict
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from graph_client import graph_client
from ingest_local import extract_text, chunk_text
from embedding import embed_text

load_dotenv()

def get_search_client():
    """Get Azure Search client"""
    return SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY"))
    )

def ingest_from_onedrive(drive_id: str = None, max_files: int = 10):
    """Ingest documents from OneDrive/SharePoint"""
    print("🔄 Starting OneDrive ingestion...")
    
    # Get available drives if no specific drive_id provided
    if not drive_id:
        drives = graph_client.list_drives()
        if not drives:
            print("❌ No drives found or authentication failed")
            return
        
        print("📁 Available drives:")
        for i, drive in enumerate(drives):
            print(f"  {i+1}. {drive.get('name', 'Unknown')} ({drive.get('id')})")
        
        # Try each drive until we find one with files
        files = None
        for i, drive in enumerate(drives):
            drive_id = drive["id"]
            drive_name = drive.get('name', 'Unknown')
            print(f"📂 Trying drive: {drive_name}")
            
            # Check if this drive has files
            files = graph_client.list_files(drive_id)
            if files:
                print(f"✅ Found {len(files)} files in drive '{drive_name}'")
                break
            else:
                print(f"⚠️  No files found in drive '{drive_name}'")
                if i < len(drives) - 1:
                    print("🔄 Trying next drive...")
                    continue
        
        if not files:
            print("❌ No files found in any accessible drive")
            return
    else:
        # List files in the specified drive
        files = graph_client.list_files(drive_id)
        if not files:
            print("❌ No files found in the drive")
            return
    
    # Filter for supported file types
    supported_extensions = {'.pdf', '.docx', '.pptx', '.txt'}
    supported_files = []
    
    for file in files:
        file_name = file.get('name', '')
        file_ext = os.path.splitext(file_name)[1].lower()
        if file_ext in supported_extensions:
            supported_files.append(file)
    
    print(f"📄 Found {len(supported_files)} supported files (PDF, DOCX, PPTX, TXT)")
    
    if not supported_files:
        print("❌ No supported file types found")
        return
    
    # Limit the number of files to process
    files_to_process = supported_files[:max_files]
    print(f"🔄 Processing {len(files_to_process)} files...")
    
    search_client = get_search_client()
    docs = []
    total_chunks = 0
    
    for file_info in files_to_process:
        file_name = file_info.get('name', 'Unknown')
        file_id = file_info.get('id')
        
        print(f"📄 Processing: {file_name}")
        
        try:
            # Download file to temporary location
            temp_path = graph_client.download_file(drive_id, file_id)
            if not temp_path:
                print(f"⚠️  Failed to download {file_name}")
                continue
            
            # Extract text from the file
            content = extract_text(temp_path)
            if not content.strip():
                print(f"⚠️  No text extracted from {file_name}")
                os.unlink(temp_path)  # Clean up temp file
                continue
            
            # Create chunks and embeddings
            file_chunks = 0
            for snippet, chunk_idx in chunk_text(content):
                try:
                    embedding = embed_text(snippet)
                    
                    doc = {
                        "id": str(uuid.uuid4()),
                        "title": file_name,
                        "content": snippet,
                        "chunk": chunk_idx,
                        "vector": embedding
                    }
                    
                    docs.append(doc)
                    file_chunks += 1
                    total_chunks += 1
                    
                    # Upload in batches of 50
                    if len(docs) >= 50:
                        search_client.upload_documents(documents=docs)
                        print(f"📤 Uploaded batch of {len(docs)} chunks")
                        docs = []
                        
                except Exception as e:
                    print(f"❌ Error processing chunk from {file_name}: {e}")
            
            print(f"✅ {file_name}: {file_chunks} chunks created")
            
            # Clean up temporary file
            os.unlink(temp_path)
            
        except Exception as e:
            print(f"❌ Error processing {file_name}: {e}")
            continue
    
    # Upload remaining documents
    if docs:
        search_client.upload_documents(documents=docs)
        print(f"📤 Uploaded final batch of {len(docs)} chunks")
    
    print(f"✅ OneDrive ingestion complete!")
    print(f"📊 Processed {len(files_to_process)} files, created {total_chunks} chunks")

def test_graph_connection():
    """Test Microsoft Graph API connection"""
    print("🔄 Testing Microsoft Graph API connection...")
    
    # Test token acquisition
    token = graph_client.get_token()
    if not token:
        print("❌ Failed to get access token")
        print("Please check your Azure AD configuration:")
        print("- AAD_CLIENT_ID")
        print("- AAD_TENANT_ID") 
        print("- AAD_CLIENT_SECRET")
        return False
    
    print("✅ Successfully acquired access token")
    
    # Test drives access
    drives = graph_client.list_drives()
    if not drives:
        print("❌ No drives accessible")
        print("Please check application permissions:")
        print("- Files.Read.All")
        print("- Sites.Read.All")
        return False
    
    print(f"✅ Found {len(drives)} accessible drives")
    for drive in drives:
        print(f"  📁 {drive.get('name', 'Unknown')} ({drive.get('driveType', 'unknown')})")
    
    return True

if __name__ == "__main__":
    # Test connection first
    if test_graph_connection():
        print("\n" + "="*50)
        # Run ingestion
        ingest_from_onedrive(max_files=5)
    else:
        print("\n❌ Graph API connection test failed")
        print("Please complete Azure AD app registration and update .env file") 