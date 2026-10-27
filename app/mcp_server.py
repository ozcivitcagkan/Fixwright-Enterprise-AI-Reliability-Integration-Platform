"""MCP server that lets AI assistants such as Claude Desktop work with Fixwright
through its HTTP API. It is a thin client: authentication, the agent and the human
approval step all stay in the API.

Run: python -m app.mcp_server  (stdio; the MCP client starts it, not a person)
"""
import os
from typing import Any
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

load_dotenv()

# An analysis calls the model several times, and the free live demo can take up
# to a minute to wake up.
TIMEOUT_SECONDS = 120.0

http = httpx.Client(
    base_url=os.getenv("FIXWRIGHT_API_URL", "http://localhost:8000"),
    headers={"X-API-Key": os.getenv("FIXWRIGHT_API_KEY", "")},
    timeout=TIMEOUT_SECONDS,
)

mcp = MCPServer("Fixwright")


def call_api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    try:
        response = http.request(method, path, json=body)
    except httpx.HTTPError as error:
        raise ToolError(f"Could not reach the Fixwright API: {error}") from error
    if response.is_error:
        raise ToolError(f"Fixwright API returned {response.status_code}: {response.text}")
    return response.json()


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
def list_incidents() -> list[dict[str, Any]]:
    """List all incidents with their incident_id and description."""
    return call_api("GET", "/incidents")


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False))
def create_incident(incident_id: str, description: str) -> dict[str, Any]:
    """Create a new incident, for example incident_id "INC-110" with a one-sentence
    description of the problem. Fails if the incident_id already exists."""
    return call_api("POST", "/incidents", {"incident_id": incident_id, "description": description})


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False))
def analyze_incident(incident_id: str) -> dict[str, Any]:
    """Run Fixwright's AI analysis for an incident. It reads the incident, searches
    similar past incidents, and returns a probable cause, suggested steps and evidence
    together with a thread_id. The analysis is not saved until a person approves or
    rejects it, so show it to the user and ask for their decision. Takes 10 to 30 seconds."""
    return call_api("POST", f"/incidents/{quote(incident_id, safe='')}/analyze")


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False))
def decide_analysis(thread_id: str, approved: bool, comment: str | None = None) -> dict[str, Any]:
    """Record the user's approval or rejection of a pending analysis. Only call this
    after the user has explicitly said in the conversation whether to approve or reject
    it; never decide on your own. Approved analyses are reused as evidence for future
    incidents, so a wrong approval spreads. A decision cannot be changed."""
    return call_api(
        "POST",
        f"/analyses/{quote(thread_id, safe='')}/decision",
        {"approved": approved, "comment": comment},
    )


if __name__ == "__main__":
    mcp.run()