from typing import Any

import httpx

from models.events import PRAction, PREvent, ReviewComment
from providers.base import ProviderAdapter


class BitbucketAdapter(ProviderAdapter):
    """Bitbucket provider adapter for handling webhooks and API interactions."""

    API_BASE = "https://api.bitbucket.org/2.0"

    def __init__(
        self,
        webhook_secret: str,
        username: str | None = None,
        app_password: str | None = None,
    ):
        super().__init__(webhook_secret)
        self.username = username
        self.app_password = app_password
        self.auth = (username, app_password) if username and app_password else None

    def get_event_type(self, headers: dict[str, str]) -> str | None:
        """Extract Bitbucket event type from X-Event-Key header."""
        return headers.get("x-event-key")

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Bitbucket webhook signature if secret is configured.

        Note: Bitbucket doesn't always use signatures. The X-Event-Key header
        can be used to verify the webhook source.
        """
        if not self.webhook_secret:
            return True

        # Bitbucket Cloud uses JWT for some webhooks
        # For simplicity, we check if the webhook secret matches the expected value
        return signature == self.webhook_secret

    def parse_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> PREvent | None:
        """Parse Bitbucket pull request webhook event."""
        event_type = self.get_event_type(headers)

        if not event_type or "pullrequest" not in event_type:
            return None

        pr_data = payload.get("pullrequest", {})
        repo_data = pr_data.get("destination", {}).get("repository", {})

        action_map = {
            "pullrequest:created": PRAction.OPENED,
            "pullrequest:updated": PRAction.SYNCHRONIZE,
            "pullrequest:approved": None,  # Skip
            "pullrequest:unapproved": None,  # Skip
            "pullrequest:fulfilled": PRAction.MERGED,
            "pullrequest:rejected": PRAction.CLOSED,
        }

        action = action_map.get(event_type)
        if action is None:
            return None

        # Extract owner from full_name (format: "owner/repo")
        full_name = repo_data.get("full_name", "")
        owner = full_name.split("/")[0] if "/" in full_name else ""

        return PREvent(
            provider="bitbucket",
            repo_owner=owner,
            repo_name=repo_data.get("name", ""),
            pr_number=pr_data.get("id", 0),
            action=action,
            branch=pr_data.get("source", {}).get("branch", {}).get("name", ""),
            target_branch=pr_data.get("destination", {}).get("branch", {}).get("name", ""),
            commit_sha=pr_data.get("source", {}).get("commit", {}).get("hash", ""),
            pr_title=pr_data.get("title", ""),
            pr_body=pr_data.get("description"),
            author=pr_data.get("author", {}).get("username", ""),
            url=pr_data.get("links", {}).get("html", {}).get("href"),
            raw_payload=payload,
        )

    async def fetch_pr(self, event: PREvent) -> dict[str, Any]:
        """Fetch PR diff from Bitbucket API."""
        headers: dict[str, str] = {}

        url = f"{self.API_BASE}/repositories/{event.repo_owner}/{event.repo_name}/pullrequests/{event.pr_number}/diff"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, auth=self.auth)
            response.raise_for_status()

            return {
                "diff": response.text,
                "files": [],
            }

    async def post_comment(
        self, event: PREvent, comments: list[ReviewComment], summary: str = ""
    ) -> bool:
        """Post review comments to Bitbucket PR."""
        if not self.auth:
            raise ValueError("Bitbucket credentials required to post comments")

        url = f"{self.API_BASE}/repositories/{event.repo_owner}/{event.repo_name}/pullrequests/{event.pr_number}/comments"

        async with httpx.AsyncClient() as client:
            # Post summary first
            if summary:
                await client.post(url, json={"content": {"raw": summary}}, auth=self.auth)

            # Post individual comments (Bitbucket inline comments are more complex)
            for comment in comments:
                body = f"**{comment.severity.upper()}**: {comment.message}"
                if comment.suggestion:
                    body += f"\n\nSuggestion: {comment.suggestion}"

                # Note: Bitbucket inline comments require more detailed positioning
                await client.post(url, json={"content": {"raw": body}}, auth=self.auth)

            return True
