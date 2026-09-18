# Homework 2 - Distributed Remote A2A System

Repository: [Sudashiii/dibse_industrial_computing](https://github.com/Sudashiii/dibse_industrial_computing)

## Implementation

The project contains four independently running processes: a dynamic Registry,
a Literature Search Agent, an Evidence Extraction Agent and a Synthesis Agent.
The Orchestrator discovers the agents by capability and sends typed A2A
JSON-RPC `message/send` requests through the chain Search -> Evidence ->
Synthesis. Each service has its own port and Docker Compose healthcheck.
The Compose file also includes the optional LiteLLM proxy copied from Homework
1 at `localhost:4000`; the graded A2A workflow uses the local corpus and does
not make an LLM request.

## Reproduce

```powershell
cd homework_2
uv sync
uv run pytest -q
uv run python scripts/run_demo.py
```

The demo builds and starts LiteLLM plus the four A2A services, checks local
LiteLLM liveness without making a model call, executes three questions through
the dynamic Registry and Search -> Evidence -> Synthesis chain, saves the
structured results, and shuts the containers down again.

## Evidence

- [README](../README.md) - setup and manual commands
- [Execution log](../output/evidence/execution.log)
- [Structured workflow output](../output/evidence/workflow-output.json)
- [All three sample results](../output/evidence/workflow-samples.json)
- [Focused terminal screenshot](../output/evidence/terminal-screenshot.png)
- [Sample-results screenshot](../output/evidence/sample-results.png)
- [One-page PDF summary](../output/pdf/homework_2_submission_summary.pdf)

The checked-in demo evidence shows three registered agents on every run, three
completed sample requests, five search hits, five extracted evidence items and
five synthesis findings in total. No API keys or credentials are needed for
the local A2A workflow.
