import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.agent.graph import AnalysisResult
from app.agent.llm import get_chat_model
from app.main import app

ANALYSIS = AnalysisResult(
    probable_cause="Database CPU saturation during the nightly payroll run",
    suggested_steps=["Check database CPU metrics for the run window"],
    evidence=["INC-102: database CPU was at 95 percent during the run"],
)


class FakeAgentModel(GenericFakeChatModel):
    analysis: AnalysisResult
    report_prompts: list[str] = []

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        def report(messages):
            self.report_prompts.append(messages[0].content)
            return self.analysis

        return RunnableLambda(report)


def tool_call(name, args, call_id):
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def create_incident(client, incident_id, description):
    client.post("/incidents", json={"incident_id": incident_id, "description": description})


def make_fake_model():
    return FakeAgentModel(
        messages=iter([
            AIMessage(content="", tool_calls=[
                tool_call("get_incident", {"incident_id": "INC-101"}, "call_1"),
            ]),
            AIMessage(content="INC-101 matches a known payroll database problem."),
        ]),
        analysis=ANALYSIS,
    )


def make_search_model():
    return FakeAgentModel(
        messages=iter([
            AIMessage(content="", tool_calls=[
                tool_call("get_incident", {"incident_id": "INC-101"}, "call_1"),
            ]),
            AIMessage(content="", tool_calls=[
                tool_call(
                    "search_similar_incidents",
                    {"query": "payroll etl job database", "exclude_incident_id": "INC-101"},
                    "call_2",
                ),
            ]),
            AIMessage(content="INC-101 repeats the CPU problem seen in INC-102."),
        ]),
        analysis=ANALYSIS,
    )


def search_result_line(fake_model):
    report_prompt = fake_model.report_prompts[0]
    return next(
        line for line in report_prompt.splitlines()
        if line.startswith("[search_similar_incidents]")
    )


def start_analysis(client):
    create_incident(client, "INC-101", "Nightly payroll ETL job failed with a database timeout")
    app.dependency_overrides[get_chat_model] = make_fake_model

    response = client.post("/incidents/INC-101/analyze")

    return response.json()["thread_id"]


def saved_analyses(db, thread_id):
    return db.execute(
        """
        SELECT status, reviewer_comment, probable_cause
        FROM incident_analyses
        WHERE thread_id = %s
        """,
        (thread_id,),
    ).fetchall()


def test_analyze_runs_tools_and_returns_pending_analysis(client, db):
    create_incident(client, "INC-101", "Nightly payroll ETL job failed with a database timeout")
    create_incident(client, "INC-102", "Payroll ETL job timed out; database CPU at 95 percent")
    create_incident(client, "INC-103", "Login page returns HTTP 500")

    fake_model = make_search_model()
    app.dependency_overrides[get_chat_model] = lambda: fake_model

    response = client.post("/incidents/INC-101/analyze")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_approval"
    assert body["analysis"] == ANALYSIS.model_dump()
    assert body["thread_id"]
    assert saved_analyses(db, body["thread_id"]) == []

    search_line = search_result_line(fake_model)
    assert "INC-102" in search_line
    assert "INC-101" not in search_line
    assert "INC-103" not in search_line
    assert "INC-101 repeats the CPU problem" in fake_model.report_prompts[0]


@pytest.mark.parametrize("approved", [True, False])
def test_search_shows_only_approved_analyses_of_similar_incidents(client, approved):
    create_incident(client, "INC-101", "Nightly payroll ETL job failed with a database timeout")
    create_incident(client, "INC-102", "Payroll ETL job timed out; database CPU at 95 percent")

    app.dependency_overrides[get_chat_model] = make_fake_model
    thread_id = client.post("/incidents/INC-102/analyze").json()["thread_id"]
    client.post(f"/analyses/{thread_id}/decision", json={"approved": approved})

    fake_model = make_search_model()
    app.dependency_overrides[get_chat_model] = lambda: fake_model
    client.post("/incidents/INC-101/analyze")

    search_line = search_result_line(fake_model)
    assert "INC-102" in search_line
    assert (ANALYSIS.probable_cause in search_line) == approved


def test_approving_saves_approved_analysis(client, db):
    thread_id = start_analysis(client)

    response = client.post(f"/analyses/{thread_id}/decision", json={"approved": True})

    assert response.status_code == 200
    assert response.json() == {"thread_id": thread_id, "status": "approved"}
    assert saved_analyses(db, thread_id) == [("approved", None, ANALYSIS.probable_cause)]


def test_rejecting_saves_rejected_analysis_with_comment(client, db):
    thread_id = start_analysis(client)

    response = client.post(
        f"/analyses/{thread_id}/decision",
        json={"approved": False, "comment": "Evidence is too thin"},
    )

    assert response.status_code == 200
    assert response.json() == {"thread_id": thread_id, "status": "rejected"}
    assert saved_analyses(db, thread_id) == [
        ("rejected", "Evidence is too thin", ANALYSIS.probable_cause)
    ]


def test_second_decision_returns_409(client, db):
    thread_id = start_analysis(client)
    client.post(f"/analyses/{thread_id}/decision", json={"approved": True})

    response = client.post(f"/analyses/{thread_id}/decision", json={"approved": False})

    assert response.status_code == 409
    assert response.json() == {"detail": "Analysis already decided"}
    assert saved_analyses(db, thread_id) == [("approved", None, ANALYSIS.probable_cause)]


def test_decision_for_unknown_thread_returns_404(client):
    app.dependency_overrides[get_chat_model] = make_fake_model

    response = client.post("/analyses/does-not-exist/decision", json={"approved": True})

    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis not found"}


def test_analyze_unknown_incident_returns_404_without_calling_model(client):
    fake_model = FakeAgentModel(messages=iter([]), analysis=ANALYSIS)
    app.dependency_overrides[get_chat_model] = lambda: fake_model

    response = client.post("/incidents/DOES-NOT-EXIST/analyze")

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}
    assert fake_model.report_prompts == []