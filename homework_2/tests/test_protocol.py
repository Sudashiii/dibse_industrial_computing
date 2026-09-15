from __future__ import annotations

import pytest
from pydantic import ValidationError

from a2a_research.protocol import (
    A2AMessage,
    AgentCard,
    JsonRpcResponse,
    TextPart,
    decode_payload,
    make_error_response,
    make_request,
    make_success_response,
)


def test_payload_round_trip_uses_one_json_text_part() -> None:
    request = make_request(
        "request-1",
        {"task": "search", "question": "RAG", "top_k": 3},
    )

    assert request.method == "message/send"
    assert request.params.message.role == "user"
    assert decode_payload(request.params.message) == {
        "question": "RAG",
        "task": "search",
        "top_k": 3,
    }

    wire = request.model_dump(by_alias=True, mode="json")
    assert wire["params"]["message"]["messageId"].startswith("msg-")
    assert wire["params"]["message"]["parts"][0]["kind"] == "text"


def test_success_response_contains_agent_message() -> None:
    response = make_success_response("request-1", {"task": "search.result", "hits": []})

    assert response.result is not None
    assert response.result.message.role == "agent"
    assert decode_payload(response.result.message) == {
        "hits": [],
        "task": "search.result",
    }


def test_error_response_contains_no_result() -> None:
    response = make_error_response("request-1", -32602, "Invalid task payload.")

    assert response.result is None
    assert response.error is not None
    assert response.error.code == -32602


def test_jsonrpc_response_requires_exactly_one_result_or_error() -> None:
    with pytest.raises(ValidationError):
        JsonRpcResponse(id="request-1")

    with pytest.raises(ValidationError):
        JsonRpcResponse(
            id="request-1",
            result={"message": {"role": "agent", "parts": [{"text": "{}"}]}},
            error={"code": -32600, "message": "also invalid"},
        )


@pytest.mark.parametrize(
    "message",
    [
        A2AMessage(role="user", parts=[TextPart(text="not-json")]),
        A2AMessage(
            role="user",
            parts=[TextPart(text='["an", "array"]')],
        ),
        A2AMessage(
            role="user",
            parts=[TextPart(text="{}"), TextPart(text="{}")],
        ),
    ],
)
def test_decode_payload_rejects_invalid_transport_payload(message: A2AMessage) -> None:
    with pytest.raises(ValueError):
        decode_payload(message)


def test_agent_card_supports_wire_aliases() -> None:
    card = AgentCard(
        agentId="search-agent",
        name="Literature Search Agent",
        description="Finds relevant papers in the local corpus.",
        capabilities=["research.search"],
        url="http://search-agent:8101/a2a",
        healthUrl="http://search-agent:8101/health",
    )

    wire = card.model_dump(by_alias=True, mode="json")
    assert wire["agentId"] == "search-agent"
    assert wire["healthUrl"] == "http://search-agent:8101/health"
