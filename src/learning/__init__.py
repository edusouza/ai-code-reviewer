"""Learning system for code patterns and knowledge retention."""

from learning.patterns import (
    CodePattern,
    PatternExtractor,
    PatternManager,
    PatternRetriever,
    PatternType,
    get_pattern_manager,
    init_pattern_manager,
)
from learning.vector_store import (
    VectorDocument,
    VertexVectorStore,
    get_vector_store,
    init_vector_store,
)

__all__ = [
    # Vector Store
    "VectorDocument",
    "VertexVectorStore",
    "init_vector_store",
    "get_vector_store",
    # Patterns
    "PatternType",
    "CodePattern",
    "PatternExtractor",
    "PatternRetriever",
    "PatternManager",
    "init_pattern_manager",
    "get_pattern_manager",
]
