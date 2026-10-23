import logging
import os

import httpx
from langchain_core.embeddings import Embeddings

from app.config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL_ID

VOYAGE_EMBEDDINGS_URL = "https://api.voyageai.com/v1/embeddings"

logger = logging.getLogger(__name__)


class VoyageEmbeddings(Embeddings):
    def __init__(self, api_key: str, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        response = httpx.post(
            VOYAGE_EMBEDDINGS_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "input": texts,
                "model": EMBEDDING_MODEL_ID,
                "input_type": input_type,
                "output_dimension": EMBEDDING_DIMENSIONS,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        items = sorted(response.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in items]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]


def get_embeddings() -> Embeddings:
    api_key = os.getenv("VOYAGE_API_KEY")
    if not api_key:
        raise RuntimeError("VOYAGE_API_KEY is not set")
    return VoyageEmbeddings(api_key)


def to_pgvector(vector: list[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


def embed_for_storage(embeddings: Embeddings, text: str) -> str | None:
    """Returns the text's vector in pgvector format, or None if Voyage is unavailable.
    The incident is saved either way; missing vectors can be filled in later."""
    try:
        vector = embeddings.embed_documents([text])[0]
    except httpx.HTTPError:
        logger.warning("Embedding failed, saving without a vector", exc_info=True)
        return None
    return to_pgvector(vector)