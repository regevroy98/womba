"""Common Atlassian client utilities."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

try:  # pragma: no cover - settings module requires optional dependencies
    from src.config.settings import settings
except ModuleNotFoundError:  # pragma: no cover - fall back to environment variables in tests
    settings = None  # type: ignore[assignment]


@dataclass
class AtlassianCredentials:
    """Shared authentication parameters for Atlassian cloud APIs."""

    base_url: str
    email: str
    api_token: str

    @classmethod
    def resolve(
        cls,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ) -> "AtlassianCredentials":
        """Resolve credentials using explicit overrides or global settings."""

        def _get_setting(name: str, env_key: str) -> str:
            if settings is not None:
                return getattr(settings, name)
            return os.environ.get(env_key, "")

        resolved_base_url = (
            base_url or _get_setting("jira_base_url", "JIRA_BASE_URL") or ""
        ).rstrip("/")
        return cls(
            base_url=resolved_base_url,
            email=email or _get_setting("jira_email", "JIRA_EMAIL"),
            api_token=api_token or _get_setting("jira_api_token", "JIRA_API_TOKEN"),
        )


class AtlassianClientBase:
    """Base class that consolidates Atlassian authentication handling."""

    def __init__(
        self,
        credentials: Optional[AtlassianCredentials] = None,
        *,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ) -> None:
        resolved = credentials or AtlassianCredentials.resolve(
            base_url=base_url,
            email=email,
            api_token=api_token,
        )

        self.base_url = resolved.base_url
        self.email = resolved.email
        self.api_token = resolved.api_token

    @property
    def auth(self) -> tuple[str, str]:
        """Return the HTTP basic auth tuple used by Atlassian APIs."""

        return (self.email, self.api_token)
