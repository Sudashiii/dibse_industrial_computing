"""Standalone Evidence Extraction Agent for the research workflow."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

import uvicorn

from a2a_research.agent_runtime import create_agent_app
from a2a_research.protocol import AgentCard
from a2a_research.research_models import (
    EvidenceRequest,
    EvidenceResponse,
    EvidenceItem,
)
from a2a_research.settings import ServiceSettings


LOGGER = logging.getLogger("evidence-agent")


def extract_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Turn supplied search hits into traceable evidence items.

    This worker does not perform another search and does not invent claims.
    Each claim and quote is taken from the hit's validated abstract, while
    provenance and limitations are carried through unchanged.
    """

    request = EvidenceRequest.model_validate(payload)
    evidence = [
        EvidenceItem(
            paper_id=hit.paper_id,
            title=hit.title,
            claim=hit.abstract.strip(),
            evidence_quote=hit.abstract,
            limitations=list(hit.limitations),
            source=hit.source,
        )
        for hit in request.hits
    ]
    return EvidenceResponse(
        question=request.question,
        evidence=evidence,
    ).model_dump(mode="json")


def _settings_from_environment() -> ServiceSettings:
    values = dict(os.environ)
    values.setdefault("A2A_SERVICE_NAME", "evidence-agent")
    values.setdefault("A2A_PORT", "8102")
    values.setdefault("A2A_PUBLIC_URL", "http://127.0.0.1:8102/a2a")
    return ServiceSettings.from_env(values)


def _agent_card(settings: ServiceSettings) -> AgentCard:
    a2a_url = (settings.public_url or f"http://127.0.0.1:{settings.port}/a2a").rstrip("/")
    health_url = f"{a2a_url.rsplit('/', 1)[0]}/health"
    return AgentCard(
        agentId="evidence-agent",
        name="Evidence Extraction Agent",
        description="Extracts traceable claims and quotes from supplied research hits.",
        capabilities=["research.extract_evidence"],
        url=a2a_url,
        healthUrl=health_url,
    )


def create_evidence_app(
    *,
    registry_url: str | None = None,
    settings: ServiceSettings | None = None,
):
    """Build the app with optional dependency injection for API tests."""

    runtime_settings = settings or _settings_from_environment()
    agent_card = _agent_card(runtime_settings)

    return create_agent_app(
        agent_card,
        extract_evidence,
        registry_url=registry_url,
        logger=LOGGER,
    )


_RUNTIME_SETTINGS = _settings_from_environment()
app = create_evidence_app(
    registry_url=_RUNTIME_SETTINGS.registry_url,
    settings=_RUNTIME_SETTINGS,
)


def main() -> None:
    """Run the evidence extraction agent as a standalone process."""

    uvicorn.run(
        app,
        host=_RUNTIME_SETTINGS.host,
        port=_RUNTIME_SETTINGS.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
