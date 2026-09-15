"""Standalone Literature Search Agent for the distributed research workflow."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import uvicorn

from a2a_research.agent_runtime import create_agent_app
from a2a_research.protocol import AgentCard
from a2a_research.research_models import (
    PaperRecord,
    SearchRequest,
    SearchHit,
    SearchResponse,
)
from a2a_research.settings import ServiceSettings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = PROJECT_ROOT / "data" / "papers.json"
LOGGER = logging.getLogger("search-agent")


def load_corpus(path: Path = CORPUS_PATH) -> list[PaperRecord]:
    """Load and validate the versioned local paper corpus."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("The paper corpus must contain a JSON array.")
    return [PaperRecord.model_validate(record) for record in raw]


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[^\W_]+", value.lower(), flags=re.UNICODE))


def score_paper(question: str, paper: PaperRecord) -> int:
    """Score one paper using transparent title, keyword and abstract weights."""

    query_tokens = _tokens(question)
    title_score = len(query_tokens & _tokens(paper.title)) * 5
    keyword_score = len(query_tokens & _tokens(" ".join(paper.keywords))) * 3
    abstract_score = len(query_tokens & _tokens(paper.abstract))
    return title_score + keyword_score + abstract_score


def search_papers(
    question: str,
    *,
    top_k: int = 3,
    corpus: Sequence[PaperRecord] | None = None,
) -> dict[str, Any]:
    """Return the highest-scoring local papers for a research question."""

    request = SearchRequest(task="search", question=question, top_k=top_k)
    if not _tokens(request.question):
        raise ValueError("The research question must contain searchable words.")

    records = load_corpus() if corpus is None else list(corpus)
    ranked = sorted(
        (
            (score_paper(request.question, paper), paper)
            for paper in records
        ),
        key=lambda item: (-item[0], item[1].paper_id),
    )
    hits = [
        SearchHit(
            paper_id=paper.paper_id,
            title=paper.title,
            authors=paper.authors,
            year=paper.year,
            score=score,
            abstract=paper.abstract,
            limitations=paper.limitations,
            source=paper.source,
        )
        for score, paper in ranked[: request.top_k]
        if score > 0
    ]
    return SearchResponse(question=request.question, hits=hits).model_dump(mode="json")


def handle_search(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an A2A task and execute the search."""

    request = SearchRequest.model_validate(payload)
    return search_papers(request.question, top_k=request.top_k)


def _settings_from_environment() -> ServiceSettings:
    values = dict(os.environ)
    values.setdefault("A2A_SERVICE_NAME", "search-agent")
    values.setdefault("A2A_PORT", "8101")
    values.setdefault("A2A_PUBLIC_URL", "http://127.0.0.1:8101/a2a")
    return ServiceSettings.from_env(values)


def _agent_card(settings: ServiceSettings) -> AgentCard:
    a2a_url = (settings.public_url or f"http://127.0.0.1:{settings.port}/a2a").rstrip("/")
    health_url = f"{a2a_url.rsplit('/', 1)[0]}/health"
    return AgentCard(
        agentId="search-agent",
        name="Literature Search Agent",
        description="Finds and ranks relevant papers in the local research corpus.",
        capabilities=["research.search"],
        url=a2a_url,
        healthUrl=health_url,
    )


def create_search_app(
    *,
    corpus: Sequence[PaperRecord] | None = None,
    registry_url: str | None = None,
    settings: ServiceSettings | None = None,
):
    """Build the app with optional dependency injection for API tests."""

    runtime_settings = settings or _settings_from_environment()
    agent_card = _agent_card(runtime_settings)

    def handler(payload: dict[str, Any]) -> dict[str, Any]:
        request = SearchRequest.model_validate(payload)
        return search_papers(
            request.question,
            top_k=request.top_k,
            corpus=corpus,
        )

    return create_agent_app(
        agent_card,
        handler,
        registry_url=registry_url,
        logger=LOGGER,
    )


_RUNTIME_SETTINGS = _settings_from_environment()
app = create_search_app(
    registry_url=_RUNTIME_SETTINGS.registry_url,
    settings=_RUNTIME_SETTINGS,
)


def main() -> None:
    """Run the search agent as a standalone process."""

    uvicorn.run(
        app,
        host=_RUNTIME_SETTINGS.host,
        port=_RUNTIME_SETTINGS.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
