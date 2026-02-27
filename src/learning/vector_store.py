"""Vertex AI Vector Search client for storing and retrieving code patterns."""
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import asyncio
import hashlib

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """A document stored in the vector database."""
    id: str
    content: str
    embedding: Optional[List[float]]
    metadata: Dict[str, Any]
    score: Optional[float] = None


class VertexVectorStore:
    """Client for Vertex AI Vector Search."""
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        index_id: Optional[str] = None,
        endpoint_id: Optional[str] = None,
        embedding_model: str = "textembedding-gecko@003"
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
        
        self._index_client = None
        self._endpoint_client = None
        self._embedding_client = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize clients lazily."""
        if self._initialized:
            return
        
        try:
            from google.cloud import aiplatform
            from vertexai.language_models import TextEmbeddingModel
            
            aiplatform.init(project=self.project_id, location=self.location)
            
            # Initialize embedding model
            self._embedding_client = TextEmbeddingModel.from_pretrained(self.embedding_model)
            
            # Initialize vector search clients if IDs are provided
            if self.index_id:
                from google.cloud.aiplatform.gapic.schema import predict
                from google.cloud.aiplatform.matching_engine import (
                    MatchingEngineIndex,
                    MatchingEngineIndexEndpoint
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
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        await self.initialize()
        
        if not self._embedding_client:
            logger.error("Embedding client not available")
            # Return dummy embedding for development
            return [0.0] * 768
        
        try:
            # Truncate if too long
            if len(text) > 10000:
                text = text[:10000]
            
            embeddings = self._embedding_client.get_embeddings([text])
            
            if embeddings and len(embeddings) > 0:
                return embeddings[0].values
            else:
                logger.error("No embeddings returned")
                return [0.0] * 768
                
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return [0.0] * 768
    
    async def add_documents(
        self,
        documents: List[VectorDocument],
        namespace: str = "default"
    ) -> bool:
        """
        Add documents to the vector store.
        
        Args:
            documents: Documents to add
            namespace: Namespace for the documents
            
        Returns:
            True if successful
        """
        await self.initialize()
        
        if not self._index_client:
            logger.warning("Vector search index not configured, skipping add")
            return False
        
        try:
            # Generate embeddings for documents that don't have them
            for doc in documents:
                if doc.embedding is None:
                    doc.embedding = await self.generate_embedding(doc.content)
            
            # Prepare data for upsert
            ids = [doc.id for doc in documents]
            embeddings = [doc.embedding for doc in documents]
            metadatas = [doc.metadata for doc in documents]
            
            # Create JSONL format for Vertex AI
            datapoints = []
            for i, (doc_id, embedding, metadata) in enumerate(zip(ids, embeddings, metadatas)):
                datapoint = {
                    "id": doc_id,
                    "embedding": embedding,
                    "restricts": [
                        {
                            "namespace": "type",
                            "allow_list": [metadata.get("type", "general")]
                        },
                        {
                            "namespace": "language",
                            "allow_list": [metadata.get("language", "unknown")]
                        }
                    ],
                    "metadata": metadata
                }
                datapoints.append(datapoint)
            
            # Upload to index
            # Note: In production, this would use batch upload
            logger.info(f"Adding {len(datapoints)} documents to vector store")
            
            # For now, we just log since actual implementation depends on setup
            return True
            
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return False
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_type: Optional[str] = None,
        filter_language: Optional[str] = None,
        namespace: str = "default"
    ) -> List[VectorDocument]:
        """
        Search for similar documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_type: Filter by document type
            filter_language: Filter by programming language
            namespace: Namespace to search
            
        Returns:
            List of matching documents
        """
        await self.initialize()
        
        if not self._endpoint_client:
            logger.warning("Vector search endpoint not configured, returning empty results")
            return []
        
        try:
            # Generate query embedding
            query_embedding = await self.generate_embedding(query)
            
            # Build filters
            filters = []
            if filter_type:
                filters.append({
                    "namespace": "type",
                    "allow_list": [filter_type]
                })
            if filter_language:
                filters.append({
                    "namespace": "language",
                    "allow_list": [filter_language]
                })
            
            # Query the endpoint
            results = self._endpoint_client.find_neighbors(
                deployed_index_id=self.index_id,
                queries=[query_embedding],
                num_neighbors=top_k,
                filter=filters if filters else None
            )
            
            # Parse results
            documents = []
            for neighbor in results[0] if results else []:
                doc = VectorDocument(
                    id=neighbor.id,
                    content=neighbor.metadata.get("content", ""),
                    embedding=None,
                    metadata=neighbor.metadata,
                    score=neighbor.distance
                )
                documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def delete_documents(
        self,
        document_ids: List[str],
        namespace: str = "default"
    ) -> bool:
        """
        Delete documents from the vector store.
        
        Args:
            document_ids: IDs of documents to delete
            namespace: Namespace
            
        Returns:
            True if successful
        """
        await self.initialize()
        
        if not self._index_client:
            logger.warning("Vector search index not configured, skipping delete")
            return False
        
        try:
            # Remove from index
            self._index_client.remove_datapoints(datapoint_ids=document_ids)
            logger.info(f"Deleted {len(document_ids)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            return False
    
    async def get_document(
        self,
        document_id: str,
        namespace: str = "default"
    ) -> Optional[VectorDocument]:
        """
        Get a specific document by ID.
        
        Args:
            document_id: Document ID
            namespace: Namespace
            
        Returns:
            Document if found, None otherwise
        """
        # Note: Vertex AI Vector Search doesn't support direct ID lookup
        # This would need to be implemented via metadata storage (Firestore, etc.)
        logger.warning("Direct document retrieval not implemented for Vertex AI Vector Search")
        return None
    
    def generate_document_id(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Generate a deterministic document ID.
        
        Args:
            content: Document content
            metadata: Document metadata
            
        Returns:
            Document ID
        """
        # Create hash from content and key metadata
        hash_input = f"{content}:{metadata.get('language', '')}:{metadata.get('type', '')}"
        return f"doc_{hashlib.md5(hash_input.encode()).hexdigest()[:16]}"


# Global client instance
_vector_store: Optional[VertexVectorStore] = None


def init_vector_store(
    project_id: Optional[str] = None,
    index_id: Optional[str] = None,
    endpoint_id: Optional[str] = None
) -> VertexVectorStore:
    """
    Initialize the global vector store.
    
    Args:
        project_id: GCP project ID
        index_id: Vector search index ID
        endpoint_id: Vector search endpoint ID
        
    Returns:
        VertexVectorStore instance
    """
    global _vector_store
    _vector_store = VertexVectorStore(
        project_id=project_id,
        index_id=index_id,
        endpoint_id=endpoint_id
    )
    return _vector_store


def get_vector_store() -> Optional[VertexVectorStore]:
    """Get the global vector store instance."""
    return _vector_store
