import os
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from embedding import embed_text

load_dotenv()

def get_search_client():
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    key = os.getenv("AZURE_SEARCH_API_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
    
    credential = AzureKeyCredential(key)
    return SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)

def get_index_client():
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    key = os.getenv("AZURE_SEARCH_API_KEY")
    
    credential = AzureKeyCredential(key)
    return SearchIndexClient(endpoint=endpoint, credential=credential)

def search_docs(query: str, top_k: int = 5):
    """Hybrid search using both vector similarity and keyword matching"""
    search_client = get_search_client()
    
    # Generate embedding for the query
    query_embedding = embed_text(query)
    
    # Create vector query
    vector_query = VectorizedQuery(
        vector=query_embedding,
        k_nearest_neighbors=top_k,
        fields="vector"
    )
    
    # Perform hybrid search (vector + keyword)
    results = search_client.search(
        search_text=query,  # Keyword search
        vector_queries=[vector_query],  # Vector search
        select=["title", "content", "chunk"],  # Only select fields that exist
        top=top_k
    )
    
    # Format results
    matches = []
    for result in results:
        content = result.get("content", "")
        snippet = content[:240] + "..." if len(content) > 240 else content
        
        matches.append({
            "metadata": {
                "title": result.get("title", ""),
                "snippet": snippet
            },
            "score": result.get("@search.score", 0.0)
        })
    
    return matches 