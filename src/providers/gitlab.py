import hashlib
import hmac
from typing import Any

import httpx

from models.events import PRAction, PREvent, ReviewComment
from providers.base import ProviderAdapter


class GitLabAdapter(ProviderAdapter):
    """GitLab provider adapter for handling webhooks and API interactions."""

    API_BASE = "https://gitlab.com/api/v4"

    def __init__(self, webhook_secret: str, token: str | None = None):
        super().__init__(webhook_secret, token)

    def get_event_type(self, headers: dict[str, str]) -> str | None:
        """Extract GitLab event type from X-Gitlab-Event header."""
        return headers.get("x-gitlab-event")

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitLab X-Gitlab-Token or X-Gitlab-Signature."""
        if not self.webhook_secret:
            return True

        # GitLab uses a simple token comparison or HMAC
        if signature == self.webhook_secret:
            return True

        # Some GitLab versions use HMAC-SHA256
        expected = hmac.new(self.webhook_secret.encode(), payload, hashlib.sha256).hexdigest()

        return hmac.compare_digest(signature, expected)

    def parse_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> PREvent | None:
        """Parse GitLab merge request webhook event."""
        event_type = self.get_event_type(headers)

        if event_type != "Merge Request Hook":
            return None

        object_kind = payload.get("object_kind")
        if object_kind != "merge_request":
            return None

        action_map = {
            "open": PRAction.OPENED,
            "reopen": PRAction.REOPENED,
            "update": PRAction.SYNCHRONIZE,
            "close": PRAction.CLOSED,
            "merge": PRAction.MERGED,
        }

        attrs = payload.get("object_attributes", {})
        action_str = attrs.get("action", "")

        if action_str not in action_map:
            return None

        project = payload.get("project", {})

        return PREvent(
            provider="gitlab",
            repo_owner=project.get("namespace", ""),
            repo_name=project.get("name", ""),
            pr_number=attrs.get("iid", 0),
            action=action_map[action_str],
            branch=attrs.get("source_branch", ""),
            target_branch=attrs.get("target_branch", ""),
            commit_sha=attrs.get("last_commit", {}).get("id", ""),
            pr_title=attrs.get("title", ""),
            pr_body=attrs.get("description"),
            author=attrs.get("author_id", ""),
            url=attrs.get("url"),
            raw_payload=payload,
        )

    async def fetch_pr(self, event: PREvent) -> dict[str, Any]:
        """Fetch MR diff from GitLab API."""
        headers = {"PRIVATE-TOKEN": self.api_token} if self.api_token else {}

        project_id = f"{event.repo_owner}/{event.repo_name}"
        url = f"{self.API_BASE}/projects/{project_id.replace('/', '%2F')}/merge_requests/{event.pr_number}/diffs"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            diffs = response.json()
            return {
                "diff": "\n".join([d.get("diff", "") for d in diffs]),
                "files": diffs,
            }

    async def post_comment(
        self, event: PREvent, comments: list[ReviewComment], summary: str = ""
    ) -> bool:
        """Post review comments to GitLab MR."""
        if not self.api_token:
            raise ValueError("GitLab token required to post comments")

        headers = {"PRIVATE-TOKEN": self.api_token}

        project_id = f"{event.repo_owner}/{event.repo_name}"
        base_url = f"{self.API_BASE}/projects/{project_id.replace('/', '%2F')}/merge_requests/{event.pr_number}"

        async with httpx.AsyncClient() as client:
            # Post summary as main comment
            if summary:
                summary_url = f"{base_url}/notes"
                await client.post(summary_url, headers=headers, json={"body": summary})

            # Post individual line comments
            for comment in comments:
                comment_url = f"{base_url}/discussions"
                body = f"**{comment.severity.upper()}**: {comment.message}"
                if comment.suggestion:
                    body += f"\n\nSuggestion:\n```\n{comment.suggestion}\n```"

                await client.post(
                    comment_url,
                    headers=headers,
                    json={
                        "body": body,
                        "position": {
                            "base_sha": event.commit_sha,
                            "head_sha": event.commit_sha,
                            "start_sha": event.commit_sha,
                            "position_type": "text",
                            "new_path": comment.file_path,
                            "new_line": comment.line_number,
                        },
                    },
                )

            return True
