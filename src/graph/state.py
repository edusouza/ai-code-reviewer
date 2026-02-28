from datetime import datetime
from typing import Any, TypedDict

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
    suggestion: str | None
    agent_type: str
    confidence: float
    category: str


class ReviewConfig(TypedDict):
    """Review configuration."""

    max_suggestions: int
    severity_threshold: str
    enable_agents: dict[str, bool]
    custom_rules: dict[str, Any]


class ReviewMetadata(TypedDict):
    """Review metadata and tracking."""

    review_id: str
    started_at: datetime
    completed_at: datetime | None
    current_step: str
    agent_results: dict[str, Any]
    error_count: int


class ReviewState(TypedDict):
    """Complete state for the review workflow."""

    # Input data
    pr_event: PREvent

    # Configuration
    config: ReviewConfig

    # PR content
    pr_diff: str
    agents_md: str | None

    # Processing data
    chunks: list[ChunkInfo]
    current_chunk_index: int

    # Agent outputs
    suggestions: list[Suggestion]
    raw_agent_outputs: dict[str, list[Suggestion]]

    # Validation
    validated_suggestions: list[Suggestion]
    rejected_suggestions: list[Suggestion]

    # Final output
    comments: list[ReviewComment]
    summary: str
    passed: bool

    # Metadata
    metadata: ReviewMetadata

    # Error handling
    error: str | None
    should_stop: bool
