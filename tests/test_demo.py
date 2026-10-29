import pytest

from app.agent.llm import get_chat_model
from app.main import app
from tests.conftest import sign_in_admin, sign_in_demo
from tests.test_analyze import ANALYSIS, FakeAgentModel, make_fake_model


def add_demo_rows(db, incidents=0, analyses=0, age="0 days"):
    """Inserts rows that look like earlier demo usage, `age` old."""
    db.execute(
        "INSERT INTO incidents (incident_id, description, created_by) VALUES ('SEED', 'Seed', 'admin')"
    )
    db.execute(
        """
        INSERT INTO incidents (incident_id, description, created_by, created_at)
        SELECT 'DEMO-' || n, 'Demo incident', 'demo', now() - %s::interval
        FROM generate_series(1, %s) AS n
        """,
        (age, incidents),
    )
    db.execute(
        """
        INSERT INTO incident_analyses
            (incident_id, thread_id, status, probable_cause, suggested_steps, evidence,
             requested_by, created_at)
        SELECT 'SEED', 'seed-thread-' || n, 'rejected', 'x', '[]', '[]', 'demo', now() - %s::interval
        FROM generate_series(1, %s) AS n
        """,
        (age, analyses),
    )


def test_demo_full_flow_records_demo_everywhere(client, db):
    sign_in_demo(client)
    client.post(
        "/incidents",
        json={"incident_id": "INC-101", "description": "Nightly payroll ETL job failed with a database timeout"},
    )
    app.dependency_overrides[get_chat_model] = make_fake_model
    thread_id = client.post("/incidents/INC-101/analyze").json()["thread_id"]

    decision = client.post(f"/analyses/{thread_id}/decision", json={"approved": True})

    assert decision.status_code == 200
    assert db.execute("SELECT created_by FROM incidents").fetchone()[0] == "demo"
    assert db.execute("SELECT requested_by, decided_by FROM incident_analyses").fetchone() == ("demo", "demo")
    assert client.get("/auth/me").json() == {"role": "demo", "demo_analyses_left": 29}


def test_demo_incident_limit_returns_429(client, db):
    add_demo_rows(db, incidents=20)
    sign_in_demo(client)

    response = client.post("/incidents", json={"incident_id": "INC-X", "description": "Disk full"})

    assert response.status_code == 429
    assert response.json() == {"detail": "Daily demo limit reached"}


def test_demo_analysis_limit_returns_429_without_calling_model(client, db):
    add_demo_rows(db, analyses=30)
    sign_in_demo(client)
    client.post("/incidents", json={"incident_id": "INC-101", "description": "Disk full"})
    fake_model = FakeAgentModel(messages=iter([]), analysis=ANALYSIS)
    app.dependency_overrides[get_chat_model] = lambda: fake_model

    response = client.post("/incidents/INC-101/analyze")

    assert response.status_code == 429
    assert response.json() == {"detail": "Daily demo limit reached"}
    assert fake_model.report_prompts == []
    assert client.get("/auth/me").json() == {"role": "demo", "demo_analyses_left": 0}


def test_demo_rows_from_yesterday_do_not_count(client, db):
    add_demo_rows(db, incidents=20, analyses=30, age="1 day")

    response = sign_in_demo(client)

    assert response.json() == {"role": "demo", "demo_analyses_left": 30}
    created = client.post("/incidents", json={"incident_id": "INC-X", "description": "Disk full"})
    assert created.status_code == 200


@pytest.mark.parametrize("length, status", [(1000, 200), (1001, 422)])
def test_demo_description_length(client, length, status):
    sign_in_demo(client)

    response = client.post("/incidents", json={"incident_id": "INC-X", "description": "x" * length})

    assert response.status_code == status


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_demo_cannot_change_or_delete_incidents(client, method):
    client.post("/incidents", json={"incident_id": "INC-1", "description": "Disk full"})
    sign_in_demo(client)

    response = client.request(method, "/incidents/INC-1", json={"description": "changed"})

    assert response.status_code == 403
    assert response.json() == {"detail": "Demo users cannot change or delete incidents"}


def test_api_and_admin_have_no_demo_limits(client, db):
    add_demo_rows(db, incidents=20)

    as_api = client.post("/incidents", json={"incident_id": "INC-API", "description": "x" * 1500})
    sign_in_admin(client)
    as_admin = client.post("/incidents", json={"incident_id": "INC-ADM", "description": "x" * 1500})

    assert as_api.status_code == 200
    assert as_admin.status_code == 200