"""Integration tests for providers."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from providers.bitbucket import BitbucketAdapter
from providers.factory import ProviderFactory
from providers.github import GitHubAdapter
from providers.gitlab import GitLabAdapter


@pytest.mark.integration
@pytest.mark.provider
class TestProviderFactory:
    """Test suite for provider factory."""

    def test_create_github(self):
        """Test creating GitHub adapter."""
        adapter = ProviderFactory.create_provider(
            "github", webhook_secret="secret", token="github_token"
        )

        assert isinstance(adapter, GitHubAdapter)

    def test_create_gitlab(self):
        """Test creating GitLab adapter."""
        adapter = ProviderFactory.create_provider(
            "gitlab", webhook_secret="secret", token="gitlab_token"
        )

        assert isinstance(adapter, GitLabAdapter)

    def test_create_bitbucket(self):
        """Test creating Bitbucket adapter."""
        adapter = ProviderFactory.create_provider(
            "bitbucket", webhook_secret="secret", username="user", app_password="pass"
        )

        assert isinstance(adapter, BitbucketAdapter)

    def test_create_invalid_provider(self):
        """Test creating invalid provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            ProviderFactory.create_provider("unknown", webhook_secret="secret")


@pytest.mark.integration
@pytest.mark.provider
class TestProviderEventNormalization:
    """Test event normalization across providers."""

    def test_github_event_normalization(self, sample_github_pr_payload, github_headers):
        """Test GitHub event normalization."""
        adapter = GitHubAdapter(webhook_secret="secret")

        event = adapter.parse_webhook(sample_github_pr_payload, github_headers)

        # Check normalized fields
        assert event.provider == "github"
        assert event.repo_owner == "myorg"
        assert event.repo_name == "myrepo"
        assert event.pr_number == 42
        assert event.action.value == "opened"
        assert event.branch == "feature/new-thing"
        assert event.target_branch == "main"
        assert event.commit_sha == "abc123def456"
        assert event.pr_title == "Add new feature"
        assert event.author == "johndoe"
        assert event.url == "https://github.com/myorg/myrepo/pull/42"

    def test_gitlab_event_normalization(self, sample_gitlab_mr_payload, gitlab_headers):
        """Test GitLab event normalization."""
        adapter = GitLabAdapter(webhook_secret="secret")

        event = adapter.parse_webhook(sample_gitlab_mr_payload, gitlab_headers)

        # Check normalized fields
        assert event.provider == "gitlab"
        assert event.repo_owner == "myorg"
        assert event.repo_name == "myrepo"
        assert event.pr_number == 42
        assert event.action.value == "opened"
        assert event.branch == "feature/new-thing"
        assert event.target_branch == "main"
        assert event.author == "johndoe"

    def test_bitbucket_event_normalization(self, sample_bitbucket_pr_payload, bitbucket_headers):
        """Test Bitbucket event normalization."""
        adapter = BitbucketAdapter(webhook_secret="secret")

        event = adapter.parse_webhook(sample_bitbucket_pr_payload, bitbucket_headers)

        # Check normalized fields
        assert event.provider == "bitbucket"
        assert event.repo_owner == "myorg"
        assert event.repo_name == "myrepo"
        assert event.pr_number == 42
        assert event.action.value == "opened"
        assert event.branch == "feature/new-thing"
        assert event.target_branch == "main"
        assert event.author == "johndoe"


@pytest.mark.integration
@pytest.mark.provider
class TestProviderSignatureVerification:
    """Test signature verification across providers."""

    def test_github_hmac_signature(self):
        """Test GitHub HMAC signature verification."""
        import hashlib
        import hmac

        secret = "webhook_secret"
        payload = b'{"action": "opened"}'

        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature = f"sha256={expected}"

        adapter = GitHubAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, signature) is True

    def test_gitlab_token_signature(self):
        """Test GitLab token signature verification."""
        secret = "webhook_secret"
        payload = b'{"object_kind": "merge_request"}'

        adapter = GitLabAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, secret) is True

    def test_bitbucket_simple_signature(self):
        """Test Bitbucket simple signature verification."""
        secret = "webhook_secret"
        payload = b'{"pullrequest": {}}'

        adapter = BitbucketAdapter(webhook_secret=secret)
        assert adapter.verify_signature(payload, secret) is True


