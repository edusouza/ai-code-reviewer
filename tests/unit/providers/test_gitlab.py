"""Tests for GitLab provider adapter."""
import pytest
import hmac
import hashlib
import json
from unittest.mock import Mock, AsyncMock, patch

from providers.gitlab import GitLabAdapter
from models.events import PREvent, PRAction


@pytest.mark.unit
@pytest.mark.provider
class TestGitLabAdapter:
    """Test suite for GitLabAdapter."""
    
    def test_init_with_token(self):
        """Test adapter initialization with token."""
        adapter = GitLabAdapter(webhook_secret="secret", token="gitlab_token")
        assert adapter.webhook_secret == "secret"
        assert adapter.api_token == "gitlab_token"
    
    def test_init_without_token(self):
        """Test adapter initialization without token."""
        adapter = GitLabAdapter(webhook_secret="secret")
        assert adapter.webhook_secret == "secret"
        assert adapter.api_token is None
    
    def test_get_event_type(self, gitlab_headers):
        """Test event type extraction from headers."""
        adapter = GitLabAdapter(webhook_secret="secret")
        
        event_type = adapter.get_event_type(gitlab_headers)
        assert event_type == "Merge Request Hook"
    
    def test_get_event_type_missing(self):
        """Test event type extraction with missing header."""
        adapter = GitLabAdapter(webhook_secret="secret")
        
        event_type = adapter.get_event_type({})
        assert event_type is None
    
    def test_verify_signature_token_match(self):
        """Test signature verification with simple token match."""
        secret = "mysecret"
        payload = b'{"object_kind": "merge_request"}'
        
        adapter = GitLabAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, secret) is True
    
    def test_verify_signature_hmac(self):
        """Test signature verification with HMAC."""
        secret = "mysecret"
        payload = b'{"object_kind": "merge_request"}'
        
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        adapter = GitLabAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, expected) is True
    
    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        secret = "mysecret"
        payload = b'{"object_kind": "merge_request"}'
        
        adapter = GitLabAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, "invalid") is False
    
    def test_verify_signature_no_secret(self):
        """Test signature verification with no secret (dev mode)."""
        adapter = GitLabAdapter(webhook_secret="")
        assert adapter.verify_signature(b'{"object_kind": "merge_request"}', "any") is True
    
    def test_parse_webhook_opened(self, sample_gitlab_mr_payload, gitlab_headers):
        """Test parsing merge request opened event."""
        adapter = GitLabAdapter(webhook_secret="secret")
        
        event = adapter.parse_webhook(sample_gitlab_mr_payload, gitlab_headers)
        
        assert event is not None
        assert event.provider == "gitlab"
        assert event.repo_owner == "myorg"
        assert event.repo_name == "myrepo"
        assert event.pr_number == 42
        assert event.action == PRAction.OPENED
        assert event.branch == "feature/new-thing"
        assert event.target_branch == "main"
        assert event.author == "johndoe"
    
    def test_parse_webhook_merged(self, gitlab_headers):
        """Test parsing merge request merged event."""
        adapter = GitLabAdapter(webhook_secret="secret")
        
        payload = {
            "object_kind": "merge_request",
            "project": {"name": "repo", "namespace": "owner"},
            "object_attributes": {
                "iid": 1,
                "title": "Feature",
                "action": "merge",
                "source_branch": "feature",
                "target_branch": "main",
                "author_id": "user1",
                "last_commit": {"id": "abc123"}
            }
        }
        
        event = adapter.parse_webhook(payload, gitlab_headers)
        
        assert event is not None
        assert event.action == PRAction.MERGED
    
    def test_parse_webhook_closed(self, gitlab_headers):
        """Test parsing merge request closed event."""
        adapter = GitLabAdapter(webhook_secret="secret")
        
        payload = {
            "object_kind": "merge_request",
            "project": {"name": "repo", "namespace": "owner"},
            "object_attributes": {
                "iid": 1,
                "title": "Feature",
                "action": "close",
                "source_branch": "feature",
                "target_branch": "main",
                "author_id": "user1",
                "last_commit": {"id": "abc123"}
            }
        }
        
        event = adapter.parse_webhook(payload, gitlab_headers)
        
        assert event is not None
        assert event.action == PRAction.CLOSED
    
    def test_parse_webhook_non_mr_event(self):
        """Test parsing non-merge request event."""
        adapter = GitLabAdapter(webhook_secret="secret")
        
        headers = {"X-Gitlab-Event": "Push Hook"}
        event = adapter.parse_webhook({}, headers)
        
        assert event is None
    
    def test_parse_webhook_wrong_object_kind(self, gitlab_headers):
        """Test parsing with wrong object kind."""
        adapter = GitLabAdapter(webhook_secret="secret")
        
        payload = {
            "object_kind": "issue",  # Wrong kind
            "project": {"name": "repo", "namespace": "owner"},
            "object_attributes": {"iid": 1, "title": "Test"}
        }
        
        event = adapter.parse_webhook(payload, gitlab_headers)
        
        assert event is None
    
    def test_parse_webhook_unsupported_action(self, gitlab_headers):
        """Test parsing unsupported action."""
        adapter = GitLabAdapter(webhook_secret="secret")
        
        payload = {
            "object_kind": "merge_request",
            "project": {"name": "repo", "namespace": "owner"},
            "object_attributes": {
                "iid": 1,
                "title": "Test",
                "action": "approved",  # Unsupported
                "source_branch": "feature",
                "target_branch": "main",
                "last_commit": {"id": "abc"}
            }
        }
        
        event = adapter.parse_webhook(payload, gitlab_headers)
        
        assert event is None
    
    @pytest.mark.asyncio
    async def test_fetch_pr_success(self, sample_pr_event):
        """Test successful MR fetch."""
        adapter = GitLabAdapter(webhook_secret="secret", token="token")
        
        # Update event for GitLab
        sample_pr_event.provider = "gitlab"
        
        mock_response = Mock()
        mock_response.json = Mock(return_value=[
            {"diff": "diff content 1"},
            {"diff": "diff content 2"}
        ])
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.fetch_pr(sample_pr_event)
        
        assert "diff content 1" in result["diff"]
        assert "diff content 2" in result["diff"]
        assert len(result["files"]) == 2
    
    @pytest.mark.asyncio
    async def test_fetch_pr_no_token(self, sample_pr_event):
        """Test MR fetch without token."""
        adapter = GitLabAdapter(webhook_secret="secret")
        
        sample_pr_event.provider = "gitlab"
        
        mock_response = Mock()
        mock_response.json = Mock(return_value=[])
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.fetch_pr(sample_pr_event)
        
        assert result["diff"] == ""
    
    @pytest.mark.asyncio
    async def test_fetch_pr_error(self, sample_pr_event):
        """Test MR fetch with HTTP error."""
        adapter = GitLabAdapter(webhook_secret="secret", token="token")
        
        sample_pr_event.provider = "gitlab"
        
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
        adapter = GitLabAdapter(webhook_secret="secret", token="token")
        
        sample_pr_event.provider = "gitlab"
        
        comments = [
            Mock(file_path="file.py", line_number=10, message="Test", severity="warning", suggestion="fix")
        ]
        
        mock_response = Mock()
        mock_response.status_code = 201
        
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
        adapter = GitLabAdapter(webhook_secret="secret")
        
        sample_pr_event.provider = "gitlab"
        
        comments = [Mock(file_path="file.py", line_number=10, message="Test", severity="warning")]
        
        with pytest.raises(ValueError, match="GitLab token required"):
            await adapter.post_comment(sample_pr_event, comments)
    
    @pytest.mark.asyncio
    async def test_post_comment_no_summary(self, sample_pr_event):
        """Test comment posting without summary."""
        adapter = GitLabAdapter(webhook_secret="secret", token="token")
        
        sample_pr_event.provider = "gitlab"
        
        comments = [
            Mock(file_path="file.py", line_number=10, message="Test", severity="warning", suggestion=None)
        ]
        
        mock_response = Mock()
        mock_response.status_code = 201
        
        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.post_comment(sample_pr_event, comments, "")
        
        assert result is True


