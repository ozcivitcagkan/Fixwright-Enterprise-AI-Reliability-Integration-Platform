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


def test_analyze_runs_tools_and_returns_analysis(client):
    create_incident(client, "INC-101", "Nightly payroll ETL job failed with a database timeout")
    create_incident(client, "INC-102", "Payroll ETL job timed out; database CPU at 95 percent")
    create_incident(client, "INC-103", "Login page returns HTTP 500")

    fake_model = FakeAgentModel(
        messages=iter([
            AIMessage(content="", tool_calls=[
                tool_call("get_incident", {"incident_id": "INC-101"}, "call_1"),
            ]),
            AIMessage(content="", tool_calls=[
                tool_call(
                    "search_similar_incidents",
                    {"keywords": "payroll database", "exclude_incident_id": "INC-101"},
                    "call_2",
                ),
            ]),
            AIMessage(content="INC-101 repeats the CPU problem seen in INC-102."),
        ]),
        analysis=ANALYSIS,
    )
    app.dependency_overrides[get_chat_model] = lambda: fake_model

    response = client.post("/incidents/INC-101/analyze")

    assert response.status_code == 200
    assert response.json() == ANALYSIS.model_dump()

    report_prompt = fake_model.report_prompts[0]
    search_line = next(
        line for line in report_prompt.splitlines()
        if line.startswith("[search_similar_incidents]")
    )
    assert "INC-102" in search_line
    assert "INC-101" not in search_line
    assert "INC-103" not in search_line
    assert "INC-101 repeats the CPU problem" in report_prompt


def test_analyze_unknown_incident_returns_404_without_calling_model(client):
    fake_model = FakeAgentModel(messages=iter([]), analysis=ANALYSIS)
    app.dependency_overrides[get_chat_model] = lambda: fake_model

    response = client.post("/incidents/DOES-NOT-EXIST/analyze")

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}
    assert fake_model.report_prompts == []