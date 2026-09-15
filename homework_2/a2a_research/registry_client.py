"""Async HTTP client used by agents and the future workflow orchestrator."""

from __future__ import annotations

from types import TracebackType

import httpx

from a2a_research.protocol import AgentCard
from a2a_research.registry import (
    AgentListResponse,
    RegistrationResponse,
)


class RegistryLookupError(LookupError):
    """Raised when no registered agent provides a requested capability."""


class RegistryClient:
    """Small typed client for the registry HTTP API.

    An HTTPX client can be injected for tests or for connection reuse. When no
    client is injected, the registry client owns and closes its own client.
    """

    def __init__(
        self,
        registry_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 5.0,
    ) -> None:
        normalized_url = registry_url.strip().rstrip("/")
        if not normalized_url:
            raise ValueError("registry_url must not be empty.")
        self.registry_url = normalized_url
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def __aenter__(self) -> RegistryClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying client when this instance owns it."""

        if self._owns_client:
            await self._client.aclose()

    async def register(self, card: AgentCard) -> AgentCard:
        """Register an agent card and return the accepted card."""

        response = await self._client.post(
            f"{self.registry_url}/register",
            json=card.model_dump(by_alias=True, mode="json"),
        )
        response.raise_for_status()
        body = RegistrationResponse.model_validate(response.json())
        return body.agent

    async def list_agents(self, capability: str | None = None) -> list[AgentCard]:
        """List active agents, optionally filtering by capability."""

        params: dict[str, str] | None = None
        if capability is not None:
            params = {"capability": capability}
        response = await self._client.get(
            f"{self.registry_url}/agents",
            params=params,
        )
        response.raise_for_status()
        body = AgentListResponse.model_validate(response.json())
        return body.agents

    async def find_agent(self, capability: str) -> AgentCard:
        """Return the deterministically first active agent for a capability."""

        cards = await self.list_agents(capability)
        if not cards:
            raise RegistryLookupError(
                f"No active agent provides capability '{capability}'."
            )
        return cards[0]
