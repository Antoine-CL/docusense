import os
from dotenv import load_dotenv
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile
)
from azure.core.credentials import AzureKeyCredential

load_dotenv()

endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
key = os.getenv("AZURE_SEARCH_API_KEY")
index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

credential = AzureKeyCredential(key)
index_client = SearchIndexClient(endpoint=endpoint, credential=credential)

# Define the fields for the index
fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
    SearchableField(name="title", type=SearchFieldDataType.String, filterable=True, sortable=True),
    SearchableField(name="content", type=SearchFieldDataType.String),
    SimpleField(name="chunk", type=SearchFieldDataType.Int32),
    SearchField(
        name="vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=1536,
        vector_search_profile_name="myHnswProfile"
    )
]

# Configure vector search
vector_search = VectorSearch(
    algorithms=[
        HnswAlgorithmConfiguration(name="myHnsw")
    ],
    profiles=[
        VectorSearchProfile(
            name="myHnswProfile",
            algorithm_configuration_name="myHnsw"
        )
    ]
)

# Create the search index
index = SearchIndex(
    name=index_name,
    fields=fields,
    vector_search=vector_search
)

try:
    result = index_client.create_or_update_index(index)
    print(f"✅ Index '{index_name}' created/updated successfully!")
    print(f"Index has {len(result.fields)} fields")
except Exception as e:
    print(f"❌ Error creating index: {e}") 