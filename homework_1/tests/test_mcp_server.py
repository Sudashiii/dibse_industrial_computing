import asyncio

from mcp_server import mcp


def test_inventory_lookup_is_registered_as_mcp_tool() -> None:
    tools = asyncio.run(mcp.list_tools())

    assert {tool.name for tool in tools} == {
        "lookup_inventory",
        "calculate_tiered_discount",
        "append_audit_event",
    }


def test_audit_log_is_registered_as_mcp_resource() -> None:
    resources = asyncio.run(mcp.list_resources())

    assert "audit://events" in {str(resource.uri) for resource in resources}
