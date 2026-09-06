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

## LiteLLM-Agent

In diesem Projekt ist hinter dem lokalen LiteLLM-Proxy OpenRouter als Provider
geschaltet, weil dafür bereits ein Account vorhanden war. Der Agent spricht
weiterhin nur den lokalen LiteLLM-Endpunkt an.

```powershell
Copy-Item .env.example .env
# OPENROUTER_API_KEY in .env eintragen
docker compose up -d
uv run python litellm_agent.py "Prüfe den Bestand des Industrial Sensor und berechne den Rabatt für 120 Stück. Nenne mir am Ende die wichtigsten Werte."
docker compose down
```

Beispielantwort: 120 Stück auf Lager; für 120 Stück ergeben sich 506,49 EUR
Rabatt und 5.481,51 EUR netto. Weitere ausgeführte Prompt-/Antwort-Beispiele
stehen in `docs/submission_summary.md` und den Logs unter `logs/`.

## Abgabeübersicht

Die einseitige Zusammenfassung liegt unter `output/pdf/homework1_submission_summary.pdf`.
