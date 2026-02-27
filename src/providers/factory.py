from config import settings
from providers.base import ProviderAdapter
from providers.bitbucket import BitbucketAdapter
from providers.github import GitHubAdapter
from providers.gitlab import GitLabAdapter


class ProviderFactory:
    """Factory for creating provider adapters."""

    _adapters: dict[str, type[ProviderAdapter]] = {
        "github": GitHubAdapter,
        "gitlab": GitLabAdapter,
        "bitbucket": BitbucketAdapter,
    }

    @classmethod
    def create(cls, provider: str) -> ProviderAdapter:
        """Create a provider adapter instance.

        Args:
            provider: Provider name (github, gitlab, bitbucket)

        Returns:
            ProviderAdapter instance

        Raises:
            ValueError: If provider is not supported
        """
        provider = provider.lower()

        if provider not in cls._adapters:
            raise ValueError(f"Unsupported provider: {provider}")

        adapter_class = cls._adapters[provider]

        if provider == "github":
            return adapter_class(
                webhook_secret=settings.github_webhook_secret, api_token=settings.github_private_key
            )
        elif provider == "gitlab":
            return adapter_class(
                webhook_secret=settings.gitlab_webhook_secret, api_token=settings.gitlab_token
            )
        elif provider == "bitbucket":
            return adapter_class(
                webhook_secret=settings.bitbucket_webhook_secret,
                username=settings.bitbucket_username,
                app_password=settings.bitbucket_app_password,
            )

        raise ValueError(f"Configuration not found for provider: {provider}")

    @classmethod
    def register(cls, name: str, adapter_class: type[ProviderAdapter]) -> None:
        """Register a new provider adapter.

        Args:
            name: Provider name
            adapter_class: Adapter class to register
        """
        cls._adapters[name.lower()] = adapter_class

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported provider names."""
        return list(cls._adapters.keys())
