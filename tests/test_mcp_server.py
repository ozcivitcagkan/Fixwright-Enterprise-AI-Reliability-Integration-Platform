import pytest
from mcp import Client

from app import mcp_server
from app.agent.llm import get_chat_model
from app.main import app
from tests.test_analyze import ANALYSIS, make_fake_model


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def api(client, monkeypatch):
    # The MCP tools call the test app instead of a running server
    monkeypatch.setattr(mcp_server, "http", client)
    return client


@pytest.mark.anyio
async def test_exposes_expected_tools(api):
    async with Client(mcp_server.mcp) as mcp_client:
        tools = {tool.name: tool for tool in (await mcp_client.list_tools()).tools}

    assert set(tools) == {"list_incidents", "create_incident", "analyze_incident", "decide_analysis"}
    assert tools["list_incidents"].annotations.read_only_hint is True
    assert tools["decide_analysis"].annotations.destructive_hint is True
    assert "never decide on your own" in tools["decide_analysis"].description


@pytest.mark.anyio
async def test_create_and_list_incidents(api):
    async with Client(mcp_server.mcp) as mcp_client:
        created = await mcp_client.call_tool(
            "create_incident",
            {"incident_id": "INC-201", "description": "VPN drops every hour"},
        )
        listed = await mcp_client.call_tool("list_incidents", {})

    assert created.is_error is False
    incident_ids = [incident["incident_id"] for incident in listed.structured_content["result"]]
    assert incident_ids == ["INC-201"]


@pytest.mark.anyio
async def test_analyze_then_decide(api):
    api.post(
        "/incidents",
        json={"incident_id": "INC-101", "description": "Nightly payroll ETL job failed with a database timeout"},
    )
    app.dependency_overrides[get_chat_model] = make_fake_model

    async with Client(mcp_server.mcp) as mcp_client:
        analyzed = await mcp_client.call_tool("analyze_incident", {"incident_id": "INC-101"})
        thread_id = analyzed.structured_content["thread_id"]
        decided = await mcp_client.call_tool(
            "decide_analysis",
            {"thread_id": thread_id, "approved": True, "comment": "Matches what we saw"},
        )
        repeated = await mcp_client.call_tool(
            "decide_analysis",
            {"thread_id": thread_id, "approved": False},
        )

    assert analyzed.structured_content["status"] == "pending_approval"
    assert analyzed.structured_content["analysis"] == ANALYSIS.model_dump()
    assert decided.structured_content == {"thread_id": thread_id, "status": "approved"}
    assert repeated.is_error is True
    assert "409" in repeated.content[0].text


@pytest.mark.anyio
async def test_api_errors_are_returned_to_the_model(api):
    api.headers["X-API-Key"] = "wrong-key"

    async with Client(mcp_server.mcp) as mcp_client:
        result = await mcp_client.call_tool("list_incidents", {})

    assert result.is_error is True
    assert "401" in result.content[0].text