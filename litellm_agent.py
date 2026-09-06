"""Run a local ReAct agent that uses the MCP tools through LiteLLM."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

from demo_client import configure_logging, format_tool_result


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "litellm_run.log"
DEFAULT_MAX_ITERATIONS = 8
DEFAULT_API_BASE = "http://localhost:4000/v1"
DEFAULT_API_KEY = "sk-homework-local-key"
DEFAULT_MODEL = "homework-model"

SYSTEM_PROMPT = """
Du bist ein lokaler ReAct-Agent für einen industriellen Produktkatalog.
Arbeite in kurzen, nachvollziehbaren Schritten: Verwende die MCP-Tools, wenn
Informationen aus dem Bestand, eine Rabattberechnung oder ein Audit-Eintrag
benötigt werden. Für Bestandsfragen verwendest du lookup_inventory, für
Rabatte calculate_tiered_discount und für explizite Audit-Einträge
append_audit_event. Wenn du zuerst lookup_inventory aufrufst, übernimm den
zurückgegebenen unit_price exakt in calculate_tiered_discount. Verwende nie
0 als Platzhalter für einen unbekannten Preis. Beende die Bearbeitung mit
einer kurzen Antwort auf Deutsch. Gib keine versteckten Gedankengänge aus;
fasse nur die relevanten Ergebnisse und die verwendeten Aktionen zusammen.
""".strip()


class AgentConfigurationError(ValueError):
    """Raised when the local LiteLLM configuration is invalid."""


@dataclass(frozen=True)
class AgentSettings:
    """Settings required for the OpenAI-compatible LiteLLM endpoint."""

    api_base: str
    api_key: str
    model: str


def settings_from_env(env: Mapping[str, str] | None = None) -> AgentSettings:
    """Read LiteLLM settings without exposing secret values in logs."""

    values = os.environ if env is None else env
    api_base = values.get("LITELLM_API_BASE", DEFAULT_API_BASE).strip()
    api_key = values.get("LITELLM_KEY", DEFAULT_API_KEY).strip()
    model = values.get("LITELLM_DEFAULT_MODEL", DEFAULT_MODEL).strip()

    if not api_base:
        raise AgentConfigurationError("LITELLM_API_BASE darf nicht leer sein.")
    if not api_key:
        raise AgentConfigurationError("LITELLM_KEY darf nicht leer sein.")
    if not model:
        raise AgentConfigurationError("LITELLM_DEFAULT_MODEL darf nicht leer sein.")

    return AgentSettings(api_base=api_base.rstrip("/"), api_key=api_key, model=model)


def _field(value: Any, name: str, default: Any = None) -> Any:
    """Read a field from either an SDK model or a plain dictionary."""

    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _plain_schema(schema: Any) -> dict[str, Any]:
    if isinstance(schema, Mapping):
        return dict(schema)

    model_dump = getattr(schema, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(exclude_none=True)
        if isinstance(dumped, Mapping):
            return dict(dumped)

    return {"type": "object", "properties": {}}


def mcp_tools_to_openai_tools(tools_response: Any) -> list[dict[str, Any]]:
    """Convert an MCP ``list_tools`` response to Chat Completions schemas."""

    definitions: list[dict[str, Any]] = []
    for tool in getattr(tools_response, "tools", []):
        input_schema = _field(tool, "inputSchema")
        if input_schema is None:
            input_schema = _field(tool, "input_schema")
        if input_schema is None:
            input_schema = _field(tool, "parameters")

        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": str(_field(tool, "name", "")),
                    "description": str(_field(tool, "description", "") or ""),
                    "parameters": _plain_schema(input_schema),
                },
            }
        )

    return definitions


def _tool_call_payload(tool_call: Any) -> dict[str, Any]:
    """Convert one SDK tool call to the assistant-message wire format."""

    function = _field(tool_call, "function", {})
    arguments = _field(function, "arguments", "{}")
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments, ensure_ascii=False)

    return {
        "id": str(_field(tool_call, "id", "")),
        "type": str(_field(tool_call, "type", "function")),
        "function": {
            "name": str(_field(function, "name", "")),
            "arguments": arguments,
        },
    }


def assistant_message_payload(message: Any) -> dict[str, Any]:
    """Keep only valid assistant fields when continuing a tool-call turn."""

    tool_calls = list(_field(message, "tool_calls", []) or [])
    return {
        "role": "assistant",
        "content": _field(message, "content"),
        **(
            {"tool_calls": [_tool_call_payload(call) for call in tool_calls]}
            if tool_calls
            else {}
        ),
    }


def _parse_tool_arguments(tool_call: Any) -> dict[str, Any]:
    function = _field(tool_call, "function", {})
    raw_arguments = _field(function, "arguments", "{}")

    if isinstance(raw_arguments, str):
        arguments = json.loads(raw_arguments or "{}")
    elif isinstance(raw_arguments, Mapping):
        arguments = dict(raw_arguments)
    else:
        raise ValueError("Tool arguments must be a JSON object.")

    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must decode to a JSON object.")
    return arguments


def _json_for_log(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


async def _audit_agent_action(
    session: ClientSession,
    logger: logging.Logger,
    tool_name: str,
    arguments: dict[str, Any],
    success: bool,
) -> None:
    """Record agent actions without recursively auditing the audit tool."""

    if tool_name == "append_audit_event":
        return

    audit_arguments = {
        "event_type": "agent_tool_call",
        "message": f"ReAct agent called MCP tool '{tool_name}'",
        "details": {
            "tool_name": tool_name,
            "arguments": arguments,
            "success": success,
        },
    }
    try:
        audit_result = await session.call_tool("append_audit_event", arguments=audit_arguments)
        if getattr(audit_result, "isError", False):
            logger.warning("AUDIT_FAILED tool=%s", tool_name)
    except Exception as exc:  # pragma: no cover - depends on an external MCP session
        logger.warning("AUDIT_FAILED tool=%s error=%s", tool_name, exc)


async def run_react_agent(
    session: ClientSession,
    llm_client: Any,
    tool_definitions: Sequence[dict[str, Any]],
    user_prompt: str,
    model: str,
    logger: logging.Logger,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> str:
    """Execute a bounded ReAct loop using the local MCP session."""

    if not user_prompt.strip():
        raise ValueError("Der Agent-Prompt darf nicht leer sein.")
    if max_iterations < 1:
        raise ValueError("max_iterations muss mindestens 1 sein.")

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt.strip()},
    ]
    logger.info("PROMPT prompt=%s", user_prompt.strip())

    for iteration in range(1, max_iterations + 1):
        logger.info("LLM_REQUEST iteration=%d", iteration)
        response = await llm_client.chat.completions.create(
            model=model,
            messages=list(messages),
            tools=list(tool_definitions),
            tool_choice="auto",
        )

        choices = _field(response, "choices", []) or []
        if not choices:
            raise RuntimeError("LiteLLM returned no completion choices.")

        assistant_message = _field(choices[0], "message")
        if assistant_message is None:
            raise RuntimeError("LiteLLM returned no assistant message.")

        tool_calls = list(_field(assistant_message, "tool_calls", []) or [])
        messages.append(assistant_message_payload(assistant_message))

        if not tool_calls:
            final_answer = _field(assistant_message, "content")
            if not final_answer:
                raise RuntimeError("LiteLLM returned neither text nor tool calls.")
            logger.info("FINAL answer=%s", " ".join(str(final_answer).split()))
            return str(final_answer)

        for call_index, tool_call in enumerate(tool_calls, start=1):
            function = _field(tool_call, "function", {})
            tool_name = str(_field(function, "name", ""))
            tool_call_id = str(_field(tool_call, "id", f"call-{iteration}-{call_index}"))
            arguments: dict[str, Any] = {}

            try:
                arguments = _parse_tool_arguments(tool_call)
                logger.info(
                    "ACTION iteration=%d tool=%s arguments=%s",
                    iteration,
                    tool_name,
                    _json_for_log(arguments),
                )
                result = await session.call_tool(tool_name, arguments=arguments)
                observation = format_tool_result(result)
                success = not bool(getattr(result, "isError", False))
                if not success:
                    observation = _json_for_log({"error": observation})
            except Exception as exc:
                success = False
                observation = _json_for_log({"error": str(exc)})
                logger.warning(
                    "TOOL_ERROR iteration=%d tool=%s error=%s",
                    iteration,
                    tool_name,
                    exc,
                )

            logger.info(
                "OBSERVATION iteration=%d tool=%s payload=%s",
                iteration,
                tool_name,
                observation,
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": observation,
                }
            )
            await _audit_agent_action(session, logger, tool_name, arguments, success)

    raise RuntimeError(f"Agent stopped after {max_iterations} iterations without a final answer.")


async def run_agent(
    user_prompt: str,
    log_path: Path = DEFAULT_LOG_PATH,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> str:
    """Start the MCP server, connect to LiteLLM, and run one user request."""

    settings = settings_from_env()
    logger = configure_logging(log_path, logger_name="homework.litellm_agent")
    server_path = PROJECT_ROOT / "mcp_server.py"
    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    logger.info("LiteLLM endpoint=%s model=%s", settings.api_base, settings.model)
    logger.info("Starting MCP server over Stdio: %s", server_path)

    async with stdio_client(server_parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            tool_definitions = mcp_tools_to_openai_tools(tools_response)
            logger.info(
                "DISCOVERY tools=%s",
                [definition["function"]["name"] for definition in tool_definitions],
            )

            llm_client = AsyncOpenAI(
                api_key=settings.api_key,
                base_url=settings.api_base,
            )
            try:
                answer = await run_react_agent(
                    session=session,
                    llm_client=llm_client,
                    tool_definitions=tool_definitions,
                    user_prompt=user_prompt,
                    model=settings.model,
                    logger=logger,
                    max_iterations=max_iterations,
                )
            finally:
                await llm_client.close()

    logger.info("Agent completed successfully; log_file=%s", log_path)
    print(answer)
    return answer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="Aufgabe, die der ReAct-Agent bearbeiten soll.")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Path for the generated execution log.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help="Maximum number of LLM turns in the ReAct loop.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    try:
        asyncio.run(run_agent(args.prompt, args.log_file, args.max_iterations))
    except (AgentConfigurationError, ValueError, RuntimeError) as exc:
        print(f"Agent konnte nicht ausgeführt werden: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
