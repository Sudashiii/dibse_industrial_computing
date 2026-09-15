"""In-memory registry primitives for dynamic A2A agent discovery."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from a2a_research.protocol import AgentCard


class RegistrationResponse(BaseModel):
    """Response returned after an agent registers itself."""

    status: Literal["registered"] = "registered"
    agent: AgentCard

    model_config = ConfigDict(extra="forbid")


class AgentListResponse(BaseModel):
    """List response used by the registry lookup endpoint."""

    agents: list[AgentCard]
    count: int

    model_config = ConfigDict(extra="forbid")


@dataclass(slots=True)
class _RegistryEntry:
    card: AgentCard
    last_seen: float


class RegistryStore:
    """Store agent cards and remove entries that stopped registering.

    The registry deliberately keeps only process metadata. Agent state and
    research data remain owned by the individual services.
    """

    def __init__(
        self,
        *,
        ttl_seconds: float = 90.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero.")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[str, _RegistryEntry] = {}

    def register(self, card: AgentCard) -> AgentCard:
        """Register or refresh an agent by its stable ID.

        Re-registering an existing ID replaces its card, which supports a
        restarted service changing its container address or version.
        """

        self._entries[card.agent_id] = _RegistryEntry(
            card=card.model_copy(deep=True),
            last_seen=self._clock(),
        )
        return card

    def list_active(self, capability: str | None = None) -> list[AgentCard]:
        """Return active cards, optionally filtered by one capability."""

        self._remove_expired()
        normalized_capability = capability.strip() if capability is not None else None
        cards = [entry.card for entry in self._entries.values()]
        if normalized_capability:
            cards = [
                card
                for card in cards
                if normalized_capability in card.capabilities
            ]
        return sorted(cards, key=lambda card: card.agent_id)

    def get_active(self, agent_id: str) -> AgentCard | None:
        """Return one active card or ``None`` for an unknown/stale ID."""

        self._remove_expired()
        entry = self._entries.get(agent_id)
        return entry.card if entry is not None else None

    def active_count(self) -> int:
        """Return the number of currently active registered agents."""

        return len(self.list_active())

    def _remove_expired(self) -> None:
        now = self._clock()
        expired_ids = [
            agent_id
            for agent_id, entry in self._entries.items()
            if now - entry.last_seen > self._ttl_seconds
        ]
        for agent_id in expired_ids:
            del self._entries[agent_id]
