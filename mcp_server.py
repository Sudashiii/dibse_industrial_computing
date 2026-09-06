"""FastMCP server for the Homework 1 tools."""

from fastmcp import FastMCP

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


@mcp.tool()
def lookup_inventory(query: str) -> dict[str, object]:
    """Look up product stock by product ID or part of its name."""

    return search_inventory(query)


@mcp.tool()
def calculate_tiered_discount(items: list[OrderItem]) -> dict[str, object]:
    """Calculate progressive tiered discounts for order positions."""

    return calculate_discount(items)


def main() -> None:
    """Run the MCP server over the standard-input/output transport."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
