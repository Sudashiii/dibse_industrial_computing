"""Standalone Synthesis Agent for the distributed research workflow."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

import uvicorn

from a2a_research.agent_runtime import create_agent_app
from a2a_research.protocol import AgentCard
from a2a_research.research_models import (
    SynthesisRequest,
    SynthesisResponse,
)
from a2a_research.settings import ServiceSettings


LOGGER = logging.getLogger("synthesis-agent")


def _unique(values: list[str]) -> list[str]:
    """Keep values in first-seen order while removing duplicates and blanks."""

    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def synthesize_answer(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Compose a concise answer using only evidence from the previous agent.

    The implementation is intentionally deterministic for reproducible
    execution logs. It does not perform a new search or add unsupported facts.
    """

    request = SynthesisRequest.model_validate(payload)
    if not request.evidence:
        return SynthesisResponse(
            question=request.question,
            answer="No evidence was supplied for this research question.",
            key_findings=[],
            limitations=[],
            sources=[],
        ).model_dump(mode="json")

    key_findings = [
        f"[{item.paper_id}] {item.claim.strip()}"
        for item in request.evidence
    ]
    limitations = _unique(
        [limitation for item in request.evidence for limitation in item.limitations]
    )
    sources = _unique([item.source for item in request.evidence])
    answer = (
        f"Based on {len(request.evidence)} source(s), the available evidence indicates: "
        + " ".join(key_findings)
    )

    return SynthesisResponse(
        question=request.question,
        answer=answer,
        key_findings=key_findings,
        limitations=limitations,
        sources=sources,
    ).model_dump(mode="json")


def _settings_from_environment() -> ServiceSettings:
    values = dict(os.environ)
    values.setdefault("A2A_SERVICE_NAME", "synthesis-agent")
    values.setdefault("A2A_PORT", "8103")
    values.setdefault("A2A_PUBLIC_URL", "http://127.0.0.1:8103/a2a")
    return ServiceSettings.from_env(values)


def _agent_card(settings: ServiceSettings) -> AgentCard:
    a2a_url = (settings.public_url or f"http://127.0.0.1:{settings.port}/a2a").rstrip("/")
    health_url = f"{a2a_url.rsplit('/', 1)[0]}/health"
    return AgentCard(
        agentId="synthesis-agent",
        name="Research Synthesis Agent",
        description="Builds an evidence-grounded answer from supplied research evidence.",
        capabilities=["research.synthesize"],
        url=a2a_url,
        healthUrl=health_url,
    )


def create_synthesis_app(
    *,
    registry_url: str | None = None,
    settings: ServiceSettings | None = None,
):
    """Build the app with optional dependency injection for API tests."""

    runtime_settings = settings or _settings_from_environment()
    agent_card = _agent_card(runtime_settings)

    return create_agent_app(
        agent_card,
        synthesize_answer,
        registry_url=registry_url,
        logger=LOGGER,
    )


_RUNTIME_SETTINGS = _settings_from_environment()
app = create_synthesis_app(
    registry_url=_RUNTIME_SETTINGS.registry_url,
    settings=_RUNTIME_SETTINGS,
)


def main() -> None:
    """Run the synthesis agent as a standalone process."""

    uvicorn.run(
        app,
        host=_RUNTIME_SETTINGS.host,
        port=_RUNTIME_SETTINGS.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
