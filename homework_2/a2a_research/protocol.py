"""Small, explicit A2A-compatible message layer used by Homework 2.

The project implements the JSON-RPC ``message/send`` part of A2A that is
needed by the local multi-agent workflow. Payloads are transported in one
JSON text part so that the wire format remains easy to inspect in logs.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Literal
from uuid import uuid4

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


Role = Literal["user", "agent"]

JSON_RPC_INVALID_REQUEST = -32600
JSON_RPC_METHOD_NOT_FOUND = -32601
JSON_RPC_INVALID_PARAMS = -32602
JSON_RPC_INTERNAL_ERROR = -32603


def _new_message_id() -> str:
    return f"msg-{uuid4().hex}"


class TextPart(BaseModel):
    """A text part in the minimal A2A message representation."""

    kind: Literal["text"] = "text"
    text: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class A2AMessage(BaseModel):
    """A2A message with the standard camel-case ``messageId`` field."""

    message_id: str = Field(
        default_factory=_new_message_id,
        alias="messageId",
        min_length=1,
    )
    role: Role
    parts: list[TextPart] = Field(min_length=1)

    model_config = ConfigDict(
        alias_generator=None,
        extra="forbid",
        populate_by_name=True,
    )


class MessageSendParams(BaseModel):
    """Parameters for the A2A ``message/send`` method."""

    message: A2AMessage

    model_config = ConfigDict(extra="forbid")


class JsonRpcRequest(BaseModel):
    """JSON-RPC request accepted by every remote agent."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    method: Literal["message/send"]
    params: MessageSendParams

    model_config = ConfigDict(extra="forbid")


class JsonRpcResult(BaseModel):
    """Successful JSON-RPC result containing an agent message."""

    message: A2AMessage

    model_config = ConfigDict(extra="forbid")


class JsonRpcError(BaseModel):
    """JSON-RPC error payload."""

    code: int
    message: str
    data: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class JsonRpcResponse(BaseModel):
    """A response with exactly one of ``result`` or ``error``."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None
    result: JsonRpcResult | None = None
    error: JsonRpcError | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_result_or_error(self) -> JsonRpcResponse:
        if (self.result is None) == (self.error is None):
            raise ValueError("Exactly one of result or error must be provided.")
        return self


class AgentCard(BaseModel):
    """Public metadata used by the registry for dynamic agent lookup."""

    agent_id: str = Field(alias="agentId", min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    url: AnyHttpUrl
    health_url: AnyHttpUrl | None = Field(default=None, alias="healthUrl")
    version: str = "0.1.0"
    protocol: str = "a2a-jsonrpc-message-send"

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )


def encode_payload(payload: Mapping[str, Any]) -> str:
    """Encode a structured task payload into a stable JSON text part."""

    return json.dumps(
        dict(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def decode_payload(message: A2AMessage) -> dict[str, Any]:
    """Decode the single JSON text part used by this project."""

    if len(message.parts) != 1 or message.parts[0].kind != "text":
        raise ValueError("A2A payload must contain exactly one text part.")

    try:
        payload = json.loads(message.parts[0].text)
    except json.JSONDecodeError as exc:
        raise ValueError("A2A text part must contain valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("A2A JSON payload must be an object.")
    return payload


def make_request(request_id: str | int, payload: Mapping[str, Any]) -> JsonRpcRequest:
    """Create a JSON-RPC ``message/send`` request for a remote agent."""

    return JsonRpcRequest(
        id=request_id,
        method="message/send",
        params={
            "message": A2AMessage(
                role="user",
                parts=[TextPart(text=encode_payload(payload))],
            )
        },
    )


def make_success_response(
    request_id: str | int | None,
    payload: Mapping[str, Any],
) -> JsonRpcResponse:
    """Create a successful JSON-RPC response from a structured payload."""

    return JsonRpcResponse(
        id=request_id,
        result={
            "message": A2AMessage(
                role="agent",
                parts=[TextPart(text=encode_payload(payload))],
            )
        },
    )


def make_error_response(
    request_id: str | int | None,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> JsonRpcResponse:
    """Create a JSON-RPC error response without exposing a traceback."""

    return JsonRpcResponse(
        id=request_id,
        error=JsonRpcError(code=code, message=message, data=data),
    )
