"""Tests for API webhooks module."""

import pytest
from httpx import AsyncClient


class TestGitHubWebhook:
    """Test GitHub webhook endpoint."""

    @pytest.mark.asyncio
    async def test_github_webhook_endpoint_exists(self, async_client: AsyncClient):
        """Test that GitHub webhook endpoint exists and accepts POST requests."""
        response = await async_client.post(
            "/webhooks/github",
            json={"action": "opened", "pull_request": {"number": 1}},
            headers={"x-hub-signature-256": "sha256=test"}
        )

        # Endpoint should accept the request (will process asynchronously)
        assert response.status_code == 202


class TestGitLabWebhook:
    """Test GitLab webhook endpoint."""

    @pytest.mark.asyncio
    async def test_gitlab_webhook_endpoint_exists(self, async_client: AsyncClient):
        """Test that GitLab webhook endpoint exists and accepts POST requests."""
        response = await async_client.post(
            "/webhooks/gitlab",
            json={"object_kind": "merge_request"},
            headers={"x-gitlab-token": "test-token"}
        )

        # Endpoint should accept the request
        assert response.status_code == 202


class TestBitbucketWebhook:
    """Test Bitbucket webhook endpoint."""

    @pytest.mark.asyncio
    async def test_bitbucket_webhook_endpoint_exists(self, async_client: AsyncClient):
        """Test that Bitbucket webhook endpoint exists and accepts POST requests."""
        response = await async_client.post(
            "/webhooks/bitbucket",
            json={"pullrequest": {"id": 1}},
            headers={"x-hook-uuid": "test-uuid"}
        )

        # Endpoint should accept the request
        assert response.status_code == 202
