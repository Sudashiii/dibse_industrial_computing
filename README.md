# Homework 1 – MCP Server

## Voraussetzungen

- Python 3.11 oder neuer
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
uv sync
```

## Tests ausführen

```bash
uv run pytest
```

## MCP-Server starten

```bash
uv run python mcp_server.py
```

## Lokale MCP-Demo

```bash
uv run python demo_client.py
```

## LiteLLM-Agent (optional)

```powershell
Copy-Item .env.example .env
# OPENAI_API_KEY in .env eintragen
docker compose up -d
uv run python litellm_agent.py "Prüfe den Bestand des Industrial Sensor und berechne den Rabatt für 120 Stück."
docker compose down
```
