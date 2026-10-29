from langgraph.checkpoint.postgres import PostgresSaver

from app.agent.llm import get_chat_model
from app.db import connect, connect_checkpointer_db
from app.demo import delete_old_demo_data
from app.main import app
from tests.conftest import TEST_DB_NAME, sign_in_demo
from tests.test_analyze import create_incident, make_fake_model


def analyze(client, incident_id):
    return client.post(f"/incidents/{incident_id}/analyze").json()["thread_id"]


def has_checkpoint(checkpointer, thread_id):
    return checkpointer.get_tuple({"configurable": {"thread_id": thread_id}}) is not None


def test_cleanup_removes_only_old_demo_data_and_its_checkpoints(client, db):
    app.dependency_overrides[get_chat_model] = make_fake_model
    # As the API key: an incident and an analysis that must survive however old they are
    create_incident(client, "INC-101", "Nightly payroll ETL job failed with a database timeout")
    api_thread = analyze(client, "INC-101")
    # As a demo visitor: an old and a new incident, plus an analysis of the API incident
    sign_in_demo(client)
    create_incident(client, "INC-D1", "Old demo incident")
    old_demo_thread = analyze(client, "INC-D1")
    create_incident(client, "INC-D2", "New demo incident")
    new_demo_thread = analyze(client, "INC-D2")
    demo_on_api_thread = analyze(client, "INC-101")

    # Eight days is past the seven-day retention. The analysis of INC-D1 stays new on
    # purpose: it must go anyway, because its incident goes and takes it along.
    db.execute(
        "UPDATE incidents SET created_at = now() - interval '8 days' "
        "WHERE incident_id IN ('INC-101', 'INC-D1')"
    )
    db.execute(
        "UPDATE incident_analyses SET created_at = now() - interval '8 days' WHERE thread_id = ANY(%s)",
        ([api_thread, demo_on_api_thread],),
    )

    with connect(TEST_DB_NAME) as cleanup_conn, connect_checkpointer_db(TEST_DB_NAME) as saver_conn:
        checkpointer = PostgresSaver(saver_conn)
        counts = delete_old_demo_data(cleanup_conn, checkpointer)

        assert counts == {"incidents": 1, "analyses": 2}
        assert not has_checkpoint(checkpointer, old_demo_thread)
        assert not has_checkpoint(checkpointer, demo_on_api_thread)
        assert has_checkpoint(checkpointer, api_thread)
        assert has_checkpoint(checkpointer, new_demo_thread)

    remaining_incidents = {row[0] for row in db.execute("SELECT incident_id FROM incidents")}
    assert remaining_incidents == {"INC-101", "INC-D2"}
    remaining_threads = {row[0] for row in db.execute("SELECT thread_id FROM incident_analyses")}
    assert remaining_threads == {api_thread, new_demo_thread}


def test_cleanup_removes_analyses_decided_by_demo(client, db):
    app.dependency_overrides[get_chat_model] = make_fake_model
    # The API key starts two analyses, a demo visitor decides both with a comment
    create_incident(client, "INC-101", "Nightly payroll ETL job failed with a database timeout")
    old_decision_thread = analyze(client, "INC-101")
    new_decision_thread = analyze(client, "INC-101")
    sign_in_demo(client)
    for thread_id in (old_decision_thread, new_decision_thread):
        decided = client.post(
            f"/analyses/{thread_id}/decision",
            json={"approved": False, "comment": "Text a visitor wrote"},
        )
        assert decided.status_code == 200

    # Only the decision is old: the analysis itself and its incident are recent
    db.execute(
        "UPDATE incident_analyses SET reviewed_at = now() - interval '8 days' WHERE thread_id = %s",
        (old_decision_thread,),
    )

    with connect(TEST_DB_NAME) as cleanup_conn, connect_checkpointer_db(TEST_DB_NAME) as saver_conn:
        checkpointer = PostgresSaver(saver_conn)
        counts = delete_old_demo_data(cleanup_conn, checkpointer)

        assert counts == {"incidents": 0, "analyses": 1}
        assert not has_checkpoint(checkpointer, old_decision_thread)
        assert has_checkpoint(checkpointer, new_decision_thread)

    remaining_threads = {row[0] for row in db.execute("SELECT thread_id FROM incident_analyses")}
    assert remaining_threads == {new_decision_thread}