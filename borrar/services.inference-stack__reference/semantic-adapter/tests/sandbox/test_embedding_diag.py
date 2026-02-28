import os
from google import genai
from google.genai import types

def test_embedding():
    api_key = os.getenv("GOOGLE_API_KEY")
    model = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
    print(f"Testing Gemini Embedding API")
    print(f"Model: {model}")
    print(f"API Key present: {bool(api_key)}")
    
    client = genai.Client(api_key=api_key)
    try:
        print("Sending request...")
        response = client.models.embed_content(
            model=model,
            contents="Hola mundo",
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY"
            )
        )
        print("✅ SUCCESS!")
        print(f"Embedding length: {len(response.embeddings[0].values)}")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_embedding()
