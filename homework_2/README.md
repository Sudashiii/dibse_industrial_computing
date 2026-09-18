# Homework 2 – Distributed Remote A2A Research System

## Current status

The shared FastAPI/A2A protocol layer, dynamic registry, Literature Search,
Evidence Extraction and Synthesis Agents are available. The Orchestrator now
discovers all three agents dynamically by capability. The checked-in evidence
contains three successful containerized sample workflows.

## Local setup

```powershell
uv sync
uv run pytest
```

The registry can be started locally with:

```powershell
uv run uvicorn a2a_research.registry_app:app --host 127.0.0.1 --port 8000
```

Start the search agent in a second terminal after the registry is running:

```powershell
$env:A2A_REGISTRY_URL = "http://127.0.0.1:8000"
uv run uvicorn a2a_research.search_agent:app --host 127.0.0.1 --port 8101
```

Start the evidence agent in a third terminal:

```powershell
$env:A2A_REGISTRY_URL = "http://127.0.0.1:8000"
uv run uvicorn a2a_research.evidence_agent:app --host 127.0.0.1 --port 8102
```

Start the synthesis agent in a fourth terminal:

```powershell
$env:A2A_REGISTRY_URL = "http://127.0.0.1:8000"
uv run uvicorn a2a_research.synthesis_agent:app --host 127.0.0.1 --port 8103
```

After all four processes are running, start the complete workflow from a
fifth terminal. The Orchestrator looks up each capability in the Registry and
passes the structured result of one agent to the next:

```powershell
$env:A2A_REGISTRY_URL = "http://127.0.0.1:8000"
uv run python -m a2a_research.orchestrator `
  --question "Welche Vorteile und Grenzen haben Retrieval-Systeme?" `
  --top-k 2
```

## Docker Compose

Docker Desktop with Compose is required. The same four processes can be
started as containers:

```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker compose up --build -d litellm registry search-agent evidence-agent synthesis-agent
docker compose --profile workflow run --rm orchestrator `
  --question "Welche Vorteile und Grenzen haben Retrieval-Systeme?" `
  --top-k 2
docker compose down
```

The agent containers register themselves with the `registry` service. The
Orchestrator receives their container URLs from the Registry, so no agent URL
is hard-coded into the workflow. The Compose `orchestrator` service is kept in
the `workflow` profile because it is a one-shot command.

The Compose file also includes the optional local LiteLLM proxy copied from
Homework 1. It is available at `http://localhost:4000/v1` and routes the
`homework-model` alias to OpenRouter when a real `OPENROUTER_API_KEY` is
provided in `.env`. The A2A workflow itself uses the local deterministic
corpus and does not require an LLM request.

To start the proxy together with the A2A services:

```powershell
Copy-Item .env.example .env
docker compose up --build -d litellm registry search-agent evidence-agent synthesis-agent
```

No LiteLLM or OpenRouter request is needed to run the graded A2A sample.

## Submission evidence

Generate the execution log, structured result and focused terminal screenshot
with:

```powershell
uv run python scripts/run_demo.py  # runs three sample questions
uv run python docs/create_submission_pdf.py
```

The one-page summary is available at `docs/submission_summary.md`; generated
PDF and evidence files are stored under `output/`. The complete multi-sample
results are in `output/evidence/workflow-samples.json`.
