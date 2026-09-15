"""Reusable FastAPI runtime for the standalone A2A worker processes."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI

from a2a_research.protocol import (
    JSON_RPC_INTERNAL_ERROR,
    JSON_RPC_INVALID_PARAMS,
    AgentCard,
    JsonRpcRequest,
    JsonRpcResponse,
    decode_payload,
    make_error_response,
    make_success_response,
)
from a2a_research.registry_client import RegistryClient


AgentHandler = Callable[
    [dict[str, Any]],
    Mapping[str, Any] | Awaitable[Mapping[str, Any]],
]


async def register_with_retry(
    registry_url: str,
    card: AgentCard,
    *,
    attempts: int = 20,
    delay_seconds: float = 0.5,
    logger: logging.Logger | None = None,
) -> AgentCard:
    """Register a worker while the registry container is starting up."""

    if attempts < 1:
        raise ValueError("attempts must be at least one.")
    if delay_seconds < 0:
        raise ValueError("delay_seconds must not be negative.")

    log = logger or logging.getLogger(__name__)
    async with RegistryClient(registry_url, timeout=3.0) as client:
        for attempt in range(1, attempts + 1):
            try:
                registered_card = await client.register(card)
                log.info(
                    "REGISTERED agent_id=%s registry=%s attempt=%d",
                    registered_card.agent_id,
                    registry_url,
                    attempt,
                )
                return registered_card
            except httpx.HTTPError as exc:
                if attempt == attempts:
                    raise RuntimeError(
                        f"Could not register '{card.agent_id}' after {attempts} attempts."
                    ) from exc
                log.warning(
                    "REGISTRY_RETRY agent_id=%s attempt=%d/%d error=%s",
                    card.agent_id,
                    attempt,
                    attempts,
                    exc,
                )
                await asyncio.sleep(delay_seconds)

    raise RuntimeError("Registry registration ended unexpectedly.")


def create_agent_app(
    card: AgentCard,
    handler: AgentHandler,
    *,
    registry_url: str | None = None,
    logger: logging.Logger | None = None,
) -> FastAPI:
    """Create the health, agent-card and A2A routes for one worker."""

    log = logger or logging.getLogger(card.agent_id)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if registry_url:
            await register_with_retry(registry_url, card, logger=log)
        yield

    app = FastAPI(
        title=card.name,
        version=card.version,
        description=card.description,
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "agent_id": card.agent_id,
            "service": card.name,
        }

    @app.get("/.well-known/agent-card.json", response_model=AgentCard)
    def agent_card() -> AgentCard:
        return card

    @app.post("/a2a", response_model=JsonRpcResponse)
    async def message_send(request: JsonRpcRequest) -> JsonRpcResponse:
        try:
            payload = decode_payload(request.params.message)
            result = handler(payload)
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, Mapping):
                raise ValueError("Agent handler must return a JSON object.")
            return make_success_response(request.id, result)
        except ValueError as exc:
            return make_error_response(
                request.id,
                JSON_RPC_INVALID_PARAMS,
                str(exc),
            )
        except Exception:
            log.exception("A2A_HANDLER_FAILED agent_id=%s", card.agent_id)
            return make_error_response(
                request.id,
                JSON_RPC_INTERNAL_ERROR,
                "Agent handler failed.",
            )

    return app
