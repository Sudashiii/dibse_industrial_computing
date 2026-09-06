import asyncio

from mcp_server import mcp


def test_inventory_lookup_is_registered_as_mcp_tool() -> None:
    tools = asyncio.run(mcp.list_tools())

    assert {tool.name for tool in tools} == {
        "lookup_inventory",
        "calculate_tiered_discount",
    }