@pytest.mark.integration
@pytest.mark.provider
class TestProviderAPIIntegration:
    """Test provider API integration with mocked responses."""

    @pytest.mark.asyncio
    async def test_github_fetch_pr(self, sample_pr_event):
        """Test GitHub PR fetch with mocked API."""
        adapter = GitHubAdapter(webhook_secret="secret", token="token")

        mock_response = Mock()
        mock_response.text = "diff --git a/file.txt b/file.txt\n+new line"
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.fetch_pr(sample_pr_event)

        assert "diff" in result
        assert result["diff"] == "diff --git a/file.txt b/file.txt\n+new line"

    @pytest.mark.asyncio
    async def test_gitlab_fetch_mr(self, sample_pr_event):
        """Test GitLab MR fetch with mocked API."""
        adapter = GitLabAdapter(webhook_secret="secret", token="token")
        sample_pr_event.provider = "gitlab"

        mock_response = Mock()
        mock_response.json = Mock(
            return_value=[{"diff": "@@ -1 +1 @@\n-old\n+new"}, {"diff": "@@ -2 +2 @@\n-foo\n+bar"}]
        )
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.fetch_pr(sample_pr_event)

        assert "diff" in result
        assert "old" in result["diff"]
        assert "new" in result["diff"]
        assert len(result["files"]) == 2

    @pytest.mark.asyncio
    async def test_bitbucket_fetch_pr(self, sample_pr_event):
        """Test Bitbucket PR fetch with mocked API."""
        adapter = BitbucketAdapter(webhook_secret="secret", username="user", app_password="pass")
        sample_pr_event.provider = "bitbucket"

        mock_response = Mock()
        mock_response.text = "diff --git a/file.txt b/file.txt\n+new line"
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.fetch_pr(sample_pr_event)

        assert "diff" in result
        assert result["diff"] == "diff --git a/file.txt b/file.txt\n+new line"

    @pytest.mark.asyncio
    async def test_github_post_comment(self, sample_pr_event):
        """Test GitHub comment posting with mocked API."""
        adapter = GitHubAdapter(webhook_secret="secret", token="token")

        comments = [
            Mock(
                file_path="src/main.py",
                line_number=10,
                message="Test comment",
                severity="warning",
                suggestion=None,
            )
        ]

        mock_response = Mock()
        mock_response.status_code = 200

        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.post_comment(sample_pr_event, comments, "Review Summary")

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_gitlab_post_comment(self, sample_pr_event):
        """Test GitLab comment posting with mocked API."""
        adapter = GitLabAdapter(webhook_secret="secret", token="token")
        sample_pr_event.provider = "gitlab"

        comments = [
            Mock(
                file_path="src/main.py",
                line_number=10,
                message="Test comment",
                severity="warning",
                suggestion="Fix this",
            )
        ]

        mock_response = Mock()
        mock_response.status_code = 201

        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.post_comment(sample_pr_event, comments, "Review Summary")

        assert result is True
        # Should post summary + discussion
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_bitbucket_post_comment(self, sample_pr_event):
        """Test Bitbucket comment posting with mocked API."""
        adapter = BitbucketAdapter(webhook_secret="secret", username="user", app_password="pass")
        sample_pr_event.provider = "bitbucket"

        comments = [
            Mock(
                file_path="src/main.py",
                line_number=10,
                message="Test comment",
                severity="warning",
                suggestion=None,
            )
        ]

        mock_response = Mock()
        mock_response.status_code = 201

        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.post_comment(sample_pr_event, comments, "Review Summary")

        assert result is True
        # Should post summary + individual comment
        assert mock_client.post.call_count == 2
