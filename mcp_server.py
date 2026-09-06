"""FastMCP server for the Homework 1 tools."""

from fastmcp import FastMCP

from database import search_inventory


mcp = FastMCP("Homework 1 MCP Server")


@mcp.resource("homework://info")
def homework_info() -> str:
    """Return basic information about the local homework MCP server."""

    return "Homework 1 MCP server is ready."


@mcp.tool()
def lookup_inventory(query: str) -> dict[str, object]:
    """Look up product stock by product ID or part of its name."""

    return search_inventory(query)


def main() -> None:
    """Run the MCP server over the standard-input/output transport."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
