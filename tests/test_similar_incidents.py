import json

from langchain_core.messages import AIMessage, ToolMessage

from app.agent.graph import collect_similar_incidents

APPROVED = {"probable_cause": "Database CPU saturation", "suggested_steps": []}


def search_message(results, call_id="call_1"):
    return ToolMessage(
        content=json.dumps(results),
        name="search_similar_incidents",
        tool_call_id=call_id,
    )


def test_keeps_highest_similarity_per_incident_and_sorts_by_it():
    messages = [
        search_message([
            {"incident_id": "INC-2", "similarity": 0.5, "approved_analysis": None},
        ]),
        search_message([
            {"incident_id": "INC-2", "similarity": 0.7, "approved_analysis": None},
            {"incident_id": "INC-3", "similarity": 0.6, "approved_analysis": APPROVED},
        ], call_id="call_2"),
    ]

    assert collect_similar_incidents(messages) == [
        {"incident_id": "INC-2", "similarity": 0.7, "has_approved_analysis": False},
        {"incident_id": "INC-3", "similarity": 0.6, "has_approved_analysis": True},
    ]


def test_approved_analysis_seen_in_any_search_is_kept():
    messages = [
        search_message([{"incident_id": "INC-2", "similarity": 0.8, "approved_analysis": None}]),
        search_message(
            [{"incident_id": "INC-2", "similarity": 0.6, "approved_analysis": APPROVED}],
            call_id="call_2",
        ),
    ]

    assert collect_similar_incidents(messages) == [
        {"incident_id": "INC-2", "similarity": 0.8, "has_approved_analysis": True},
    ]


def test_skips_errors_other_tools_and_bad_content():
    messages = [
        AIMessage(content="Looking into it"),
        search_message({"error": "Similarity search is unavailable right now"}),
        ToolMessage(
            content=json.dumps({"incident_id": "INC-1", "description": "Disk full"}),
            name="get_incident",
            tool_call_id="call_2",
        ),
        ToolMessage(content="not json", name="search_similar_incidents", tool_call_id="call_3"),
    ]

    assert collect_similar_incidents(messages) == []


def test_no_search_gives_empty_list():
    assert collect_similar_incidents([AIMessage(content="No tools needed")]) == []