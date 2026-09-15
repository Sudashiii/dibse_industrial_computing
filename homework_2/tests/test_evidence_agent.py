from __future__ import annotations

from fastapi.testclient import TestClient

from a2a_research.evidence_agent import create_evidence_app, extract_evidence
from a2a_research.protocol import (
    JSON_RPC_INVALID_PARAMS,
    JsonRpcResponse,
    decode_payload,
    make_request,
)
from a2a_research.research_models import SearchHit
from a2a_research.search_agent import search_papers


def _search_hits() -> list[dict[str, object]]:
    result = search_papers("retrieval enterprise", top_k=2)
    return result["hits"]


def test_extract_evidence_preserves_search_provenance() -> None:
    hits = _search_hits()

    result = extract_evidence(
        {
            "task": "extract",
            "question": "retrieval enterprise",
            "hits": hits,
        }
    )

    assert result["task"] == "evidence.result"
    assert len(result["evidence"]) == len(hits)
    first = result["evidence"][0]
    assert first["paper_id"] == hits[0]["paper_id"]
    assert first["title"] == hits[0]["title"]
    assert first["source"] == hits[0]["source"]
    assert first["limitations"] == hits[0]["limitations"]
    assert first["claim"] == hits[0]["abstract"]
    assert first["evidence_quote"] == hits[0]["abstract"]


def test_extract_evidence_returns_empty_result_for_empty_hits() -> None:
    result = extract_evidence(
        {
            "task": "extract",
            "question": "a question without matching papers",
            "hits": [],
        }
    )

    assert result["evidence"] == []


def test_search_hit_validation_rejects_incomplete_handoff() -> None:
    try:
        SearchHit.model_validate({"paper_id": "P-001"})
    except ValueError:
        pass
    else:
        raise AssertionError("An incomplete search hit must not cross the hand-off.")


def test_a2a_endpoint_returns_evidence_result() -> None:
    client = TestClient(create_evidence_app(registry_url=None))
    request = make_request(
        "request-1",
        {
            "task": "extract",
            "question": "retrieval enterprise",
            "hits": _search_hits(),
        },
    )

    response = client.post(
        "/a2a",
        json=request.model_dump(by_alias=True, mode="json"),
    )

    assert response.status_code == 200
    rpc_response = JsonRpcResponse.model_validate(response.json())
    assert rpc_response.result is not None
    payload = decode_payload(rpc_response.result.message)
    assert payload["task"] == "evidence.result"
    assert len(payload["evidence"]) == 2


def test_a2a_endpoint_returns_jsonrpc_error_for_wrong_task() -> None:
    client = TestClient(create_evidence_app(registry_url=None))
    request = make_request(
        "request-2",
        {"task": "search", "question": "retrieval enterprise", "hits": []},
    )

    response = client.post(
        "/a2a",
        json=request.model_dump(by_alias=True, mode="json"),
    )

    rpc_response = JsonRpcResponse.model_validate(response.json())
    assert rpc_response.error is not None
    assert rpc_response.error.code == JSON_RPC_INVALID_PARAMS


def test_evidence_agent_card_and_health_are_exposed() -> None:
    client = TestClient(create_evidence_app(registry_url=None))

    card_response = client.get("/.well-known/agent-card.json")
    health_response = client.get("/health")

    assert card_response.status_code == 200
    assert card_response.json()["agentId"] == "evidence-agent"
    assert card_response.json()["capabilities"] == ["research.extract_evidence"]
    assert health_response.json()["agent_id"] == "evidence-agent"
