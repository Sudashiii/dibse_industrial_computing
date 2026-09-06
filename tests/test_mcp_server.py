import asyncio

from mcp_server import mcp


def test_inventory_lookup_is_registered_as_mcp_tool() -> None:
    tools = asyncio.run(mcp.list_tools())

    assert "lookup_inventory" in {tool.name for tool in tools}
