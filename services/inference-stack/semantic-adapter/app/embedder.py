import os
import asyncio
import logging
from typing import List
from google import genai
from google.genai import types

logger = logging.getLogger("semantic_adapter.embedder")

class GeminiEmbedder:
    """
    Implementation of the embedding service using Google Gemini (google-genai SDK).
    Follows ETL integration guide exactly: NO output_dimensionality parameter.
    """

    def __init__(self, model: str = None):
        """
        Initialize the Gemini embedder.
        Reads GOOGLE_API_KEY and EMBEDDING_MODEL from environment variables.
        """
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")
        
        self.model = model or os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
        if self.model.startswith("models/"):
            self.model = self.model.replace("models/", "")
        self.client = genai.Client(api_key=self.api_key)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of documents asynchronously.
        Returns 3072-dimensional vectors automatically.
        """
        if not texts:
            return []
            
        try:
            # Per ETL guide: NO output_dimensionality parameter
            # Model returns 3072 dimensions automatically
            response = await asyncio.to_thread(
                self.client.models.embed_content,
                model=self.model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY"  # Same as query for compatibility
                ),
            )
            return [e.values for e in response.embeddings]
        except Exception as e:
            logger.warning("Batch embedding failed, falling back to sequential mode: %s", e)
            results = []
            for text in texts:
                emb = await self.embed_query(text)
                results.append(emb)
            return results

    async def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query asynchronously.
        Returns 3072-dimensional vector automatically.
        """
        response = await asyncio.to_thread(
            self.client.models.embed_content,
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY"  # Per ETL guide
            ),
        )
        return response.embeddings[0].values
