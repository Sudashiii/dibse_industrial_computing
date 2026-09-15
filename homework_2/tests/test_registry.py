from __future__ import annotations

from fastapi.testclient import TestClient

from a2a_research.protocol import AgentCard
from a2a_research.registry import RegistryStore
from a2a_research.registry_app import create_app


def card(
    agent_id: str,
    *,
    capabilities: list[str],
    port: int,
) -> AgentCard:
    return AgentCard(
        agentId=agent_id,
        name=f"{agent_id} name",
        description=f"Provides {agent_id} capabilities.",
        capabilities=capabilities,
        url=f"http://127.0.0.1:{port}/a2a",
        healthUrl=f"http://127.0.0.1:{port}/health",
    )


def test_health_reports_registered_agent_count() -> None:
    store = RegistryStore()
    store.register(card("search-agent", capabilities=["research.search"], port=8101))
    client = TestClient(create_app(store))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "a2a-registry",
        "active_agents": 1,
    }


def test_register_and_filter_agents_by_capability() -> None:
    client = TestClient(create_app(RegistryStore()))
    search_card = card("search-agent", capabilities=["research.search"], port=8101)
    synthesis_card = card(
        "synthesis-agent",
        capabilities=["research.synthesize"],
        port=8103,
    )

    assert client.post("/register", json=search_card.model_dump(by_alias=True, mode="json")).status_code == 200
    assert client.post(
        "/register",
        json=synthesis_card.model_dump(by_alias=True, mode="json"),
    ).status_code == 200

    response = client.get("/agents", params={"capability": "research.search"})

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["agents"][0]["agentId"] == "search-agent"


def test_duplicate_registration_replaces_the_card() -> None:
    store = RegistryStore()
    first = card("search-agent", capabilities=["research.search"], port=8101)
    replacement = card(
        "search-agent",
        capabilities=["research.search", "research.preview"],
        port=9101,
    )

    store.register(first)
    store.register(replacement)

    active = store.list_active()
    assert len(active) == 1
    assert str(active[0].url) == "http://127.0.0.1:9101/a2a"
    assert active[0].capabilities == ["research.search", "research.preview"]


def test_stale_entries_are_not_returned() -> None:
    now = [100.0]
    store = RegistryStore(ttl_seconds=5, clock=lambda: now[0])
    store.register(card("search-agent", capabilities=["research.search"], port=8101))

    now[0] = 106.0

    assert store.list_active() == []
    assert store.get_active("search-agent") is None


def test_unknown_agent_returns_not_found() -> None:
    client = TestClient(create_app(RegistryStore()))

    response = client.get("/agents/missing-agent")

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent is not registered."
