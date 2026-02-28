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
    def create(
        cls,
        provider: str,
        webhook_secret: str | None = None,
        token: str | None = None,
        username: str | None = None,
        app_password: str | None = None,
    ) -> ProviderAdapter:
        """Create a provider adapter instance.

        Args:
            provider: Provider name (github, gitlab, bitbucket)
            webhook_secret: Optional webhook secret override
            token: Optional API token override
            username: Optional username for Bitbucket
            app_password: Optional app password for Bitbucket

        Returns:
            ProviderAdapter instance

        Raises:
            ValueError: If provider is not supported
        """
        provider = provider.lower()

        if provider not in cls._adapters:
            raise ValueError(f"Unknown provider: {provider}")

        adapter_class = cls._adapters[provider]

        if provider == "github":
            return adapter_class(
                webhook_secret=webhook_secret or settings.github_webhook_secret,
                token=token or settings.github_private_key,
            )
        elif provider == "gitlab":
            return adapter_class(
                webhook_secret=webhook_secret or settings.gitlab_webhook_secret,
                token=token or settings.gitlab_token,
            )
        elif provider == "bitbucket":
            return adapter_class(
                webhook_secret=webhook_secret or settings.bitbucket_webhook_secret,
                username=username or settings.bitbucket_username,
                app_password=app_password or settings.bitbucket_app_password,
            )

        raise ValueError(f"Configuration not found for provider: {provider}")

    # Alias for backward compatibility with tests
    create_provider = create

    @classmethod
    def register(cls, name: str, adapter_class: type[ProviderAdapter]) -> None:
        """Register a new provider adapter.

        Args:
            name: Provider name
            adapter_class: Adapter class to register
        """
        cls._adapters[name.lower()] = adapter_class

    @classmethod
    def get_provider(cls, provider: str) -> ProviderAdapter:
        """Get a provider adapter instance (alias for create).

        Args:
            provider: Provider name (github, gitlab, bitbucket)

        Returns:
            ProviderAdapter instance
        """
        return cls.create(provider)

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported provider names."""
        return list(cls._adapters.keys())
