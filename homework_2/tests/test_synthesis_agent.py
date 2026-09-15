from __future__ import annotations

from fastapi.testclient import TestClient

from a2a_research.evidence_agent import extract_evidence
from a2a_research.protocol import (
    JSON_RPC_INVALID_PARAMS,
    JsonRpcResponse,
    decode_payload,
    make_request,
)
from a2a_research.search_agent import search_papers
from a2a_research.synthesis_agent import create_synthesis_app, synthesize_answer


def _evidence() -> list[dict[str, object]]:
    search_result = search_papers("retrieval enterprise", top_k=2)
    return extract_evidence(
        {
            "task": "extract",
            "question": search_result["question"],
            "hits": search_result["hits"],
        }
    )["evidence"]


def test_synthesis_is_grounded_in_supplied_evidence() -> None:
    evidence = _evidence()

    result = synthesize_answer(
        {
            "task": "synthesize",
            "question": "retrieval enterprise",
            "evidence": evidence,
        }
    )

    assert result["task"] == "synthesis.result"
    assert len(result["key_findings"]) == 2
    assert result["key_findings"][0].startswith("[P-001]")
    assert "P-001" in result["answer"]
    assert "P-002" in result["answer"]
    assert result["sources"] == ["local-demo-corpus"]
    assert result["limitations"]


def test_synthesis_handles_empty_evidence() -> None:
    result = synthesize_answer(
        {
            "task": "synthesize",
            "question": "a question without matching papers",
            "evidence": [],
        }
    )

    assert result["answer"] == "No evidence was supplied for this research question."
    assert result["key_findings"] == []
    assert result["limitations"] == []
    assert result["sources"] == []


def test_a2a_endpoint_returns_synthesis_result() -> None:
    client = TestClient(create_synthesis_app(registry_url=None))
    request = make_request(
        "request-1",
        {
            "task": "synthesize",
            "question": "retrieval enterprise",
            "evidence": _evidence(),
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
    assert payload["task"] == "synthesis.result"
    assert len(payload["key_findings"]) == 2


def test_a2a_endpoint_returns_jsonrpc_error_for_wrong_task() -> None:
    client = TestClient(create_synthesis_app(registry_url=None))
    request = make_request(
        "request-2",
        {"task": "extract", "question": "retrieval enterprise", "evidence": []},
    )

    response = client.post(
        "/a2a",
        json=request.model_dump(by_alias=True, mode="json"),
    )

    rpc_response = JsonRpcResponse.model_validate(response.json())
    assert rpc_response.error is not None
    assert rpc_response.error.code == JSON_RPC_INVALID_PARAMS


def test_synthesis_agent_card_and_health_are_exposed() -> None:
    client = TestClient(create_synthesis_app(registry_url=None))

    card_response = client.get("/.well-known/agent-card.json")
    health_response = client.get("/health")

    assert card_response.status_code == 200
    assert card_response.json()["agentId"] == "synthesis-agent"
    assert card_response.json()["capabilities"] == ["research.synthesize"]
    assert health_response.json()["agent_id"] == "synthesis-agent"
