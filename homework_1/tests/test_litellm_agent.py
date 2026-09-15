from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest

from litellm_agent import (
    AgentConfigurationError,
    assistant_message_payload,
    mcp_tools_to_openai_tools,
    run_react_agent,
    settings_from_env,
)


def test_settings_from_env_uses_local_defaults() -> None:
    settings = settings_from_env({})

    assert settings.api_base == "http://localhost:4000/v1"
    assert settings.api_key == "sk-homework-local-key"
    assert settings.model == "homework-model"


def test_settings_from_env_rejects_empty_values() -> None:
    with pytest.raises(AgentConfigurationError):
        settings_from_env({"LITELLM_KEY": ""})


def test_mcp_tools_are_converted_to_openai_function_schemas() -> None:
    response = SimpleNamespace(
        tools=[
            SimpleNamespace(
                name="lookup_inventory",
                description="Look up stock",
                inputSchema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            )
        ]
    )

    assert mcp_tools_to_openai_tools(response) == [
        {
            "type": "function",
            "function": {
                "name": "lookup_inventory",
                "description": "Look up stock",
                "parameters": response.tools[0].inputSchema,
            },
        }
    ]


def test_assistant_message_payload_preserves_tool_calls() -> None:
    message = SimpleNamespace(
        content=None,
        tool_calls=[
            SimpleNamespace(
                id="call-1",
                type="function",
                function=SimpleNamespace(
                    name="lookup_inventory",
                    arguments='{"query": "P-1001"}',
                ),
            )
        ],
    )

    assert assistant_message_payload(message) == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "lookup_inventory",
                    "arguments": '{"query": "P-1001"}',
                },
            }
        ],
    }


class FakeCompletions:
    def __init__(self, responses: list[object]) -> None:
        self.responses = iter(responses)
        self.requests: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.requests.append(kwargs)
        return next(self.responses)


class FakeLLMClient:
    def __init__(self, responses: list[object]) -> None:
        self.completions = FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        self.calls.append((name, arguments))
        if name == "lookup_inventory":
            return SimpleNamespace(
                isError=False,
                structuredContent={"found": True, "count": 1},
                content=[],
            )
        return SimpleNamespace(isError=False, structuredContent={"success": True}, content=[])


def test_react_loop_calls_mcp_and_records_agent_action() -> None:
    tool_call = SimpleNamespace(
        id="call-1",
        type="function",
        function=SimpleNamespace(
            name="lookup_inventory",
            arguments='{"query": "Industrial Sensor"}',
        ),
    )
    first_message = SimpleNamespace(content=None, tool_calls=[tool_call])
    final_message = SimpleNamespace(
        content="Der Bestand wurde geprüft.",
        tool_calls=None,
    )
    client = FakeLLMClient(
        [
            SimpleNamespace(choices=[SimpleNamespace(message=first_message)]),
            SimpleNamespace(choices=[SimpleNamespace(message=final_message)]),
        ]
    )
    session = FakeSession()
    logger = logging.getLogger("test.litellm_agent")

    answer = asyncio.run(
        run_react_agent(
            session=session,
            llm_client=client,
            tool_definitions=[],
            user_prompt="Prüfe den Bestand.",
            model="homework-model",
            logger=logger,
        )
    )

    assert answer == "Der Bestand wurde geprüft."
    assert [name for name, _ in session.calls] == [
        "lookup_inventory",
        "append_audit_event",
    ]
    assert session.calls[0][1] == {"query": "Industrial Sensor"}
    assert session.calls[1][1]["event_type"] == "agent_tool_call"
    assert len(client.completions.requests) == 2
    assert client.completions.requests[1]["messages"][-1]["role"] == "tool"


def test_react_loop_is_bounded() -> None:
    tool_call = SimpleNamespace(
        id="call-1",
        type="function",
        function=SimpleNamespace(name="lookup_inventory", arguments="{}"),
    )
    client = FakeLLMClient(
        [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=None, tool_calls=[tool_call])
                    )
                ]
            )
        ]
        * 2
    )

    with pytest.raises(RuntimeError, match="2 iterations"):
        asyncio.run(
            run_react_agent(
                session=FakeSession(),
                llm_client=client,
                tool_definitions=[],
                user_prompt="Laufe nicht endlos.",
                model="homework-model",
                logger=logging.getLogger("test.litellm_agent.bounded"),
                max_iterations=2,
            )
        )
