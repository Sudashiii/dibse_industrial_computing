"""Dynamic A2A orchestrator for the distributed research workflow."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from collections.abc import Sequence
from types import TracebackType
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from a2a_research.protocol import (
    AgentCard,
    JsonRpcResponse,
    decode_payload,
    make_request,
)
from a2a_research.registry_client import RegistryClient
from a2a_research.research_models import (
    EvidenceRequest,
    EvidenceResponse,
    SearchRequest,
    SearchResponse,
    SynthesisRequest,
    SynthesisResponse,
)


SEARCH_CAPABILITY = "research.search"
EVIDENCE_CAPABILITY = "research.extract_evidence"
SYNTHESIS_CAPABILITY = "research.synthesize"
DEFAULT_REGISTRY_URL = "http://127.0.0.1:8000"
LOGGER = logging.getLogger("research-orchestrator")


class WorkflowError(RuntimeError):
    """Raised when a remote workflow step cannot return a valid result."""


class DiscoveredAgent(BaseModel):
    """The registry metadata used for one workflow invocation."""

    capability: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    url: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class WorkflowResult(BaseModel):
    """Complete, inspectable output of the three-agent workflow."""

    question: str = Field(min_length=3)
    agents: list[DiscoveredAgent] = Field(min_length=3)
    search: SearchResponse
    evidence: EvidenceResponse
    synthesis: SynthesisResponse

    model_config = ConfigDict(extra="forbid")


class ResearchOrchestrator:
    """Discover and call each research agent through the registry.

    Agent URLs are never configured in the workflow code. Each step resolves
    its required capability immediately before calling the remote service.
    """

    def __init__(
        self,
        registry_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None
        self._registry = RegistryClient(registry_url, client=self._client)
        self._logger = logger or LOGGER

    async def __aenter__(self) -> ResearchOrchestrator:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the HTTP client when the orchestrator created it."""

        if self._owns_client:
            await self._client.aclose()

    async def run(self, question: str, *, top_k: int = 3) -> WorkflowResult:
        """Execute Search → Evidence → Synthesis using dynamic lookup."""

        normalized_question = question.strip()
        search_request = SearchRequest(
            task="search",
            question=normalized_question,
            top_k=top_k,
        )

        discovered: list[DiscoveredAgent] = []

        search_card = await self._discover(SEARCH_CAPABILITY)
        discovered.append(self._discovered_agent(SEARCH_CAPABILITY, search_card))
        search_payload = await self._send(
            search_card,
            search_request.model_dump(mode="json"),
            step="search",
        )
        search_result = SearchResponse.model_validate(search_payload)

        evidence_card = await self._discover(EVIDENCE_CAPABILITY)
        discovered.append(self._discovered_agent(EVIDENCE_CAPABILITY, evidence_card))
        evidence_request = EvidenceRequest(
            task="extract",
            question=search_result.question,
            hits=search_result.hits,
        )
        evidence_payload = await self._send(
            evidence_card,
            evidence_request.model_dump(mode="json"),
            step="evidence",
        )
        evidence_result = EvidenceResponse.model_validate(evidence_payload)

        synthesis_card = await self._discover(SYNTHESIS_CAPABILITY)
        discovered.append(
            self._discovered_agent(SYNTHESIS_CAPABILITY, synthesis_card)
        )
        synthesis_request = SynthesisRequest(
            task="synthesize",
            question=evidence_result.question,
            evidence=evidence_result.evidence,
        )
        synthesis_payload = await self._send(
            synthesis_card,
            synthesis_request.model_dump(mode="json"),
            step="synthesis",
        )
        synthesis_result = SynthesisResponse.model_validate(synthesis_payload)

        self._logger.info(
            "WORKFLOW_COMPLETED question=%r agents=%s findings=%d",
            normalized_question,
            ",".join(agent.agent_id for agent in discovered),
            len(synthesis_result.key_findings),
        )
        return WorkflowResult(
            question=normalized_question,
            agents=discovered,
            search=search_result,
            evidence=evidence_result,
            synthesis=synthesis_result,
        )

    async def _discover(self, capability: str) -> AgentCard:
        self._logger.info("REGISTRY_LOOKUP capability=%s", capability)
        card = await self._registry.find_agent(capability)
        self._logger.info(
            "AGENT_SELECTED capability=%s agent_id=%s url=%s",
            capability,
            card.agent_id,
            card.url,
        )
        return card

    async def _send(
        self,
        card: AgentCard,
        payload: dict[str, Any],
        *,
        step: str,
    ) -> dict[str, Any]:
        request = make_request(f"workflow-{step}", payload)
        self._logger.info("A2A_CALL step=%s agent_id=%s", step, card.agent_id)
        try:
            response = await self._client.post(
                str(card.url),
                json=request.model_dump(by_alias=True, mode="json"),
            )
            response.raise_for_status()
            rpc_response = JsonRpcResponse.model_validate(response.json())
            if rpc_response.error is not None:
                raise WorkflowError(
                    f"{step} agent '{card.agent_id}' returned JSON-RPC "
                    f"error {rpc_response.error.code}: {rpc_response.error.message}"
                )
            if rpc_response.result is None:
                raise WorkflowError(
                    f"{step} agent '{card.agent_id}' returned no result."
                )
            return decode_payload(rpc_response.result.message)
        except WorkflowError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise WorkflowError(
                f"{step} agent '{card.agent_id}' returned an invalid response: {exc}"
            ) from exc

    @staticmethod
    def _discovered_agent(capability: str, card: AgentCard) -> DiscoveredAgent:
        return DiscoveredAgent(
            capability=capability,
            agent_id=card.agent_id,
            url=str(card.url),
        )


async def run_workflow(
    question: str,
    *,
    registry_url: str = DEFAULT_REGISTRY_URL,
    top_k: int = 3,
) -> WorkflowResult:
    """Run one workflow with an internally managed HTTP client."""

    async with ResearchOrchestrator(registry_url) as orchestrator:
        return await orchestrator.run(question, top_k=top_k)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the distributed A2A literature research workflow."
    )
    parser.add_argument(
        "--question",
        required=True,
        help="Research question passed to the Search Agent.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Maximum number of search hits to pass downstream (default: 3).",
    )
    parser.add_argument(
        "--registry-url",
        default=os.getenv("A2A_REGISTRY_URL", DEFAULT_REGISTRY_URL),
        help="Registry base URL (default: A2A_REGISTRY_URL or localhost:8000).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for a complete workflow run."""

    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = asyncio.run(
        run_workflow(
            args.question,
            registry_url=args.registry_url,
            top_k=args.top_k,
        )
    )
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
