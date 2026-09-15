# Homework 2 – Distributed Remote A2A Research System

## Current status

The shared FastAPI/A2A protocol layer and the dynamic registry are scaffolded.
The three research agents, Docker Compose deployment and final workflow are
added in the following commits.

## Local setup

```powershell
uv sync
uv run pytest
```

The registry can be started locally with:

```powershell
uv run uvicorn a2a_research.registry_app:app --host 127.0.0.1 --port 8000
```
