from __future__ import annotations

from collections.abc import Mapping

import httpx
import pytest

from a2a_research.evidence_agent import create_evidence_app
from a2a_research.orchestrator import (
    EVIDENCE_CAPABILITY,
    SEARCH_CAPABILITY,
    SYNTHESIS_CAPABILITY,
    ResearchOrchestrator,
    WorkflowError,
)
from a2a_research.protocol import AgentCard
from a2a_research.registry import RegistryStore
from a2a_research.registry_app import create_app
from a2a_research.search_agent import create_search_app
from a2a_research.synthesis_agent import create_synthesis_app


class RoutingTransport(httpx.AsyncBaseTransport):
    """Route test requests to independent FastAPI apps by hostname."""

    def __init__(self, apps: Mapping[str, object]) -> None:
        self._transports = {
            host: httpx.ASGITransport(app=app) for host, app in apps.items()
        }

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        try:
            transport = self._transports[request.url.host]
        except KeyError as exc:
            raise AssertionError(f"Unexpected test host: {request.url.host}") from exc
        return await transport.handle_async_request(request)

    async def aclose(self) -> None:
        for transport in self._transports.values():
            await transport.aclose()


def _cards() -> list[AgentCard]:
    return [
        AgentCard(
            agentId="search-agent",
            name="Literature Search Agent",
            description="Finds papers.",
            capabilities=[SEARCH_CAPABILITY],
            url="http://search:8101/a2a",
            healthUrl="http://search:8101/health",
        ),
        AgentCard(
            agentId="evidence-agent",
            name="Evidence Extraction Agent",
            description="Extracts evidence.",
            capabilities=[EVIDENCE_CAPABILITY],
            url="http://evidence:8102/a2a",
            healthUrl="http://evidence:8102/health",
        ),
        AgentCard(
            agentId="synthesis-agent",
            name="Research Synthesis Agent",
            description="Synthesizes evidence.",
            capabilities=[SYNTHESIS_CAPABILITY],
            url="http://synthesis:8103/a2a",
            healthUrl="http://synthesis:8103/health",
        ),
    ]


def _test_transport(include_synthesis: bool = True) -> RoutingTransport:
    cards = _cards()
    store = RegistryStore()
    for card in cards:
        if include_synthesis or card.agent_id != "synthesis-agent":
            store.register(card)
    apps: dict[str, object] = {
        "registry": create_app(store),
        "search": create_search_app(registry_url=None),
        "evidence": create_evidence_app(registry_url=None),
    }
    if include_synthesis:
        apps["synthesis"] = create_synthesis_app(registry_url=None)
    return RoutingTransport(apps)


@pytest.mark.asyncio
async def test_orchestrator_discovers_and_chains_three_agents() -> None:
    transport = _test_transport()
    async with httpx.AsyncClient(transport=transport) as client:
        orchestrator = ResearchOrchestrator("http://registry", client=client)
        result = await orchestrator.run("retrieval enterprise", top_k=2)

    assert [agent.agent_id for agent in result.agents] == [
        "search-agent",
        "evidence-agent",
        "synthesis-agent",
    ]
    assert [agent.capability for agent in result.agents] == [
        SEARCH_CAPABILITY,
        EVIDENCE_CAPABILITY,
        SYNTHESIS_CAPABILITY,
    ]
    assert [hit.paper_id for hit in result.search.hits] == ["P-001", "P-002"]
    assert [item.paper_id for item in result.evidence.evidence] == ["P-001", "P-002"]
    assert len(result.synthesis.key_findings) == 2
    assert "P-001" in result.synthesis.answer


@pytest.mark.asyncio
async def test_orchestrator_fails_when_registry_capability_is_missing() -> None:
    transport = _test_transport(include_synthesis=False)
    async with httpx.AsyncClient(transport=transport) as client:
        orchestrator = ResearchOrchestrator("http://registry", client=client)

        with pytest.raises(LookupError, match=SYNTHESIS_CAPABILITY):
            await orchestrator.run("retrieval enterprise", top_k=1)


@pytest.mark.asyncio
async def test_orchestrator_surfaces_remote_jsonrpc_errors() -> None:
    transport = _test_transport()
    async with httpx.AsyncClient(transport=transport) as client:
        orchestrator = ResearchOrchestrator("http://registry", client=client)
        card = _cards()[0]

        with pytest.raises(WorkflowError, match="search agent"):
            await orchestrator._send(
                card,
                {"task": "not-search", "question": "retrieval enterprise"},
                step="search",
            )


@pytest.mark.asyncio
async def test_orchestrator_rejects_invalid_top_k_before_network_call() -> None:
    transport = _test_transport()
    async with httpx.AsyncClient(transport=transport) as client:
        orchestrator = ResearchOrchestrator("http://registry", client=client)

        with pytest.raises(ValueError, match="top_k"):
            await orchestrator.run("retrieval enterprise", top_k=0)
