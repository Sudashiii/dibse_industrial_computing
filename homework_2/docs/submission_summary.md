# Homework 2 - Distributed Remote A2A System

Repository: [Sudashiii/dibse_industrial_computing](https://github.com/Sudashiii/dibse_industrial_computing)

## Implementation

The project contains four independently running processes: a dynamic Registry,
a Literature Search Agent, an Evidence Extraction Agent and a Synthesis Agent.
The Orchestrator discovers the agents by capability and sends typed A2A
JSON-RPC `message/send` requests through the chain Search -> Evidence ->
Synthesis. Each service has its own port and Docker Compose healthcheck.

## Reproduce

```powershell
cd homework_2
uv sync
uv run pytest -q
python scripts/run_demo.py
```

The demo builds and starts the Compose services, executes the prompt
`Welche Vorteile und Grenzen haben Retrieval-Systeme?`, saves the complete
structured result, and shuts the containers down again.

## Evidence

- [README](../README.md) - setup and manual commands
- [Execution log](../output/evidence/execution.log)
- [Structured workflow output](../output/evidence/workflow-output.json)
- [Focused terminal screenshot](../output/evidence/terminal-screenshot.png)
- [One-page PDF summary](../output/pdf/homework_2_submission_summary.pdf)

The checked-in demo evidence shows three registered agents, two search hits,
two extracted evidence items and two synthesis findings. No API keys or
credentials are needed for this local workflow.
