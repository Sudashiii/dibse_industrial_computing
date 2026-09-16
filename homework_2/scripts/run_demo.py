"""Run the containerized workflow and save focused submission evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "evidence"
COMPOSE_SERVICES = (
    "registry",
    "search-agent",
    "evidence-agent",
    "synthesis-agent",
)
RELEVANT_LOG_MARKERS = (
    "REGISTRY_LOOKUP",
    "AGENT_SELECTED",
    "A2A_CALL",
    "WORKFLOW_COMPLETED",
    "SUMMARY",
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _display_command(args: Sequence[str]) -> str:
    return " ".join(args)


def _run(
    args: Sequence[str],
    *,
    cwd: Path,
    log_lines: list[str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = _display_command(args)
    log_lines.append(f"[{_timestamp()}] COMMAND {command}")
    result = subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log_lines.append(f"[{_timestamp()}] RESULT exit={result.returncode}")
    if check and result.returncode != 0:
        output = "\n".join(
            part.strip()
            for part in (result.stdout, result.stderr)
            if part.strip()
        )
        raise RuntimeError(f"Command failed: {command}\n{output}")
    return result


def _append_relevant_workflow_logs(
    stderr: str,
    log_lines: list[str],
) -> None:
    for line in stderr.splitlines():
        if any(marker in line for marker in RELEVANT_LOG_MARKERS[:-1]):
            log_lines.append(line.strip())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Docker Compose A2A workflow and save evidence."
    )
    parser.add_argument(
        "--question",
        default="Welche Vorteile und Grenzen haben Retrieval-Systeme?",
        help="Research question passed to the workflow.",
    )
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for execution.log and workflow-output.json.",
    )
    return parser


def run_demo(
    question: str,
    *,
    top_k: int,
    output_dir: Path,
) -> dict[str, object]:
    """Run Compose, capture the workflow JSON and return its parsed result."""

    output_dir.mkdir(parents=True, exist_ok=True)
    log_lines = [
        "A2A research workflow execution evidence",
        f"question={question}",
        f"top_k={top_k}",
    ]
    services_started = False
    workflow_result: dict[str, object] | None = None

    try:
        _run(
            ["docker", "compose", "config", "--quiet"],
            cwd=PROJECT_ROOT,
            log_lines=log_lines,
        )
        services_started = True
        _run(
            [
                "docker",
                "compose",
                "up",
                "--build",
                "--detach",
                "--wait",
                *COMPOSE_SERVICES,
            ],
            cwd=PROJECT_ROOT,
            log_lines=log_lines,
        )
        workflow = _run(
            [
                "docker",
                "compose",
                "--profile",
                "workflow",
                "run",
                "--rm",
                "orchestrator",
                "--question",
                question,
                "--top-k",
                str(top_k),
            ],
            cwd=PROJECT_ROOT,
            log_lines=log_lines,
        )
        _append_relevant_workflow_logs(workflow.stderr, log_lines)
        try:
            workflow_result = json.loads(workflow.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "The orchestrator did not return valid JSON."
            ) from exc
        if not isinstance(workflow_result, dict):
            raise RuntimeError("The orchestrator result must be a JSON object.")

        agents = workflow_result.get("agents", [])
        search = workflow_result.get("search", {})
        evidence = workflow_result.get("evidence", {})
        synthesis = workflow_result.get("synthesis", {})
        log_lines.append(
            "SUMMARY "
            f"agents={len(agents)} "
            f"search_hits={len(search.get('hits', []))} "
            f"evidence_items={len(evidence.get('evidence', []))} "
            f"synthesis_findings={len(synthesis.get('key_findings', []))}"
        )
        return workflow_result
    finally:
        if services_started:
            down = _run(
                ["docker", "compose", "down", "--remove-orphans"],
                cwd=PROJECT_ROOT,
                log_lines=log_lines,
                check=False,
            )
            if down.returncode == 0:
                log_lines.append("CLEANUP compose_down=ok")
            else:
                log_lines.append("CLEANUP compose_down=failed")
        (output_dir / "execution.log").write_text(
            "\n".join(log_lines) + "\n",
            encoding="utf-8",
        )
        if workflow_result is not None:
            (output_dir / "workflow-output.json").write_text(
                json.dumps(workflow_result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    try:
        result = run_demo(
            args.question,
            top_k=args.top_k,
            output_dir=output_dir,
        )
    except (OSError, RuntimeError) as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        return 1

    print(f"Saved execution evidence to {output_dir}")
    print(
        "Summary: "
        f"{len(result['agents'])} agents, "
        f"{len(result['search']['hits'])} search hits, "
        f"{len(result['evidence']['evidence'])} evidence items, "
        f"{len(result['synthesis']['key_findings'])} synthesis findings"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