@pytest.mark.unit
@pytest.mark.provider
class TestGitLabAdapterEdgeCases:
    """Test edge cases for GitLabAdapter."""
    
    def test_parse_webhook_missing_attributes(self, gitlab_headers):
        """Test parsing with missing object_attributes."""
        adapter = GitLabAdapter(webhook_secret="secret")
        
        payload = {
            "object_kind": "merge_request",
            "project": {"name": "repo", "namespace": "owner"}
            # Missing object_attributes
        }
        
        event = adapter.parse_webhook(payload, gitlab_headers)
        
        # Should handle gracefully
        assert event is not None
        assert event.pr_number == 0
    
    def test_parse_webhook_missing_project(self, gitlab_headers):
        """Test parsing with missing project data."""
        adapter = GitLabAdapter(webhook_secret="secret")
        
        payload = {
            "object_kind": "merge_request",
            "object_attributes": {
                "iid": 1,
                "title": "Test",
                "action": "open",
                "source_branch": "feature",
                "target_branch": "main",
                "last_commit": {"id": "abc"}
            }
            # Missing project
        }
        
        event = adapter.parse_webhook(payload, gitlab_headers)
        
        assert event is not None
        assert event.repo_name == ""
        assert event.repo_owner == ""
    
    async def test_fetch_pr_url_encoding(self, sample_pr_event):
        """Test URL encoding for project path."""
        adapter = GitLabAdapter(webhook_secret="secret", token="token")
        
        sample_pr_event.provider = "gitlab"
        sample_pr_event.repo_owner = "group/subgroup"
        sample_pr_event.repo_name = "project"
        
        # The URL should encode the slash in the project path
        # group/subgroup/project -> group%2Fsubgroup%2Fproject
        expected_path = "group%2Fsubgroup%2Fproject"
        
        mock_response = Mock()
        mock_response.json = Mock(return_value=[])
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client) as mock_cls:
            await adapter.fetch_pr(sample_pr_event)
            
            # Verify the URL contains encoded path
            call_args = mock_client.get.call_args
            assert expected_path in call_args[0][0]
