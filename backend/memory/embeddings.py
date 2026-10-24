"""Embedding service — placeholder for future semantic search."""
import logging
from typing import List

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Placeholder for semantic search via embeddings. Future enhancement."""

    async def embed_text(self, text: str) -> List[float]:
        logger.debug("EmbeddingService.embed_text called — not yet implemented")
        return []

    async def search_similar(self, query_embedding: List[float], top_k: int = 5) -> List[dict]:
        logger.debug("EmbeddingService.search_similar called — not yet implemented")
        return []
