"""Feedback webhook handler for receiving emoji reactions and comments."""

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["feedback"])


class FeedbackWebhookHandler:
    """Handler for feedback webhook events from providers."""

    def __init__(self):
        self.webhook_secret = getattr(settings, "feedback_webhook_secret", "")

    def verify_signature(self, raw_body: bytes, signature: str, provider: str) -> bool:
        """
        Verify webhook signature.

        Args:
            raw_body: Raw request body
            signature: Signature from header
            provider: Provider name (github, gitlab, bitbucket)

        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            logger.warning("No webhook secret configured, skipping verification")
            return True

        try:
            if provider == "github":
                return self._verify_github_signature(raw_body, signature)
            elif provider == "gitlab":
                return self._verify_gitlab_signature(raw_body, signature)
            elif provider == "bitbucket":
                return self._verify_bitbucket_signature(raw_body, signature)
            else:
                logger.warning(f"Unknown provider for signature verification: {provider}")
                return False

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    def _verify_github_signature(self, raw_body: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature."""
        if not signature.startswith("sha256="):
            return False

        expected = hmac.new(self.webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()

        return hmac.compare_digest(f"sha256={expected}", signature)

    def _verify_gitlab_signature(self, raw_body: bytes, signature: str) -> bool:
        """Verify GitLab webhook signature."""
        expected = hmac.new(self.webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()

        return hmac.compare_digest(expected, signature)

    def _verify_bitbucket_signature(self, raw_body: bytes, signature: str) -> bool:
        """Verify Bitbucket webhook signature."""
        # Bitbucket uses JWT tokens or basic auth
        # For simplicity, we'll check if the secret matches
        return signature == self.webhook_secret

    def parse_github_feedback(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parse GitHub feedback event.

        Args:
            payload: Webhook payload

        Returns:
            Parsed feedback data or None
        """
        event_type = payload.get("action", "")

        # Handle PR review comment reactions
        if "reaction" in payload:
            reaction = payload.get("reaction", {})
            comment = payload.get("comment", {})

            return {
                "provider": "github",
                "event_type": "comment_reaction",
                "emoji": reaction.get("content", ""),
                "user": reaction.get("user", {}).get("login", ""),
                "comment_id": str(comment.get("id", "")),
                "comment_body": comment.get("body", ""),
                "file_path": comment.get("path", ""),
                "line_number": comment.get("line", 0),
                "repo_owner": payload.get("repository", {}).get("owner", {}).get("login", ""),
                "repo_name": payload.get("repository", {}).get("name", ""),
                "pr_number": payload.get("pull_request", {}).get("number", 0),
                "raw_payload": payload,
            }

        # Handle PR review submitted
        if event_type == "submitted":
            review = payload.get("review", {})

            # Check for emoji reactions in review body
            body = review.get("body", "")
            emojis = self._extract_emojis(body)

            if emojis:
                return {
                    "provider": "github",
                    "event_type": "review_reaction",
                    "emojis": emojis,
                    "user": review.get("user", {}).get("login", ""),
                    "review_state": review.get("state", ""),
                    "review_body": body,
                    "repo_owner": payload.get("repository", {}).get("owner", {}).get("login", ""),
                    "repo_name": payload.get("repository", {}).get("name", ""),
                    "pr_number": payload.get("pull_request", {}).get("number", 0),
                    "raw_payload": payload,
                }

        # Handle issue comment (general PR comments)
        if event_type in ["created", "edited"] and "issue" in payload:
            comment = payload.get("comment", {})
            body = comment.get("body", "")
            emojis = self._extract_emojis(body)

            if emojis:
                return {
                    "provider": "github",
                    "event_type": "pr_comment",
                    "emojis": emojis,
                    "user": comment.get("user", {}).get("login", ""),
                    "comment_body": body,
                    "repo_owner": payload.get("repository", {}).get("owner", {}).get("login", ""),
                    "repo_name": payload.get("repository", {}).get("name", ""),
                    "pr_number": payload.get("issue", {}).get("number", 0),
                    "raw_payload": payload,
                }

        return None

    def parse_gitlab_feedback(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parse GitLab feedback event.

        Args:
            payload: Webhook payload

        Returns:
            Parsed feedback data or None
        """
        event_type = payload.get("object_kind", "")

        # Handle note (comment) webhooks
        if event_type == "note":
            note = payload.get("object_attributes", {})
            noteable_type = note.get("noteable_type", "")

            # Only process merge request notes
            if noteable_type == "MergeRequest":
                body = note.get("note", "")
                emojis = self._extract_emojis(body)

                if emojis:
                    return {
                        "provider": "gitlab",
                        "event_type": "mr_note",
                        "emojis": emojis,
                        "user": payload.get("user", {}).get("username", ""),
                        "note_body": body,
                        "repo_path": payload.get("project", {}).get("path_with_namespace", ""),
                        "pr_number": note.get("noteable_iid", 0),
                        "raw_payload": payload,
                    }

        # Handle emoji award webhooks
        if event_type == "emoji":
            award = payload.get("object_attributes", {})

            return {
                "provider": "gitlab",
                "event_type": "emoji_award",
                "emoji": award.get("name", ""),
                "user": payload.get("user", {}).get("username", ""),
                "awardable_type": award.get("awardable_type", ""),
                "repo_path": payload.get("project", {}).get("path_with_namespace", ""),
                "raw_payload": payload,
            }

        return None

    def parse_bitbucket_feedback(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parse Bitbucket feedback event.

        Args:
            payload: Webhook payload

        Returns:
            Parsed feedback data or None
        """
        event_type = payload.get("event", "")

        # Handle pull request comment created
        if event_type == "pullrequest:comment_created":
            comment = payload.get("comment", {})
            body = comment.get("content", {}).get("raw", "")
            emojis = self._extract_emojis(body)

            if emojis:
                pr = payload.get("pullrequest", {})

                return {
                    "provider": "bitbucket",
                    "event_type": "pr_comment",
                    "emojis": emojis,
                    "user": payload.get("actor", {}).get("username", ""),
                    "comment_body": body,
                    "repo_owner": payload.get("repository", {})
                    .get("owner", {})
                    .get("username", ""),
                    "repo_name": payload.get("repository", {}).get("name", ""),
                    "pr_number": pr.get("id", 0),
                    "raw_payload": payload,
                }

        return None

    def _extract_emojis(self, text: str) -> list[str]:
        """
        Extract emojis from text.

        Args:
            text: Text to search

        Returns:
            List of found emojis
        """
        import re

        # Unicode emoji pattern
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f1e0-\U0001f1ff"  # flags (iOS)
            "\U00002702-\U000027b0"
            "\U000024c2-\U0001f251"
            "]+",
            flags=re.UNICODE,
        )

        # Also match GitHub/GitLab emoji shortcodes
        shortcode_pattern = re.compile(r":(\w+):")

        emojis = emoji_pattern.findall(text)
        shortcodes = shortcode_pattern.findall(text)

        # Convert shortcodes to unicode if possible
        emoji_map = {
            "+1": "👍",
            "-1": "👎",
            "thumbsup": "👍",
            "thumbsdown": "👎",
            "heart": "❤️",
            "laugh": "😄",
            "confused": "😕",
            "tada": "🎉",
            "rocket": "🚀",
            "eyes": "👀",
        }

        for shortcode in shortcodes:
            if shortcode in emoji_map:
                emojis.append(emoji_map[shortcode])

        return emojis


# Initialize handler
feedback_handler = FeedbackWebhookHandler()


async def get_raw_body(request: Request) -> bytes:
    """Extract raw request body for signature verification."""
    return await request.body()


@router.post(
    "/feedback/github",
    status_code=status.HTTP_202_ACCEPTED,
    summary="GitHub feedback webhook",
    description="Receive feedback from GitHub reactions and comments",
)
async def github_feedback_webhook(request: Request, raw_body: bytes = Depends(get_raw_body)):
    """Handle GitHub feedback webhooks."""
    try:
        payload = await request.json()
        headers = dict(request.headers)

        # Verify signature
        signature = headers.get("x-hub-signature-256", "")
        if not feedback_handler.verify_signature(raw_body, signature, "github"):
            logger.warning("Invalid GitHub feedback webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature"
            )

        # Parse feedback
        feedback = feedback_handler.parse_github_feedback(payload)

        if feedback is None:
            logger.debug("No feedback found in GitHub event")
            return {"status": "ignored", "message": "No feedback data"}

        logger.info(
            f"Received GitHub feedback: {feedback.get('event_type')} from {feedback.get('user')}"
        )

        # TODO: Process feedback through feedback processor
        # await process_feedback(feedback)

        return {"status": "accepted", "feedback_type": feedback.get("event_type")}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing GitHub feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
        ) from e


@router.post(
    "/feedback/gitlab",
    status_code=status.HTTP_202_ACCEPTED,
    summary="GitLab feedback webhook",
    description="Receive feedback from GitLab emoji awards and notes",
)
async def gitlab_feedback_webhook(request: Request, raw_body: bytes = Depends(get_raw_body)):
    """Handle GitLab feedback webhooks."""
    try:
        payload = await request.json()
        headers = dict(request.headers)

        # Verify signature
        signature = headers.get("x-gitlab-token", "")
        if not feedback_handler.verify_signature(raw_body, signature, "gitlab"):
            logger.warning("Invalid GitLab feedback webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature"
            )

        # Parse feedback
        feedback = feedback_handler.parse_gitlab_feedback(payload)

        if feedback is None:
            logger.debug("No feedback found in GitLab event")
            return {"status": "ignored", "message": "No feedback data"}

        logger.info(
            f"Received GitLab feedback: {feedback.get('event_type')} from {feedback.get('user')}"
        )

        return {"status": "accepted", "feedback_type": feedback.get("event_type")}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing GitLab feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
        ) from e


@router.post(
    "/feedback/bitbucket",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Bitbucket feedback webhook",
    description="Receive feedback from Bitbucket pull request comments",
)
async def bitbucket_feedback_webhook(request: Request, raw_body: bytes = Depends(get_raw_body)):
    """Handle Bitbucket feedback webhooks."""
    try:
        payload = await request.json()
        headers = dict(request.headers)

        # Verify signature
        signature = headers.get("x-hook-uuid", "")
        if not feedback_handler.verify_signature(raw_body, signature, "bitbucket"):
            logger.warning("Invalid Bitbucket feedback webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature"
            )

        # Parse feedback
        feedback = feedback_handler.parse_bitbucket_feedback(payload)

        if feedback is None:
            logger.debug("No feedback found in Bitbucket event")
            return {"status": "ignored", "message": "No feedback data"}

        logger.info(
            f"Received Bitbucket feedback: {feedback.get('event_type')} from {feedback.get('user')}"
        )

        return {"status": "accepted", "feedback_type": feedback.get("event_type")}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Bitbucket feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
        ) from e
