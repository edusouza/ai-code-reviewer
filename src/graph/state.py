from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
from src.models.events import PREvent, ReviewComment


class ChunkInfo(TypedDict):
    """Information about a code chunk."""
    file_path: str
    start_line: int
    end_line: int
    content: str
    language: str


class Suggestion(TypedDict):
    """A single suggestion from an agent."""
    file_path: str
    line_number: int
    message: str
    severity: str  # error, warning, suggestion, note
    suggestion: Optional[str]
    agent_type: str
    confidence: float
    category: str


class ReviewConfig(TypedDict):
    """Review configuration."""
    max_suggestions: int
    severity_threshold: str
    enable_agents: Dict[str, bool]
    custom_rules: Dict[str, Any]


class ReviewMetadata(TypedDict):
    """Review metadata and tracking."""
    review_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    current_step: str
    agent_results: Dict[str, Any]
    error_count: int


class ReviewState(TypedDict):
    """Complete state for the review workflow."""
    # Input data
    pr_event: PREvent
    
    # Configuration
    config: ReviewConfig
    
    # PR content
    pr_diff: str
    agents_md: Optional[str]
    
    # Processing data
    chunks: List[ChunkInfo]
    current_chunk_index: int
    
    # Agent outputs
    suggestions: List[Suggestion]
    raw_agent_outputs: Dict[str, List[Suggestion]]
    
    # Validation
    validated_suggestions: List[Suggestion]
    rejected_suggestions: List[Suggestion]
    
    # Final output
    comments: List[ReviewComment]
    summary: str
    passed: bool
    
    # Metadata
    metadata: ReviewMetadata
    
    # Error handling
    error: Optional[str]
    should_stop: bool
