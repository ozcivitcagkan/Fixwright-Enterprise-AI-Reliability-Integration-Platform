# Fixwright Enterprise AI Reliability & Integration Platform.

[![Tests](https://github.com/ozcivitcagkan/Fixwright-Enterprise-AI-Reliability-Integration-Platform/actions/workflows/tests.yml/badge.svg)](https://github.com/ozcivitcagkan/Fixwright-Enterprise-AI-Reliability-Integration-Platform/actions/workflows/tests.yml)

Fixwright is an enterprise-focused platform for incident management, system integrations, reliability workflows, and AI-assisted operational automation.

## Current Features

- REST API built with FastAPI
- PostgreSQL database integration
- Incident CRUD operations
- AI incident analysis agent built with LangGraph and Claude (tool calling, structured output)
- Human-in-the-loop approval: AI analyses are saved only after a person approves or rejects them
- Durable agent state with the LangGraph Postgres checkpointer
- API key authentication on every endpoint except the health check
- Pydantic request and response validation
- HTTP error handling
- Environment-based configuration
- Dockerized PostgreSQL
- Automated tests with pytest against a real PostgreSQL test database
- CI with GitHub Actions on every pull request

## Tech Stack

- Python
- FastAPI
- PostgreSQL
- Psycopg
- Pydantic
- LangGraph (with langgraph-checkpoint-postgres)
- LangChain (langchain-anthropic)
- Anthropic Claude (Haiku 5.5)
- pytest
- Docker
- GitHub Actions
- Git
- GitHub

## Getting Started

1. Start PostgreSQL in Docker and create a `.env` file with `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `ANTHROPIC_API_KEY`, and `FIXWRIGHT_API_KEY`.
2. Generate a random value for `FIXWRIGHT_API_KEY`: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
3. Install dependencies: `pip install -r requirements.txt`
4. Create the tables and the agent checkpoint tables (a one-time deploy step): `python -m app.db`
5. Run the API: `uvicorn app.main:app --reload`

## Authentication

Every endpoint except `GET /health` requires an API key in the `X-API-Key` header:

```bash
curl http://localhost:8000/incidents -H "X-API-Key: <your key>"
```

- A missing or wrong key returns `401` with a `WWW-Authenticate: APIKey` header.
- Keys are compared in constant time (`secrets.compare_digest`) to prevent timing attacks.
- If `FIXWRIGHT_API_KEY` is not set on the server, protected endpoints return `500` instead of opening up (fail closed).
- `GET /health` stays public so that deployment platforms can check the service.
- In the interactive docs (`/docs`), use the **Authorize** button to enter the key.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check (also checks the database), public |
| POST | `/incidents` | Create an incident |
| GET | `/incidents` | Retrieve incidents |
| PUT | `/incidents/{incident_id}` | Update an incident |
| DELETE | `/incidents/{incident_id}` | Delete an incident |
| POST | `/incidents/{incident_id}/analyze` | Run the AI agent and return an analysis waiting for approval |
| POST | `/analyses/{thread_id}/decision` | Approve or reject a pending analysis |

## AI Incident Analysis with Human Approval

An AI suggestion is not trusted on its own. The agent prepares an analysis, then pauses until a person approves or rejects it. Only then is the result written to the `incident_analyses` table.

**Step 1:** `POST /incidents/{incident_id}/analyze`

```json
{
  "thread_id": "3f2b...",
  "status": "pending_approval",
  "analysis": {
    "probable_cause": "...",
    "suggested_steps": ["..."],
    "evidence": ["..."]
  }
}
```

**Step 2:** `POST /analyses/{thread_id}/decision`

```json
{ "approved": true, "comment": "Matches what we saw last week" }
```

Response: `{"thread_id": "3f2b...", "status": "approved"}`

How it works:

```mermaid
flowchart LR
    START([start]) --> agent
    agent -- tool calls --> tools
    tools --> agent
    agent -- no tool calls --> respond
    respond --> approval
    approval -- "waits for a human decision" --> save
    save --> END([end])
```

- **agent**: Claude decides which tool to call next.
- **tools**: runs the requested tools against PostgreSQL:
  - `get_incident`: reads the incident.
  - `search_similar_incidents`: finds related past incidents by keyword (to be replaced by vector search with pgvector).
- **respond**: turns the findings into a structured analysis using structured output.
- **approval**: pauses the graph with `interrupt()`. The graph state is stored in PostgreSQL by the checkpointer, so the decision can arrive in a later HTTP request, even after a restart.
- **save**: writes the analysis with its status (`approved` or `rejected`) and the reviewer's comment. Rejected analyses are kept as an audit trail.

Error handling:

- `404` from `/analyze` when the incident does not exist (the model is not called).
- `404` from `/decision` when the thread does not exist.
- `409` from `/decision` when the analysis was already decided.

Configuration:

- `ANTHROPIC_API_KEY` must be set in `.env` (never committed).
- The model ID, effort level, and output limit live in `app/config.py`.

Tests replace the model with a fake chat model, so the test suite and CI never call the real API. The database, tools, graph, and checkpointer still run for real.

## Architecture Roadmap

The platform is being developed toward an enterprise AI reliability architecture covering:

- AI-assisted incident analysis
- RAG-based knowledge retrieval
- Enterprise system integrations
- Reliable AI workflows
- Automated validation and testing
- Containerized services
- CI/CD pipelines
- Cloud infrastructure

## Status

Active Development

The core API, the database layer, the AI incident analysis agent, the human approval workflow, and API key authentication are implemented.