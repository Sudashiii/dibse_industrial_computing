from __future__ import annotations

import pytest

from a2a_research.settings import ServiceSettings


def test_settings_read_environment_mapping() -> None:
    settings = ServiceSettings.from_env(
        {
            "A2A_SERVICE_NAME": "search-agent",
            "A2A_HOST": "127.0.0.1",
            "A2A_PORT": "8101",
            "A2A_REGISTRY_URL": "http://127.0.0.1:8000/",
            "A2A_PUBLIC_URL": "http://127.0.0.1:8101/a2a",
        }
    )

    assert settings.service_name == "search-agent"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8101
    assert settings.registry_url == "http://127.0.0.1:8000"
    assert settings.public_url == "http://127.0.0.1:8101/a2a"


@pytest.mark.parametrize("value", ["0", "65536", "not-a-port"])
def test_settings_reject_invalid_ports(value: str) -> None:
    with pytest.raises(ValueError, match="A2A_PORT"):
        ServiceSettings.from_env({"A2A_PORT": value})


def test_settings_reject_empty_required_values() -> None:
    with pytest.raises(ValueError, match="SERVICE_NAME"):
        ServiceSettings.from_env({"A2A_SERVICE_NAME": "  "})

    with pytest.raises(ValueError, match="REGISTRY_URL"):
        ServiceSettings.from_env({"A2A_REGISTRY_URL": "  "})
