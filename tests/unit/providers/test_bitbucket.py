"""Tests for Bitbucket provider adapter."""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from providers.bitbucket import BitbucketAdapter
from models.events import PREvent, PRAction


@pytest.mark.unit
@pytest.mark.provider
class TestBitbucketAdapter:
    """Test suite for BitbucketAdapter."""
    
    def test_init_with_credentials(self):
        """Test adapter initialization with credentials."""
        adapter = BitbucketAdapter(
            webhook_secret="secret",
            username="user",
            app_password="pass"
        )
        assert adapter.webhook_secret == "secret"
        assert adapter.username == "user"
        assert adapter.app_password == "pass"
        assert adapter.auth == ("user", "pass")
    
    def test_init_without_credentials(self):
        """Test adapter initialization without credentials."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        assert adapter.webhook_secret == "secret"
        assert adapter.username is None
        assert adapter.app_password is None
        assert adapter.auth is None
    
    def test_get_event_type(self, bitbucket_headers):
        """Test event type extraction from headers."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        event_type = adapter.get_event_type(bitbucket_headers)
        assert event_type == "pullrequest:created"
    
    def test_get_event_type_missing(self):
        """Test event type extraction with missing header."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        event_type = adapter.get_event_type({})
        assert event_type is None
    
    def test_verify_signature_simple(self):
        """Test simple signature verification."""
        secret = "mysecret"
        payload = b'{"pullrequest": {}}'
        
        adapter = BitbucketAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, secret) is True
    
    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        secret = "mysecret"
        payload = b'{"pullrequest": {}}'
        
        adapter = BitbucketAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, "invalid") is False
    
    def test_verify_signature_no_secret(self):
        """Test signature verification with no secret (dev mode)."""
        adapter = BitbucketAdapter(webhook_secret="")
        assert adapter.verify_signature(b'{"pullrequest": {}}', "any") is True
    
    def test_parse_webhook_created(self, sample_bitbucket_pr_payload, bitbucket_headers):
        """Test parsing pull request created event."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        event = adapter.parse_webhook(sample_bitbucket_pr_payload, bitbucket_headers)
        
        assert event is not None
        assert event.provider == "bitbucket"
        assert event.repo_owner == "myorg"
        assert event.repo_name == "myrepo"
        assert event.pr_number == 42
        assert event.action == PRAction.OPENED
        assert event.branch == "feature/new-thing"
        assert event.target_branch == "main"
        assert event.author == "johndoe"
    
    def test_parse_webhook_merged(self, bitbucket_headers):
        """Test parsing pull request merged event."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        payload = {
            "pullrequest": {
                "id": 1,
                "title": "Feature",
                "state": "MERGED",
                "source": {
                    "branch": {"name": "feature"},
                    "commit": {"hash": "abc123"},
                    "repository": {"name": "repo", "full_name": "owner/repo"}
                },
                "destination": {
                    "branch": {"name": "main"},
                    "repository": {"name": "repo", "full_name": "owner/repo"}
                },
                "author": {"username": "user1"},
                "links": {"html": {"href": "https://bitbucket.org/owner/repo/pull-requests/1"}}
            }
        }
        
        headers = {**bitbucket_headers, "X-Event-Key": "pullrequest:fulfilled"}
        event = adapter.parse_webhook(payload, headers)
        
        assert event is not None
        assert event.action == PRAction.MERGED
    
    def test_parse_webhook_closed(self, bitbucket_headers):
        """Test parsing pull request closed event."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        payload = {
            "pullrequest": {
                "id": 1,
                "title": "Feature",
                "state": "DECLINED",
                "source": {
                    "branch": {"name": "feature"},
                    "commit": {"hash": "abc123"},
                    "repository": {"name": "repo", "full_name": "owner/repo"}
                },
                "destination": {
                    "branch": {"name": "main"},
                    "repository": {"name": "repo", "full_name": "owner/repo"}
                },
                "author": {"username": "user1"},
                "links": {"html": {"href": "https://bitbucket.org/owner/repo/pull-requests/1"}}
            }
        }
        
        headers = {**bitbucket_headers, "X-Event-Key": "pullrequest:rejected"}
        event = adapter.parse_webhook(payload, headers)
        
        assert event is not None
        assert event.action == PRAction.CLOSED
    
    def test_parse_webhook_non_pr_event(self, bitbucket_headers):
        """Test parsing non-pull request event."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        headers = {**bitbucket_headers, "X-Event-Key": "repo:commit_comment_created"}
        event = adapter.parse_webhook({}, headers)
        
        assert event is None
    
    def test_parse_webhook_approved_event(self, bitbucket_headers):
        """Test parsing approved event (should be skipped)."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        headers = {**bitbucket_headers, "X-Event-Key": "pullrequest:approved"}
        event = adapter.parse_webhook({"pullrequest": {}}, headers)
        
        assert event is None
    
    def test_parse_webhook_unapproved_event(self, bitbucket_headers):
        """Test parsing unapproved event (should be skipped)."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        headers = {**bitbucket_headers, "X-Event-Key": "pullrequest:unapproved"}
        event = adapter.parse_webhook({"pullrequest": {}}, headers)
        
        assert event is None
    
    def test_parse_webhook_missing_pr_data(self, bitbucket_headers):
        """Test parsing with missing pull request data."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        payload = {"repository": {}}  # Missing pullrequest
        
        event = adapter.parse_webhook(payload, bitbucket_headers)
        
        assert event is None
    
    @pytest.mark.asyncio
    async def test_fetch_pr_success(self, sample_pr_event):
        """Test successful PR fetch."""
        adapter = BitbucketAdapter(
            webhook_secret="secret",
            username="user",
            app_password="pass"
        )
        
        sample_pr_event.provider = "bitbucket"
        
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
    async def test_fetch_pr_no_auth(self, sample_pr_event):
        """Test PR fetch without authentication."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        sample_pr_event.provider = "bitbucket"
        
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
        adapter = BitbucketAdapter(
            webhook_secret="secret",
            username="user",
            app_password="pass"
        )
        
        sample_pr_event.provider = "bitbucket"
        
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
        adapter = BitbucketAdapter(
            webhook_secret="secret",
            username="user",
            app_password="pass"
        )
        
        sample_pr_event.provider = "bitbucket"
        
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
    async def test_post_comment_no_auth(self, sample_pr_event):
        """Test comment posting without authentication."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        sample_pr_event.provider = "bitbucket"
        
        comments = [Mock(file_path="file.py", line_number=10, message="Test", severity="warning")]
        
        with pytest.raises(ValueError, match="Bitbucket credentials required"):
            await adapter.post_comment(sample_pr_event, comments)
    
    @pytest.mark.asyncio
    async def test_post_comment_no_summary(self, sample_pr_event):
        """Test comment posting without summary."""
        adapter = BitbucketAdapter(
            webhook_secret="secret",
            username="user",
            app_password="pass"
        )
        
        sample_pr_event.provider = "bitbucket"
        
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
class TestBitbucketAdapterEdgeCases:
    """Test edge cases for BitbucketAdapter."""
    
    def test_parse_webhook_no_full_name(self, bitbucket_headers):
        """Test parsing with missing full_name in repository."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        payload = {
            "pullrequest": {
                "id": 1,
                "title": "Test",
                "state": "OPEN",
                "source": {
                    "branch": {"name": "feature"},
                    "commit": {"hash": "abc"},
                    "repository": {"name": "repo"}  # No full_name
                },
                "destination": {
                    "branch": {"name": "main"},
                    "repository": {"name": "repo"}
                },
                "author": {"username": "user"},
                "links": {"html": {"href": "http://example.com"}}
            }
        }
        
        event = adapter.parse_webhook(payload, bitbucket_headers)
        
        assert event is not None
        assert event.repo_owner == ""  # Should handle gracefully
    
    def test_parse_webhook_nested_namespace(self, bitbucket_headers):
        """Test parsing with nested namespace in full_name."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        payload = {
            "pullrequest": {
                "id": 1,
                "title": "Test",
                "state": "OPEN",
                "source": {
                    "branch": {"name": "feature"},
                    "commit": {"hash": "abc"},
                    "repository": {"name": "repo", "full_name": "workspace/project/repo"}
                },
                "destination": {
                    "branch": {"name": "main"},
                    "repository": {"name": "repo", "full_name": "workspace/project/repo"}
                },
                "author": {"username": "user"},
                "links": {"html": {"href": "http://example.com"}}
            }
        }
        
        event = adapter.parse_webhook(payload, bitbucket_headers)
        
        assert event is not None
        # Should take first part as owner
        assert event.repo_owner == "workspace"
    
    def test_parse_webhook_no_html_url(self, bitbucket_headers):
        """Test parsing with missing HTML URL."""
        adapter = BitbucketAdapter(webhook_secret="secret")
        
        payload = {
            "pullrequest": {
                "id": 1,
                "title": "Test",
                "state": "OPEN",
                "source": {
                    "branch": {"name": "feature"},
                    "commit": {"hash": "abc"},
                    "repository": {"name": "repo", "full_name": "owner/repo"}
                },
                "destination": {
                    "branch": {"name": "main"},
                    "repository": {"name": "repo", "full_name": "owner/repo"}
                },
                "author": {"username": "user"},
                "links": {}  # No html link
            }
        }
        
        event = adapter.parse_webhook(payload, bitbucket_headers)
        
        assert event is not None
        assert event.url is None
