"""Tests for GitHub provider adapter."""
import pytest
import hmac
import hashlib
import json
from unittest.mock import Mock, AsyncMock, patch

from providers.github import GitHubAdapter
from models.events import PREvent, PRAction


@pytest.mark.unit
@pytest.mark.provider
class TestGitHubAdapter:
    """Test suite for GitHubAdapter."""
    
    def test_init_with_token(self):
        """Test adapter initialization with token."""
        adapter = GitHubAdapter(webhook_secret="secret", token="github_token")
        assert adapter.webhook_secret == "secret"
        assert adapter.api_token == "github_token"
    
    def test_init_without_token(self):
        """Test adapter initialization without token."""
        adapter = GitHubAdapter(webhook_secret="secret")
        assert adapter.webhook_secret == "secret"
        assert adapter.api_token is None
    
    def test_get_event_type(self, github_headers):
        """Test event type extraction from headers."""
        adapter = GitHubAdapter(webhook_secret="secret")
        
        event_type = adapter.get_event_type(github_headers)
        assert event_type == "pull_request"
    
    def test_get_event_type_missing(self):
        """Test event type extraction with missing header."""
        adapter = GitHubAdapter(webhook_secret="secret")
        
        event_type = adapter.get_event_type({})
        assert event_type is None
    
    def test_verify_signature_valid(self):
        """Test signature verification with valid signature."""
        secret = "mysecret"
        payload = b'{"action": "opened"}'
        
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        signature = f"sha256={expected}"
        
        adapter = GitHubAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, signature) is True
    
    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        secret = "mysecret"
        payload = b'{"action": "opened"}'
        
        adapter = GitHubAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, "sha256=invalid") is False
    
    def test_verify_signature_wrong_format(self):
        """Test signature verification with wrong format."""
        secret = "mysecret"
        payload = b'{"action": "opened"}'
        
        adapter = GitHubAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, "invalid_format") is False
    
    def test_verify_signature_no_secret(self):
        """Test signature verification with no secret (dev mode)."""
        adapter = GitHubAdapter(webhook_secret="")
        assert adapter.verify_signature(b'{"action": "opened"}', "any") is True
    
    def test_parse_webhook_opened(self, sample_github_pr_payload, github_headers):
        """Test parsing pull_request opened event."""
        adapter = GitHubAdapter(webhook_secret="secret")
        
        event = adapter.parse_webhook(sample_github_pr_payload, github_headers)
        
        assert event is not None
        assert event.provider == "github"
        assert event.repo_owner == "myorg"
        assert event.repo_name == "myrepo"
        assert event.pr_number == 42
        assert event.action == PRAction.OPENED
        assert event.branch == "feature/new-thing"
        assert event.target_branch == "main"
        assert event.author == "johndoe"
    
    def test_parse_webhook_synchronize(self, github_headers):
        """Test parsing pull_request synchronize event."""
        adapter = GitHubAdapter(webhook_secret="secret")
        
        payload = {
            "action": "synchronize",
            "number": 42,
            "pull_request": {
                "number": 42,
                "title": "Update PR",
                "head": {
                    "ref": "feature/test",
                    "sha": "abc123"
                },
                "base": {
                    "ref": "main"
                },
                "user": {"login": "user1"}
            },
            "repository": {
                "name": "repo",
                "owner": {"login": "owner"}
            }
        }
        
        event = adapter.parse_webhook(payload, github_headers)
        
        assert event is not None
        assert event.action == PRAction.SYNCHRONIZE
    
    def test_parse_webhook_merged(self, github_headers):
        """Test parsing pull_request closed as merged."""
        adapter = GitHubAdapter(webhook_secret="secret")
        
        payload = {
            "action": "closed",
            "number": 42,
            "pull_request": {
                "number": 42,
                "title": "Feature",
                "merged": True,
                "head": {"ref": "feature", "sha": "abc"},
                "base": {"ref": "main"},
                "user": {"login": "user"}
            },
            "repository": {
                "name": "repo",
                "owner": {"login": "owner"}
            }
        }
        
        event = adapter.parse_webhook(payload, github_headers)
        
        assert event is not None
        assert event.action == PRAction.MERGED
    
    def test_parse_webhook_non_pr_event(self, github_headers):
        """Test parsing non-pull_request event."""
        adapter = GitHubAdapter(webhook_secret="secret")
        
        headers = {**github_headers, "X-GitHub-Event": "push"}
        event = adapter.parse_webhook({}, headers)
        
        assert event is None
    
    def test_parse_webhook_unsupported_action(self, sample_github_pr_payload, github_headers):
        """Test parsing unsupported action."""
        adapter = GitHubAdapter(webhook_secret="secret")
        
        payload = {**sample_github_pr_payload, "action": "labeled"}
        event = adapter.parse_webhook(payload, github_headers)
        
        assert event is None
    
    @pytest.mark.asyncio
    async def test_fetch_pr_success(self, sample_pr_event):
        """Test successful PR fetch."""
        adapter = GitHubAdapter(webhook_secret="secret", token="token")
        
        mock_response = Mock()
        mock_response.text = "diff content"
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.fetch_pr(sample_pr_event)
        
        assert result["diff"] == "diff content"
        mock_client.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_pr_no_token(self, sample_pr_event):
        """Test PR fetch without token."""
        adapter = GitHubAdapter(webhook_secret="secret")
        
        mock_response = Mock()
        mock_response.text = "diff content"
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.fetch_pr(sample_pr_event)
        
        assert result["diff"] == "diff content"
    
    @pytest.mark.asyncio
    async def test_fetch_pr_error(self, sample_pr_event):
        """Test PR fetch with HTTP error."""
        adapter = GitHubAdapter(webhook_secret="secret", token="token")
        
        mock_client = Mock()
        mock_client.get = AsyncMock(side_effect=Exception("HTTP Error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception):
                await adapter.fetch_pr(sample_pr_event)
    
    @pytest.mark.asyncio
    async def test_post_comment_success(self, sample_pr_event):
        """Test successful comment posting."""
        adapter = GitHubAdapter(webhook_secret="secret", token="token")
        
        comments = [
            Mock(file_path="file.py", line_number=10, message="Test", severity="warning", suggestion=None)
        ]
        
        mock_response = Mock()
        mock_response.status_code = 200
        
        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.post_comment(sample_pr_event, comments, "Summary")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_post_comment_no_token(self, sample_pr_event):
        """Test comment posting without token."""
        adapter = GitHubAdapter(webhook_secret="secret")
        
        comments = [Mock(file_path="file.py", line_number=10, message="Test", severity="warning")]
        
        with pytest.raises(ValueError, match="GitHub token required"):
            await adapter.post_comment(sample_pr_event, comments)
    
    @pytest.mark.asyncio
    async def test_post_comment_failure(self, sample_pr_event):
        """Test comment posting failure."""
        adapter = GitHubAdapter(webhook_secret="secret", token="token")
        
        comments = [
            Mock(file_path="file.py", line_number=10, message="Test", severity="warning", suggestion=None)
        ]
        
        mock_response = Mock()
        mock_response.status_code = 404
        
        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.post_comment(sample_pr_event, comments)
        
        assert result is False


@pytest.mark.unit
@pytest.mark.provider
class TestGitHubAdapterEdgeCases:
    """Test edge cases for GitHubAdapter."""
    
    def test_parse_webhook_missing_pr_data(self, github_headers):
        """Test parsing with missing PR data."""
        adapter = GitHubAdapter(webhook_secret="secret")
        
        payload = {
            "action": "opened",
            "repository": {"name": "repo", "owner": {"login": "owner"}}
            # Missing pull_request key
        }
        
        event = adapter.parse_webhook(payload, github_headers)
        
        # Should still work but with defaults
        assert event is not None
        assert event.pr_number == 0
    
    def test_parse_webhook_missing_repo_data(self, github_headers):
        """Test parsing with missing repository data."""
        adapter = GitHubAdapter(webhook_secret="secret")
        
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 1,
                "title": "Test",
                "head": {"ref": "branch", "sha": "abc"},
                "base": {"ref": "main"},
                "user": {"login": "user"}
            }
            # Missing repository key
        }
        
        event = adapter.parse_webhook(payload, github_headers)
        
        assert event is not None
        assert event.repo_name == ""
        assert event.repo_owner == ""
    
    def test_verify_signature_empty_payload(self):
        """Test signature verification with empty payload."""
        secret = "mysecret"
        payload = b""
        
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        signature = f"sha256={expected}"
        
        adapter = GitHubAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, signature) is True
