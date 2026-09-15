"""FastMCP server for the Homework 1 tools."""

from typing import Any

from fastmcp import FastMCP

from audit_log import (
    append_audit_event as append_event_to_log,
    read_audit_log,
)
from database import search_inventory
from formula_engine import (
    OrderItem,
    calculate_tiered_discount as calculate_discount,
)


mcp = FastMCP("Homework 1 MCP Server")


@mcp.resource("homework://info")
def homework_info() -> str:
    """Return basic information about the local homework MCP server."""

    return "Homework 1 MCP server is ready."


@mcp.resource("audit://events")
def audit_events() -> str:
    """Return the content of the local JSON Lines audit log."""

    return read_audit_log()


@mcp.tool()
def lookup_inventory(query: str) -> dict[str, object]:
    """Look up product stock by product ID or part of its name."""

    return search_inventory(query)


@mcp.tool()
def calculate_tiered_discount(items: list[OrderItem]) -> dict[str, object]:
    """Calculate discounts; use the exact inventory unit_price for each item."""

    return calculate_discount(items)


@mcp.tool()
def append_audit_event(
    event_type: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append an event to the local JSON Lines audit log."""

    return append_event_to_log(event_type, message, details)


def main() -> None:
    """Run the MCP server over the standard-input/output transport."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
