from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PRAction(StrEnum):
    OPENED = "opened"
    SYNCHRONIZE = "synchronize"
    REOPENED = "reopened"
    CLOSED = "closed"
    MERGED = "merged"
    EDITED = "edited"


class PREvent(BaseModel):
    """Common PR event model normalized across all providers."""

    provider: str = Field(..., description="Provider name (github, gitlab, bitbucket)")
    repo_owner: str = Field(..., description="Repository owner/organization")
    repo_name: str = Field(..., description="Repository name")
    pr_number: int = Field(..., description="Pull/Merge request number")
    action: PRAction = Field(..., description="Action performed on PR")
    branch: str = Field(..., description="Branch name")
    target_branch: str = Field(..., description="Target branch for the PR")
    commit_sha: str = Field(..., description="Current commit SHA")
    pr_title: str = Field(default="", description="PR title")
    pr_body: str | None = Field(default=None, description="PR description/body")
    author: str = Field(default="", description="PR author username")
    url: str | None = Field(default=None, description="PR URL")
    raw_payload: dict[str, Any] = Field(
        default_factory=dict, description="Original provider payload"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "github",
                "repo_owner": "myorg",
                "repo_name": "myrepo",
                "pr_number": 42,
                "action": "opened",
                "branch": "feature/new-thing",
                "target_branch": "main",
                "commit_sha": "abc123",
                "pr_title": "Add new feature",
                "pr_body": "This PR adds...",
                "author": "johndoe",
                "url": "https://github.com/myorg/myrepo/pull/42",
            }
        }


class ReviewComment(BaseModel):
    """Represents a single review comment."""

    file_path: str = Field(..., description="File path relative to repo root")
    line_number: int = Field(..., description="Line number in the file")
    message: str = Field(..., description="Comment message")
    severity: str = Field(
        default="suggestion", description="Severity level (error, warning, suggestion, note)"
    )
    suggestion: str | None = Field(default=None, description="Suggested code replacement")

    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "src/main.py",
                "line_number": 42,
                "message": "Consider adding type hints here",
                "severity": "suggestion",
                "suggestion": "def process(data: str) -> int:",
            }
        }


class ReviewResult(BaseModel):
    """Complete review result for a PR."""

    pr_event: PREvent
    summary: str = Field(default="", description="Overall review summary")
    comments: list[ReviewComment] = Field(
        default_factory=list, description="List of review comments"
    )
    passed: bool = Field(default=True, description="Whether the review passed all checks")
    duration_ms: int | None = Field(default=None, description="Review duration in milliseconds")
