"""Environment-backed configuration for the Wunder User-API MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://go.api.gourban.services/v1"
DEFAULT_RADIUS_MI = 5.0
DEFAULT_HTTP_TIMEOUT = 30.0


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    """Resolved server configuration."""

    refresh_token: str
    tenant: str
    base_url: str = DEFAULT_BASE_URL
    branch_id: int | None = None
    default_radius_mi: float = DEFAULT_RADIUS_MI
    http_timeout: float = DEFAULT_HTTP_TIMEOUT

    @property
    def auth_base(self) -> str:
        """Base path for authentication endpoints: /{tenant}/auth."""
        return f"{self.base_url.rstrip('/')}/{self.tenant}/auth"

    @property
    def front_base(self) -> str:
        """Base path for end-user (front) endpoints: /{tenant}/front."""
        return f"{self.base_url.rstrip('/')}/{self.tenant}/front"


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _get_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def load_settings() -> Settings:
    """Build Settings from the environment, failing fast on missing required vars."""
    refresh_token = os.environ.get("WUNDER_REFRESH_TOKEN", "").strip()
    tenant = os.environ.get("WUNDER_TENANT", "").strip()

    missing = [
        name
        for name, value in (
            ("WUNDER_REFRESH_TOKEN", refresh_token),
            ("WUNDER_TENANT", tenant),
        )
        if not value
    ]
    if missing:
        raise ConfigError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". See .env.example."
        )

    base_url = os.environ.get("WUNDER_BASE_URL", "").strip() or DEFAULT_BASE_URL

    return Settings(
        refresh_token=refresh_token,
        tenant=tenant,
        base_url=base_url,
        branch_id=_get_int("WUNDER_BRANCH_ID"),
        default_radius_mi=_get_float("WUNDER_DEFAULT_RADIUS_MI", DEFAULT_RADIUS_MI),
        http_timeout=_get_float("WUNDER_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT),
    )
