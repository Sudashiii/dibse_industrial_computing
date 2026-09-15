from __future__ import annotations

import httpx
import pytest

from a2a_research.protocol import AgentCard
from a2a_research.registry import RegistryStore
from a2a_research.registry_app import create_app
from a2a_research.registry_client import RegistryClient, RegistryLookupError


def search_card() -> AgentCard:
    return AgentCard(
        agentId="search-agent",
        name="Literature Search Agent",
        description="Finds papers.",
        capabilities=["research.search"],
        url="http://search-agent:8101/a2a",
        healthUrl="http://search-agent:8101/health",
    )


@pytest.mark.asyncio
async def test_registry_client_registers_and_discovers_agent() -> None:
    app = create_app(RegistryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://registry",
    ) as http_client:
        registry = RegistryClient("http://registry", client=http_client)

        registered = await registry.register(search_card())
        discovered = await registry.find_agent("research.search")

    assert registered.agent_id == "search-agent"
    assert discovered.name == "Literature Search Agent"
    assert str(discovered.url) == "http://search-agent:8101/a2a"


@pytest.mark.asyncio
async def test_registry_client_raises_for_missing_capability() -> None:
    app = create_app(RegistryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://registry",
    ) as http_client:
        registry = RegistryClient("http://registry", client=http_client)

        with pytest.raises(RegistryLookupError, match="research.synthesize"):
            await registry.find_agent("research.synthesize")
