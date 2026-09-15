# Homework 2 – Distributed Remote A2A Research System

## Current status

The shared FastAPI/A2A protocol layer, dynamic registry, Literature Search,
Evidence Extraction and Synthesis Agents are scaffolded. Docker Compose and
the final workflow are added in the following commits.

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
