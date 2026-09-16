# Homework 2 – Distributed Remote A2A Research System

## Current status

The shared FastAPI/A2A protocol layer, dynamic registry, Literature Search,
Evidence Extraction and Synthesis Agents are available. The Orchestrator now
discovers all three agents dynamically by capability. Docker Compose and the
final workflow evidence are added in the following commits.

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
docker compose config --quiet
docker compose up --build -d registry search-agent evidence-agent synthesis-agent
docker compose --profile workflow run --rm orchestrator `
  --question "Welche Vorteile und Grenzen haben Retrieval-Systeme?" `
  --top-k 2
docker compose down
```

The agent containers register themselves with the `registry` service. The
Orchestrator receives their container URLs from the Registry, so no agent URL
is hard-coded into the workflow. The Compose `orchestrator` service is kept in
the `workflow` profile because it is a one-shot command.

## Submission evidence

Generate the execution log, structured result and focused terminal screenshot
with:

```powershell
uv run python scripts/run_demo.py
uv run python docs/create_submission_pdf.py
```

The one-page summary is available at `docs/submission_summary.md`; generated
PDF and evidence files are stored under `output/`.
