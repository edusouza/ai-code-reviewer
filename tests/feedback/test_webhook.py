"""Tests for feedback webhook handler module."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from feedback.webhook import FeedbackWebhookHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = "test-secret-key"


def _github_signature(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Compute a valid GitHub SHA256 signature."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _gitlab_signature(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Compute a valid GitLab HMAC signature."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestFeedbackWebhookHandlerInit:
    """Tests for FeedbackWebhookHandler.__init__."""

    def test_default_initialization(self):
        with patch("feedback.webhook.settings", Mock(feedback_webhook_secret="my-secret")):
            handler = FeedbackWebhookHandler()
        assert handler.webhook_secret == "my-secret"

    def test_missing_attribute_on_settings(self):
        """If settings lacks the attribute, default to empty string."""
        mock_settings = Mock(spec=[])  # no attributes
        with patch("feedback.webhook.settings", mock_settings):
            handler = FeedbackWebhookHandler()
        assert handler.webhook_secret == ""


# ---------------------------------------------------------------------------
# verify_signature
# ---------------------------------------------------------------------------


class TestVerifySignature:
    """Tests for webhook signature verification."""

    def _handler(self, secret=WEBHOOK_SECRET):
        handler = FeedbackWebhookHandler.__new__(FeedbackWebhookHandler)
        handler.webhook_secret = secret
        return handler

    def test_no_secret_returns_true(self):
        """When no secret is configured, verification is skipped."""
        handler = self._handler(secret="")
        assert handler.verify_signature(b"body", "anysig", "github") is True

    # -- GitHub --
    def test_github_valid_signature(self):
        handler = self._handler()
        body = b'{"action": "created"}'
        sig = _github_signature(body)
        assert handler.verify_signature(body, sig, "github") is True

    def test_github_invalid_signature(self):
        handler = self._handler()
        body = b'{"action": "created"}'
        assert handler.verify_signature(body, "sha256=invalid", "github") is False

    def test_github_missing_prefix(self):
        handler = self._handler()
        body = b'{"action": "created"}'
        # Signature without sha256= prefix
        digest = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        assert handler.verify_signature(body, digest, "github") is False

    # -- GitLab --
    def test_gitlab_valid_signature(self):
        handler = self._handler()
        body = b'{"object_kind": "note"}'
        sig = _gitlab_signature(body)
        assert handler.verify_signature(body, sig, "gitlab") is True

    def test_gitlab_invalid_signature(self):
        handler = self._handler()
        body = b'{"object_kind": "note"}'
        assert handler.verify_signature(body, "invalid-signature", "gitlab") is False

    # -- Bitbucket --
    def test_bitbucket_valid_signature(self):
        handler = self._handler()
        assert handler.verify_signature(b"body", WEBHOOK_SECRET, "bitbucket") is True

    def test_bitbucket_invalid_signature(self):
        handler = self._handler()
        assert handler.verify_signature(b"body", "wrong-secret", "bitbucket") is False

    # -- Unknown provider --
    def test_unknown_provider(self):
        handler = self._handler()
        assert handler.verify_signature(b"body", "anysig", "unknown-vcs") is False

    # -- Exception during verification --
    def test_exception_returns_false(self):
        handler = self._handler()
        # Force an exception by passing non-bytes body
        with patch.object(handler, "_verify_github_signature", side_effect=RuntimeError("boom")):
            assert handler.verify_signature(b"body", "sig", "github") is False


# ---------------------------------------------------------------------------
# _extract_emojis
# ---------------------------------------------------------------------------


class TestExtractEmojis:
    """Tests for emoji extraction from text."""

    def _handler(self):
        handler = FeedbackWebhookHandler.__new__(FeedbackWebhookHandler)
        handler.webhook_secret = ""
        return handler

    def test_unicode_emojis(self):
        handler = self._handler()
        result = handler._extract_emojis("Great job! 👍🎉")
        assert "👍" in result or any("👍" in e for e in result)

    def test_shortcode_thumbsup(self):
        handler = self._handler()
        # :+1: does not match \w+ regex, but :thumbsup: does
        result = handler._extract_emojis("This is :thumbsup: awesome")
        assert "👍" in result

    def test_shortcode_thumbsdown(self):
        handler = self._handler()
        # :-1: does not match \w+ regex, but :thumbsdown: does
        result = handler._extract_emojis("Not great :thumbsdown:")
        assert "👎" in result

    def test_shortcode_plus1_not_matched_by_regex(self):
        r"""The regex :(\w+): cannot match :+1: because + is not a word char."""
        handler = self._handler()
        result = handler._extract_emojis(":+1:")
        # +1 is not captured by \w+, so no emoji is extracted
        assert "👍" not in result

    def test_shortcode_heart(self):
        handler = self._handler()
        result = handler._extract_emojis(":heart:")
        assert "❤️" in result

    def test_shortcode_rocket(self):
        handler = self._handler()
        result = handler._extract_emojis(":rocket: to the moon")
        assert "🚀" in result

    def test_shortcode_eyes(self):
        handler = self._handler()
        result = handler._extract_emojis(":eyes:")
        assert "👀" in result

    def test_shortcode_tada(self):
        handler = self._handler()
        result = handler._extract_emojis(":tada:")
        assert "🎉" in result

    def test_shortcode_confused(self):
        handler = self._handler()
        result = handler._extract_emojis(":confused:")
        assert "😕" in result

    def test_shortcode_laugh(self):
        handler = self._handler()
        result = handler._extract_emojis(":laugh:")
        assert "😄" in result

    def test_unknown_shortcode_ignored(self):
        handler = self._handler()
        result = handler._extract_emojis(":not_a_real_emoji:")
        # Should not map to anything
        assert len(result) == 0

    def test_multiple_shortcodes(self):
        handler = self._handler()
        result = handler._extract_emojis(":thumbsup: and :heart:")
        assert "👍" in result
        assert "❤️" in result

    def test_empty_text(self):
        handler = self._handler()
        result = handler._extract_emojis("")
        assert result == []

    def test_no_emojis_in_text(self):
        handler = self._handler()
        result = handler._extract_emojis("Just plain text without any emojis")
        assert result == []

    def test_mixed_unicode_and_shortcodes(self):
        handler = self._handler()
        result = handler._extract_emojis("👍 and :heart:")
        assert len(result) >= 2


# ---------------------------------------------------------------------------
# parse_github_feedback
# ---------------------------------------------------------------------------


class TestParseGithubFeedback:
    """Tests for parsing GitHub webhook payloads."""

    def _handler(self):
        handler = FeedbackWebhookHandler.__new__(FeedbackWebhookHandler)
        handler.webhook_secret = ""
        return handler

    def test_reaction_event(self):
        handler = self._handler()
        payload = {
            "action": "created",
            "reaction": {
                "content": "+1",
                "user": {"login": "alice"},
            },
            "comment": {
                "id": 123,
                "body": "Nice work!",
                "path": "src/main.py",
                "line": 42,
            },
            "repository": {
                "owner": {"login": "myorg"},
                "name": "myrepo",
            },
            "pull_request": {"number": 7},
        }

        result = handler.parse_github_feedback(payload)

        assert result is not None
        assert result["provider"] == "github"
        assert result["event_type"] == "comment_reaction"
        assert result["emoji"] == "+1"
        assert result["user"] == "alice"
        assert result["comment_id"] == "123"
        assert result["comment_body"] == "Nice work!"
        assert result["file_path"] == "src/main.py"
        assert result["line_number"] == 42
        assert result["repo_owner"] == "myorg"
        assert result["repo_name"] == "myrepo"
        assert result["pr_number"] == 7
        assert result["raw_payload"] is payload

    def test_review_submitted_with_emojis(self):
        handler = self._handler()
        payload = {
            "action": "submitted",
            "review": {
                "body": "Looks great! 👍",
                "user": {"login": "bob"},
                "state": "approved",
            },
            "repository": {
                "owner": {"login": "myorg"},
                "name": "myrepo",
            },
            "pull_request": {"number": 10},
        }

        result = handler.parse_github_feedback(payload)

        assert result is not None
        assert result["provider"] == "github"
        assert result["event_type"] == "review_reaction"
        assert "👍" in result["emojis"]
        assert result["user"] == "bob"
        assert result["review_state"] == "approved"
        assert result["review_body"] == "Looks great! 👍"
        assert result["repo_owner"] == "myorg"
        assert result["repo_name"] == "myrepo"
        assert result["pr_number"] == 10

    def test_review_submitted_without_emojis(self):
        handler = self._handler()
        payload = {
            "action": "submitted",
            "review": {
                "body": "LGTM",
                "user": {"login": "bob"},
                "state": "approved",
            },
            "repository": {
                "owner": {"login": "myorg"},
                "name": "myrepo",
            },
            "pull_request": {"number": 10},
        }

        result = handler.parse_github_feedback(payload)
        assert result is None

    def test_issue_comment_created_with_emojis(self):
        handler = self._handler()
        payload = {
            "action": "created",
            "issue": {"number": 5},
            "comment": {
                "body": "This is confusing :confused:",
                "user": {"login": "carol"},
            },
            "repository": {
                "owner": {"login": "myorg"},
                "name": "myrepo",
            },
        }

        result = handler.parse_github_feedback(payload)

        assert result is not None
        assert result["provider"] == "github"
        assert result["event_type"] == "pr_comment"
        assert "😕" in result["emojis"]
        assert result["user"] == "carol"
        assert result["comment_body"] == "This is confusing :confused:"
        assert result["pr_number"] == 5

    def test_issue_comment_edited_with_emojis(self):
        handler = self._handler()
        payload = {
            "action": "edited",
            "issue": {"number": 5},
            "comment": {
                "body": ":thumbsup: updated",
                "user": {"login": "carol"},
            },
            "repository": {
                "owner": {"login": "myorg"},
                "name": "myrepo",
            },
        }

        result = handler.parse_github_feedback(payload)
        assert result is not None
        assert result["event_type"] == "pr_comment"

    def test_issue_comment_without_emojis(self):
        handler = self._handler()
        payload = {
            "action": "created",
            "issue": {"number": 5},
            "comment": {
                "body": "Just a plain comment",
                "user": {"login": "carol"},
            },
            "repository": {
                "owner": {"login": "myorg"},
                "name": "myrepo",
            },
        }

        result = handler.parse_github_feedback(payload)
        assert result is None

    def test_unrecognized_event(self):
        handler = self._handler()
        payload = {"action": "closed"}
        result = handler.parse_github_feedback(payload)
        assert result is None

    def test_reaction_with_empty_nested_fields(self):
        """Handles missing nested fields gracefully."""
        handler = self._handler()
        payload = {
            "action": "created",
            "reaction": {},
            "comment": {},
            "repository": {},
            "pull_request": {},
        }

        result = handler.parse_github_feedback(payload)
        assert result is not None
        assert result["emoji"] == ""
        assert result["user"] == ""
        assert result["repo_owner"] == ""
        assert result["repo_name"] == ""
        assert result["pr_number"] == 0

    def test_issue_comment_not_triggered_for_deleted(self):
        """The action 'deleted' should not match 'created' or 'edited'."""
        handler = self._handler()
        payload = {
            "action": "deleted",
            "issue": {"number": 5},
            "comment": {
                "body": ":+1: this",
                "user": {"login": "carol"},
            },
            "repository": {
                "owner": {"login": "myorg"},
                "name": "myrepo",
            },
        }
        result = handler.parse_github_feedback(payload)
        assert result is None


# ---------------------------------------------------------------------------
# parse_gitlab_feedback
# ---------------------------------------------------------------------------


class TestParseGitlabFeedback:
    """Tests for parsing GitLab webhook payloads."""

    def _handler(self):
        handler = FeedbackWebhookHandler.__new__(FeedbackWebhookHandler)
        handler.webhook_secret = ""
        return handler

    def test_note_on_merge_request_with_emojis(self):
        handler = self._handler()
        payload = {
            "object_kind": "note",
            "object_attributes": {
                "noteable_type": "MergeRequest",
                "note": "This looks great! :rocket:",
                "noteable_iid": 15,
            },
            "user": {"username": "alice"},
            "project": {"path_with_namespace": "myorg/myrepo"},
        }

        result = handler.parse_gitlab_feedback(payload)

        assert result is not None
        assert result["provider"] == "gitlab"
        assert result["event_type"] == "mr_note"
        assert "🚀" in result["emojis"]
        assert result["user"] == "alice"
        assert result["note_body"] == "This looks great! :rocket:"
        assert result["repo_path"] == "myorg/myrepo"
        assert result["pr_number"] == 15

    def test_note_on_merge_request_without_emojis(self):
        handler = self._handler()
        payload = {
            "object_kind": "note",
            "object_attributes": {
                "noteable_type": "MergeRequest",
                "note": "Plain text comment",
                "noteable_iid": 15,
            },
            "user": {"username": "alice"},
            "project": {"path_with_namespace": "myorg/myrepo"},
        }

        result = handler.parse_gitlab_feedback(payload)
        assert result is None

    def test_note_on_non_merge_request(self):
        """Notes on issues or commits should be ignored."""
        handler = self._handler()
        payload = {
            "object_kind": "note",
            "object_attributes": {
                "noteable_type": "Issue",
                "note": ":+1: great issue",
                "noteable_iid": 15,
            },
            "user": {"username": "alice"},
            "project": {"path_with_namespace": "myorg/myrepo"},
        }

        result = handler.parse_gitlab_feedback(payload)
        assert result is None

    def test_emoji_award_event(self):
        handler = self._handler()
        payload = {
            "object_kind": "emoji",
            "object_attributes": {
                "name": "thumbsup",
                "awardable_type": "MergeRequest",
            },
            "user": {"username": "bob"},
            "project": {"path_with_namespace": "myorg/myrepo"},
        }

        result = handler.parse_gitlab_feedback(payload)

        assert result is not None
        assert result["provider"] == "gitlab"
        assert result["event_type"] == "emoji_award"
        assert result["emoji"] == "thumbsup"
        assert result["user"] == "bob"
        assert result["awardable_type"] == "MergeRequest"
        assert result["repo_path"] == "myorg/myrepo"

    def test_unrecognized_event(self):
        handler = self._handler()
        payload = {"object_kind": "push"}
        result = handler.parse_gitlab_feedback(payload)
        assert result is None

    def test_emoji_award_with_empty_fields(self):
        handler = self._handler()
        payload = {
            "object_kind": "emoji",
            "object_attributes": {},
            "user": {},
            "project": {},
        }

        result = handler.parse_gitlab_feedback(payload)
        assert result is not None
        assert result["emoji"] == ""
        assert result["user"] == ""
        assert result["awardable_type"] == ""
        assert result["repo_path"] == ""


# ---------------------------------------------------------------------------
# parse_bitbucket_feedback
# ---------------------------------------------------------------------------


class TestParseBitbucketFeedback:
    """Tests for parsing Bitbucket webhook payloads."""

    def _handler(self):
        handler = FeedbackWebhookHandler.__new__(FeedbackWebhookHandler)
        handler.webhook_secret = ""
        return handler

    def test_pr_comment_with_emojis(self):
        handler = self._handler()
        payload = {
            "event": "pullrequest:comment_created",
            "comment": {
                "content": {"raw": "Awesome work! :thumbsup:"},
            },
            "pullrequest": {"id": 99},
            "actor": {"username": "dave"},
            "repository": {
                "owner": {"username": "myorg"},
                "name": "myrepo",
            },
        }

        result = handler.parse_bitbucket_feedback(payload)

        assert result is not None
        assert result["provider"] == "bitbucket"
        assert result["event_type"] == "pr_comment"
        assert "👍" in result["emojis"]
        assert result["user"] == "dave"
        assert result["comment_body"] == "Awesome work! :thumbsup:"
        assert result["repo_owner"] == "myorg"
        assert result["repo_name"] == "myrepo"
        assert result["pr_number"] == 99

    def test_pr_comment_without_emojis(self):
        handler = self._handler()
        payload = {
            "event": "pullrequest:comment_created",
            "comment": {
                "content": {"raw": "Just a note"},
            },
            "pullrequest": {"id": 99},
            "actor": {"username": "dave"},
            "repository": {
                "owner": {"username": "myorg"},
                "name": "myrepo",
            },
        }

        result = handler.parse_bitbucket_feedback(payload)
        assert result is None

    def test_unrecognized_event(self):
        handler = self._handler()
        payload = {"event": "repo:push"}
        result = handler.parse_bitbucket_feedback(payload)
        assert result is None

    def test_pr_comment_with_empty_nested_fields(self):
        handler = self._handler()
        payload = {
            "event": "pullrequest:comment_created",
            "comment": {
                "content": {"raw": ":heart:"},
            },
            "pullrequest": {},
            "actor": {},
            "repository": {},
        }

        result = handler.parse_bitbucket_feedback(payload)
        assert result is not None
        assert result["pr_number"] == 0
        assert result["user"] == ""
        assert result["repo_owner"] == ""
        assert result["repo_name"] == ""


# ---------------------------------------------------------------------------
# FastAPI endpoint tests using httpx AsyncClient
# ---------------------------------------------------------------------------


class TestGithubWebhookEndpoint:
    """Tests for the /feedback/github endpoint."""

    @pytest.mark.asyncio
    async def test_valid_reaction_accepted(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        payload = {
            "action": "created",
            "reaction": {
                "content": "+1",
                "user": {"login": "alice"},
            },
            "comment": {"id": 1, "body": "good", "path": "f.py", "line": 1},
            "repository": {"owner": {"login": "org"}, "name": "repo"},
            "pull_request": {"number": 1},
        }
        body = json.dumps(payload).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=True):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/feedback/github",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["feedback_type"] == "comment_reaction"

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        payload = {"action": "created"}
        body = json.dumps(payload).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=False):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/feedback/github",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_no_feedback_returns_ignored(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        payload = {"action": "closed"}
        body = json.dumps(payload).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=True):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/feedback/github",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_internal_error_returns_500(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        payload = {"action": "created"}
        body = json.dumps(payload).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=True):
            with patch.object(
                feedback_handler, "parse_github_feedback", side_effect=RuntimeError("boom")
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post(
                        "/feedback/github",
                        content=body,
                        headers={"Content-Type": "application/json"},
                    )

        assert resp.status_code == 500


class TestGitlabWebhookEndpoint:
    """Tests for the /feedback/gitlab endpoint."""

    @pytest.mark.asyncio
    async def test_valid_emoji_award_accepted(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        payload = {
            "object_kind": "emoji",
            "object_attributes": {"name": "thumbsup", "awardable_type": "MergeRequest"},
            "user": {"username": "bob"},
            "project": {"path_with_namespace": "org/repo"},
        }
        body = json.dumps(payload).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=True):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/feedback/gitlab",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["feedback_type"] == "emoji_award"

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        body = json.dumps({"object_kind": "note"}).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=False):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/feedback/gitlab",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_no_feedback_returns_ignored(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        body = json.dumps({"object_kind": "push"}).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=True):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/feedback/gitlab",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_internal_error_returns_500(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        body = json.dumps({"object_kind": "note"}).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=True):
            with patch.object(
                feedback_handler, "parse_gitlab_feedback", side_effect=RuntimeError("boom")
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post(
                        "/feedback/gitlab",
                        content=body,
                        headers={"Content-Type": "application/json"},
                    )

        assert resp.status_code == 500


class TestBitbucketWebhookEndpoint:
    """Tests for the /feedback/bitbucket endpoint."""

    @pytest.mark.asyncio
    async def test_valid_comment_accepted(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        payload = {
            "event": "pullrequest:comment_created",
            "comment": {"content": {"raw": ":thumbsup: nice"}},
            "pullrequest": {"id": 5},
            "actor": {"username": "dave"},
            "repository": {"owner": {"username": "org"}, "name": "repo"},
        }
        body = json.dumps(payload).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=True):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/feedback/bitbucket",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["feedback_type"] == "pr_comment"

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        body = json.dumps({"event": "pullrequest:comment_created"}).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=False):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/feedback/bitbucket",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_no_feedback_returns_ignored(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        body = json.dumps({"event": "repo:push"}).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=True):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/feedback/bitbucket",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_internal_error_returns_500(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from feedback.webhook import feedback_handler, router

        app = FastAPI()
        app.include_router(router)

        body = json.dumps({"event": "pullrequest:comment_created"}).encode()

        with patch.object(feedback_handler, "verify_signature", return_value=True):
            with patch.object(
                feedback_handler,
                "parse_bitbucket_feedback",
                side_effect=RuntimeError("boom"),
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post(
                        "/feedback/bitbucket",
                        content=body,
                        headers={"Content-Type": "application/json"},
                    )

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# get_raw_body helper
# ---------------------------------------------------------------------------


class TestGetRawBody:
    """Tests for the get_raw_body dependency."""

    @pytest.mark.asyncio
    async def test_returns_request_body(self):
        from feedback.webhook import get_raw_body

        mock_request = AsyncMock()
        mock_request.body.return_value = b"raw bytes"

        result = await get_raw_body(mock_request)
        assert result == b"raw bytes"


# ---------------------------------------------------------------------------
# Module-level handler instance
# ---------------------------------------------------------------------------


class TestModuleLevelHandler:
    """Test the module-level feedback_handler."""

    def test_feedback_handler_is_created(self):
        from feedback.webhook import feedback_handler

        assert isinstance(feedback_handler, FeedbackWebhookHandler)
