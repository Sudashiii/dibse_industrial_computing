"""Run a reproducible local MCP client demonstration over Stdio."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "demo_run.log"


def configure_logging(
    log_path: Path,
    logger_name: str = "homework.mcp_demo",
) -> logging.Logger:
    """Configure console and UTF-8 file logging for one run."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def _text_from_content(content: Any) -> str | None:
    text = getattr(content, "text", None)
    if text is not None:
        return str(text)

    blob = getattr(content, "blob", None)
    if blob is not None:
        return str(blob)

    return None


def format_tool_result(result: Any) -> str:
    """Convert an MCP tool result into readable JSON or text."""

    structured_content = getattr(result, "structuredContent", None)
    if structured_content is None:
        structured_content = getattr(result, "structured_content", None)
    if structured_content is not None:
        return json.dumps(structured_content, ensure_ascii=False, sort_keys=True)

    text_parts = [
        text
        for content in getattr(result, "content", [])
        if (text := _text_from_content(content)) is not None
    ]
    if text_parts:
        return "\n".join(text_parts)

    return str(result)


def format_resource_result(result: Any) -> str:
    """Extract text or blobs from an MCP resource response."""

    text_parts = [
        text
        for content in getattr(result, "contents", [])
        if (text := _text_from_content(content)) is not None
    ]
    return "\n".join(text_parts)


async def call_tool_and_log(
    session: ClientSession,
    logger: logging.Logger,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """Call one MCP tool and write its request and response to the log."""

    logger.info("REQUEST tool=%s arguments=%s", tool_name, json.dumps(arguments, ensure_ascii=False))
    result = await session.call_tool(tool_name, arguments=arguments)
    logger.info("RESPONSE tool=%s payload=%s", tool_name, format_tool_result(result))

    if getattr(result, "isError", False):
        raise RuntimeError(f"MCP tool failed: {tool_name}")
    return result


async def run_demo(log_path: Path = DEFAULT_LOG_PATH) -> None:
    """Run the complete local MCP demonstration."""

    logger = configure_logging(log_path)
    server_path = PROJECT_ROOT / "mcp_server.py"
    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    logger.info("Starting MCP server over Stdio: %s", server_path)
    async with stdio_client(server_parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            logger.info("MCP session initialized")

            tools_response = await session.list_tools()
            tool_names = [tool.name for tool in tools_response.tools]
            logger.info("DISCOVERY tools=%s", tool_names)

            resources_response = await session.list_resources()
            resource_uris = [str(resource.uri) for resource in resources_response.resources]
            logger.info("DISCOVERY resources=%s", resource_uris)

            info_result = await session.read_resource("homework://info")
            logger.info("RESOURCE homework://info payload=%s", format_resource_result(info_result))

            await call_tool_and_log(
                session,
                logger,
                "lookup_inventory",
                {"query": "Industrial Sensor"},
            )
            await call_tool_and_log(
                session,
                logger,
                "calculate_tiered_discount",
                {
                    "items": [
                        {
                            "product_name": "Industrial Sensor",
                            "quantity": 120,
                            "unit_price": 49.90,
                        }
                    ]
                },
            )
            await call_tool_and_log(
                session,
                logger,
                "append_audit_event",
                {
                    "event_type": "demo_run",
                    "message": "All business tools were executed successfully",
                    "details": {"tools": tool_names},
                },
            )

            audit_result = await session.read_resource("audit://events")
            audit_content = format_resource_result(audit_result)
            logger.info(
                "RESOURCE audit://events lines=%d payload=%s",
                len(audit_content.splitlines()) if audit_content else 0,
                audit_content,
            )

    logger.info("MCP demo completed successfully; log_file=%s", log_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Path for the generated execution log.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_demo(args.log_file))


if __name__ == "__main__":
    main()
