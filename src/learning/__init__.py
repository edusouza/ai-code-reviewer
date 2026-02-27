"""Learning system for code patterns and knowledge retention."""
from learning.vector_store import (
    VectorDocument,
    VertexVectorStore,
    init_vector_store,
    get_vector_store
)
from learning.patterns import (
    PatternType,
    CodePattern,
    PatternExtractor,
    PatternRetriever,
    PatternManager,
    init_pattern_manager,
    get_pattern_manager
)

__all__ = [
    # Vector Store
    'VectorDocument',
    'VertexVectorStore',
    'init_vector_store',
    'get_vector_store',
    # Patterns
    'PatternType',
    'CodePattern',
    'PatternExtractor',
    'PatternRetriever',
    'PatternManager',
    'init_pattern_manager',
    'get_pattern_manager'
]
