import json

import pytest

from audit_log import append_audit_event, read_audit_log


def test_append_creates_jsonl_file(tmp_path) -> None:
    log_path = tmp_path / "audit_events.jsonl"

    result = append_audit_event(
        "inventory_lookup",
        "Inventory lookup completed",
        {"query": "P-1001", "count": 1},
        log_path,
    )

    assert log_path.exists()
    event = json.loads(log_path.read_text(encoding="utf-8"))
    assert event == result["event"]
    assert event["event_type"] == "inventory_lookup"
    assert event["details"] == {"query": "P-1001", "count": 1}
    assert event["timestamp"].endswith("Z")
    assert result["success"] is True


def test_append_preserves_existing_events(tmp_path) -> None:
    log_path = tmp_path / "audit_events.jsonl"

    first = append_audit_event("first", "First event", log_path=log_path)
    second = append_audit_event("second", "Second event", log_path=log_path)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event_id"] == first["event"]["event_id"]
    assert json.loads(lines[1])["event_id"] == second["event"]["event_id"]
    assert first["event"]["event_id"] != second["event"]["event_id"]


def test_read_missing_log_returns_empty_string(tmp_path) -> None:
    assert read_audit_log(tmp_path / "missing.jsonl") == ""


def test_read_returns_raw_jsonl_content(tmp_path) -> None:
    log_path = tmp_path / "audit_events.jsonl"
    append_audit_event("test", "Readable event", log_path=log_path)

    content = read_audit_log(log_path)

    assert content.endswith("\n")
    assert json.loads(content)["message"] == "Readable event"


@pytest.mark.parametrize(
    ("event_type", "message"),
    [("", "message"), ("event", "")],
)
def test_event_fields_must_not_be_blank(tmp_path, event_type, message) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        append_audit_event(event_type, message, log_path=tmp_path / "audit.jsonl")


def test_details_must_be_json_serializable(tmp_path) -> None:
    with pytest.raises(ValueError, match="JSON-serializable"):
        append_audit_event(
            "invalid",
            "Invalid details",
            {"not_serializable": object()},
            tmp_path / "audit.jsonl",
        )
