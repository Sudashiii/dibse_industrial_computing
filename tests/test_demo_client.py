import json
from types import SimpleNamespace

from demo_client import format_resource_result, format_tool_result


def test_format_tool_result_prefers_structured_content() -> None:
    result = SimpleNamespace(
        structuredContent={"found": True, "count": 1},
        content=[],
    )

    formatted = format_tool_result(result)

    assert json.loads(formatted) == {"found": True, "count": 1}


def test_format_tool_result_reads_text_content() -> None:
    result = SimpleNamespace(
        structuredContent=None,
        content=[SimpleNamespace(text="tool output")],
    )

    assert format_tool_result(result) == "tool output"


def test_format_resource_result_reads_all_text_parts() -> None:
    result = SimpleNamespace(
        contents=[
            SimpleNamespace(text="first line"),
            SimpleNamespace(text="second line"),
        ]
    )

    assert format_resource_result(result) == "first line\nsecond line"
