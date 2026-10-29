import pytest

from app.agent.llm import get_chat_model
from app.main import app
from tests.test_analyze import ANALYSIS, create_incident, make_fake_model, start_analysis


def analyze(client, incident_id):
    app.dependency_overrides[get_chat_model] = make_fake_model
    return client.post(f"/incidents/{incident_id}/analyze").json()["thread_id"]


def test_list_shows_latest_status_and_newest_first(client):
    create_incident(client, "INC-201", "Printer offline")
    thread_id = start_analysis(client)

    listed = client.get("/incidents").json()

    assert [incident["incident_id"] for incident in listed] == ["INC-101", "INC-201"]
    assert listed[0]["latest_status"] == "pending"
    assert listed[1]["latest_status"] is None

    client.post(f"/analyses/{thread_id}/decision", json={"approved": True})

    assert client.get("/incidents").json()[0]["latest_status"] == "approved"


def test_list_shows_status_of_the_newest_analysis(client):
    first = start_analysis(client)
    client.post(f"/analyses/{first}/decision", json={"approved": False})
    analyze(client, "INC-101")

    assert client.get("/incidents").json()[0]["latest_status"] == "pending"


def test_get_one_incident(client):
    create_incident(client, "INC-201", "Printer offline")

    response = client.get("/incidents/INC-201")

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "incident_id": "INC-201",
        "description": "Printer offline",
        "latest_status": None,
    }


def test_get_unknown_incident_returns_404(client):
    response = client.get("/incidents/DOES-NOT-EXIST")

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}


def test_incident_analyses_are_listed_newest_first_with_audit_fields(client):
    first = start_analysis(client)
    client.post(
        f"/analyses/{first}/decision",
        json={"approved": False, "comment": "Too thin"},
    )
    second = analyze(client, "INC-101")

    response = client.get("/incidents/INC-101/analyses")

    assert response.status_code == 200
    records = response.json()
    assert [record["thread_id"] for record in records] == [second, first]

    pending, rejected = records
    assert pending["status"] == "pending"
    assert pending["reviewed_at"] is None
    assert pending["decided_by"] is None
    assert pending["analysis"] == ANALYSIS.model_dump()
    assert pending["similar_incidents"] == []

    assert rejected["status"] == "rejected"
    assert rejected["reviewer_comment"] == "Too thin"
    assert rejected["requested_by"] == "api"
    assert rejected["decided_by"] == "api"
    assert rejected["created_at"] is not None
    assert rejected["reviewed_at"] is not None


def test_incident_without_analyses_returns_empty_list(client):
    create_incident(client, "INC-201", "Printer offline")

    response = client.get("/incidents/INC-201/analyses")

    assert response.status_code == 200
    assert response.json() == []


def test_analyses_of_unknown_incident_returns_404(client):
    response = client.get("/incidents/DOES-NOT-EXIST/analyses")

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}


def test_pending_queue_is_oldest_first_and_leaves_out_decided(client):
    create_incident(client, "INC-1", "Nightly payroll job failed")
    create_incident(client, "INC-2", "VPN drops every hour")
    create_incident(client, "INC-3", "Printer offline")
    first = analyze(client, "INC-1")
    second = analyze(client, "INC-2")
    third = analyze(client, "INC-3")
    client.post(f"/analyses/{second}/decision", json={"approved": True})

    response = client.get("/analyses", params={"status": "pending"})

    assert response.status_code == 200
    queue = response.json()
    assert [(item["thread_id"], item["incident_id"]) for item in queue] == [
        (first, "INC-1"),
        (third, "INC-3"),
    ]
    assert queue[0]["description"] == "Nightly payroll job failed"
    assert queue[0]["probable_cause"] == ANALYSIS.probable_cause
    assert queue[0]["created_at"] is not None


@pytest.mark.parametrize("query", ["", "?status=approved"])
def test_pending_queue_accepts_only_pending(client, query):
    response = client.get(f"/analyses{query}")

    assert response.status_code == 422