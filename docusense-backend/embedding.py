import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT")

def embed_text(text: str) -> list[float]:
    try:
        response = client.embeddings.create(
            input=text,
            model=DEPLOYMENT_NAME
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ Azure OpenAI Error: {e}")
        print("⚠️  Falling back to mock embedding")
        return [0.1] * 1536  # Fallback mock embedding 