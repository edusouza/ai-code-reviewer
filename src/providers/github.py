import hashlib
import hmac
from typing import Any

import httpx

from models.events import PRAction, PREvent, ReviewComment
from providers.base import ProviderAdapter


class GitHubAdapter(ProviderAdapter):
    """GitHub provider adapter for handling webhooks and API interactions."""

    API_BASE = "https://api.github.com"

    # Constructor inherited from base class

    def get_event_type(self, headers: dict[str, str]) -> str | None:
        """Extract GitHub event type from X-GitHub-Event header."""
        return headers.get("x-github-event")

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub HMAC-SHA256 signature."""
        if not self.webhook_secret:
            # In development, skip signature verification
            return True

        if not signature.startswith("sha256="):
            return False

        expected = hmac.new(self.webhook_secret.encode(), payload, hashlib.sha256).hexdigest()

        return hmac.compare_digest(f"sha256={expected}", signature)

    def parse_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> PREvent | None:
        """Parse GitHub pull request webhook event."""
        event_type = self.get_event_type(headers)

        if event_type != "pull_request":
            return None

        action_map = {
            "opened": PRAction.OPENED,
            "synchronize": PRAction.SYNCHRONIZE,
            "reopened": PRAction.REOPENED,
            "closed": PRAction.CLOSED,
            "edited": PRAction.EDITED,
        }

        action_str = payload.get("action", "")
        if action_str not in action_map:
            return None

        pr_data = payload.get("pull_request", {})
        repo_data = payload.get("repository", {})

        # Handle merged state
        action = action_map[action_str]
        if action == PRAction.CLOSED and pr_data.get("merged", False):
            action = PRAction.MERGED

        return PREvent(
            provider="github",
            repo_owner=repo_data.get("owner", {}).get("login", ""),
            repo_name=repo_data.get("name", ""),
            pr_number=pr_data.get("number", 0),
            action=action,
            branch=pr_data.get("head", {}).get("ref", ""),
            target_branch=pr_data.get("base", {}).get("ref", ""),
            commit_sha=pr_data.get("head", {}).get("sha", ""),
            pr_title=pr_data.get("title", ""),
            pr_body=pr_data.get("body"),
            author=pr_data.get("user", {}).get("login", ""),
            url=pr_data.get("html_url"),
            raw_payload=payload,
        )

    async def fetch_pr(self, event: PREvent) -> dict[str, Any]:
        """Fetch PR diff from GitHub API."""
        headers = (
            {
                "Accept": "application/vnd.github.v3.diff",
                "Authorization": f"Bearer {self.api_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if self.api_token
            else {"Accept": "application/vnd.github.v3.diff"}
        )

        url = f"{self.API_BASE}/repos/{event.repo_owner}/{event.repo_name}/pulls/{event.pr_number}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            return {
                "diff": response.text,
                "files": [],  # Could fetch files endpoint separately
            }

    async def post_comment(
        self, event: PREvent, comments: list[ReviewComment], summary: str = ""
    ) -> bool:
        """Post review comments to GitHub PR."""
        if not self.api_token:
            raise ValueError("GitHub token required to post comments")

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # Create review with comments
        url = f"{self.API_BASE}/repos/{event.repo_owner}/{event.repo_name}/pulls/{event.pr_number}/reviews"

        review_data = {
            "body": summary or "AI Code Review Results",
            "event": "COMMENT",
            "comments": [
                {
                    "path": comment.file_path,
                    "line": comment.line_number,
                    "body": f"**{comment.severity.upper()}**: {comment.message}",
                    "suggestion": comment.suggestion,
                }
                for comment in comments
            ],
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=review_data)
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                # Log error details for debugging
                error_body = e.response.text if hasattr(e.response, "text") else str(e)
                raise ValueError(
                    f"Failed to post GitHub review: {e.response.status_code} - {error_body}"
                )
