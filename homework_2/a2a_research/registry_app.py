"""FastAPI application exposing the Homework 2 dynamic agent registry."""

from __future__ import annotations

from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query

from a2a_research.protocol import AgentCard
from a2a_research.registry import (
    AgentListResponse,
    RegistrationResponse,
    RegistryStore,
)
from a2a_research.settings import ServiceSettings


def create_app(store: RegistryStore | None = None) -> FastAPI:
    """Create an injectable registry app for production and API tests."""

    registry = store if store is not None else RegistryStore()
    app = FastAPI(
        title="Homework 2 A2A Agent Registry",
        version="0.1.0",
        description="Dynamic lookup of remote research agents by capability.",
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "a2a-registry",
            "active_agents": registry.active_count(),
        }

    @app.post("/register", response_model=RegistrationResponse)
    def register(card: AgentCard) -> RegistrationResponse:
        registered_card = registry.register(card)
        return RegistrationResponse(agent=registered_card)

    @app.get("/agents", response_model=AgentListResponse)
    def list_agents(
        capability: str | None = Query(default=None, min_length=1),
    ) -> AgentListResponse:
        cards = registry.list_active(capability)
        return AgentListResponse(agents=cards, count=len(cards))

    @app.get("/agents/{agent_id}", response_model=AgentCard)
    def get_agent(agent_id: str) -> AgentCard:
        card = registry.get_active(agent_id)
        if card is None:
            raise HTTPException(status_code=404, detail="Agent is not registered.")
        return card

    return app


app = create_app()


def main() -> None:
    """Run the registry as a standalone Uvicorn process."""

    settings = ServiceSettings.from_env()
    uvicorn.run(
        "a2a_research.registry_app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
