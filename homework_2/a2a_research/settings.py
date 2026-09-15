"""Environment-backed settings shared by the registry and agent processes."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


_DEFAULT_SERVICE_NAME = "a2a-service"
_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8000
_DEFAULT_REGISTRY_URL = "http://127.0.0.1:8000"


def _port(value: str, variable_name: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError(f"{variable_name} must be an integer.") from exc
    if not 1 <= port <= 65_535:
        raise ValueError(f"{variable_name} must be between 1 and 65535.")
    return port


@dataclass(frozen=True, slots=True)
class ServiceSettings:
    """Runtime settings that do not depend on a particular agent role."""

    service_name: str = _DEFAULT_SERVICE_NAME
    host: str = _DEFAULT_HOST
    port: int = _DEFAULT_PORT
    registry_url: str = _DEFAULT_REGISTRY_URL
    public_url: str | None = None

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        prefix: str = "A2A_",
    ) -> ServiceSettings:
        """Build settings from a mapping, making tests independent of os.environ."""

        values = os.environ if env is None else env
        service_name = values.get(f"{prefix}SERVICE_NAME", _DEFAULT_SERVICE_NAME).strip()
        host = values.get(f"{prefix}HOST", _DEFAULT_HOST).strip()
        registry_url = values.get(f"{prefix}REGISTRY_URL", _DEFAULT_REGISTRY_URL).strip()
        public_url_raw = values.get(f"{prefix}PUBLIC_URL", "").strip()

        if not service_name:
            raise ValueError(f"{prefix}SERVICE_NAME must not be empty.")
        if not host:
            raise ValueError(f"{prefix}HOST must not be empty.")
        if not registry_url:
            raise ValueError(f"{prefix}REGISTRY_URL must not be empty.")

        port = _port(values.get(f"{prefix}PORT", str(_DEFAULT_PORT)), f"{prefix}PORT")
        return cls(
            service_name=service_name,
            host=host,
            port=port,
            registry_url=registry_url.rstrip("/"),
            public_url=public_url_raw or None,
        )
