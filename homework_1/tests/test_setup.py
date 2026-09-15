from mcp_server import homework_info


def test_server_scaffold_is_importable() -> None:
    assert homework_info() == "Homework 1 MCP server is ready."
