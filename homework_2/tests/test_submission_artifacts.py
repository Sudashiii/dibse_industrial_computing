from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = PROJECT_ROOT / "output" / "evidence"


def test_checked_in_workflow_output_contains_complete_chain() -> None:
    result = json.loads(
        (EVIDENCE_DIR / "workflow-output.json").read_text(encoding="utf-8")
    )

    assert [agent["agent_id"] for agent in result["agents"]] == [
        "search-agent",
        "evidence-agent",
        "synthesis-agent",
    ]
    assert len(result["search"]["hits"]) == 2
    assert len(result["evidence"]["evidence"]) == 2
    assert len(result["synthesis"]["key_findings"]) == 2


def test_execution_log_contains_only_relevant_workflow_trace() -> None:
    log = (EVIDENCE_DIR / "execution.log").read_text(encoding="utf-8")

    assert "REGISTRY_LOOKUP capability=research.search" in log
    assert "A2A_CALL step=evidence agent_id=evidence-agent" in log
    assert "WORKFLOW_COMPLETED" in log
    assert "SUMMARY agents=3 search_hits=2 evidence_items=2 synthesis_findings=2" in log
    assert "CLEANUP compose_down=ok" in log


def test_terminal_screenshot_is_wide_and_readable() -> None:
    with Image.open(EVIDENCE_DIR / "terminal-screenshot.png") as screenshot:
        width, height = screenshot.size

    assert width > height * 2
    assert width >= 1600
