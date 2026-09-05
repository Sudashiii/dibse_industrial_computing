"""Minimal FastMCP server scaffold for Homework 1."""

from fastmcp import FastMCP


mcp = FastMCP("Homework 1 MCP Server")


@mcp.resource("homework://info")
def homework_info() -> str:
    """Return basic information about the local homework MCP server."""

    return "Homework 1 MCP server is ready."


def main() -> None:
    """Run the MCP server over the standard-input/output transport."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
