from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from a2a_research.protocol import (
    JSON_RPC_INVALID_PARAMS,
    JsonRpcResponse,
    decode_payload,
    make_request,
)
from a2a_research.research_models import PaperRecord
from a2a_research.search_agent import (
    CORPUS_PATH,
    create_search_app,
    load_corpus,
    score_paper,
    search_papers,
)


def test_load_corpus_contains_versioned_demo_records() -> None:
    corpus = load_corpus(CORPUS_PATH)

    assert len(corpus) == 6
    assert corpus[0].paper_id == "P-001"
    assert "retrieval" in corpus[0].keywords


def test_score_prefers_title_and_keyword_matches() -> None:
    paper = PaperRecord(
        paper_id="P-TEST",
        title="Retrieval Systems",
        authors=["Author"],
        year=2024,
        keywords=["enterprise"],
        abstract="A short unrelated abstract.",
        source="test",
    )

    assert score_paper("retrieval enterprise", paper) == 8


def test_search_returns_ranked_hits_and_preserves_question() -> None:
    result = search_papers(
        "Welche Vorteile und Grenzen haben Retrieval-Augmented-Generation-Systeme "
        "für wissensintensive Unternehmensanwendungen?",
        top_k=3,
    )

    assert result["task"] == "search.result"
    assert result["question"].startswith("Welche Vorteile")
    assert [hit["paper_id"] for hit in result["hits"]] == ["P-001", "P-002", "P-003"]
    assert result["hits"][0]["score"] >= result["hits"][1]["score"]


def test_search_returns_empty_hits_when_nothing_matches() -> None:
    result = search_papers("quantum archaeology on Mars", top_k=3)

    assert result["hits"] == []


def test_search_rejects_question_without_searchable_words() -> None:
    with pytest.raises(ValueError, match="searchable words"):
        search_papers("---", top_k=3)


def test_a2a_endpoint_returns_search_result() -> None:
    client = TestClient(create_search_app(registry_url=None))
    request = make_request(
        "request-1",
        {"task": "search", "question": "retrieval enterprise", "top_k": 2},
    )

    response = client.post(
        "/a2a",
        json=request.model_dump(by_alias=True, mode="json"),
    )

    assert response.status_code == 200
    rpc_response = JsonRpcResponse.model_validate(response.json())
    assert rpc_response.result is not None
    payload = decode_payload(rpc_response.result.message)
    assert payload["task"] == "search.result"
    assert len(payload["hits"]) == 2


def test_a2a_endpoint_returns_jsonrpc_error_for_wrong_task() -> None:
    client = TestClient(create_search_app(registry_url=None))
    request = make_request(
        "request-2",
        {"task": "extract", "question": "retrieval enterprise"},
    )

    response = client.post(
        "/a2a",
        json=request.model_dump(by_alias=True, mode="json"),
    )

    rpc_response = JsonRpcResponse.model_validate(response.json())
    assert rpc_response.error is not None
    assert rpc_response.error.code == JSON_RPC_INVALID_PARAMS


def test_agent_card_and_health_are_exposed() -> None:
    client = TestClient(create_search_app(registry_url=None))

    card_response = client.get("/.well-known/agent-card.json")
    health_response = client.get("/health")

    assert card_response.status_code == 200
    assert card_response.json()["agentId"] == "search-agent"
    assert card_response.json()["capabilities"] == ["research.search"]
    assert health_response.json()["status"] == "ok"
