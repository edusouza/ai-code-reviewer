"""Vertex AI Vector Search client for storing and retrieving code patterns."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from config.settings import settings

if TYPE_CHECKING:
    from google.cloud.aiplatform.matching_engine import (
        MatchingEngineIndex,
        MatchingEngineIndexEndpoint,
    )
    from vertexai.language_models import TextEmbeddingModel

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """A document stored in the vector database."""

    id: str
    content: str
    embedding: list[float] | None
    metadata: dict[str, Any]
    score: float | None = None


class VertexVectorStore:
    """Client for Vertex AI Vector Search."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str = "us-central1",
        index_id: str | None = None,
        endpoint_id: str | None = None,
        embedding_model: str = "textembedding-gecko@003",
    ):
        """
        Initialize Vertex AI Vector Search client.

        Args:
            project_id: GCP project ID
            location: GCP location
            index_id: Vector search index ID
            endpoint_id: Vector search endpoint ID
            embedding_model: Model to use for embeddings
        """
        self.project_id = project_id or settings.project_id
        self.location = location
        self.index_id = index_id
        self.endpoint_id = endpoint_id
        self.embedding_model = embedding_model

        self._index_client: MatchingEngineIndex | None = None
        self._endpoint_client: MatchingEngineIndexEndpoint | None = None
        self._embedding_client: TextEmbeddingModel | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize clients lazily."""
        if self._initialized:
            return

        try:
            from google.cloud.aiplatform import init as aiplatform_init
            from vertexai.language_models import TextEmbeddingModel

            aiplatform_init(project=self.project_id, location=self.location)

            # Initialize embedding model
            self._embedding_client = TextEmbeddingModel.from_pretrained(self.embedding_model)

            # Initialize vector search clients if IDs are provided
            if self.index_id:
                from google.cloud.aiplatform.matching_engine import (
                    MatchingEngineIndex,
                    MatchingEngineIndexEndpoint,
                )

                self._index_client = MatchingEngineIndex(index_name=self.index_id)

                if self.endpoint_id:
                    self._endpoint_client = MatchingEngineIndexEndpoint(
                        index_endpoint_name=self.endpoint_id
                    )

            self._initialized = True
            logger.info("Vertex AI Vector Search client initialized")

        except ImportError as e:
            logger.warning(f"Required packages not installed: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize Vector Search: {e}")
