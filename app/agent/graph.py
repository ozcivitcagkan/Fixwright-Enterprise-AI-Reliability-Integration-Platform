import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.agent.tools import make_tools

SYSTEM_PROMPT = """You are an incident analyst for an enterprise IT support team.
To investigate an incident, first call get_incident to read it. Then call
search_similar_incidents with a short description of the problem in your own words
to find related past incidents, excluding the incident itself. Results are ranked by
meaning and include a similarity score from 0 to 1. When a result has an approved
analysis, a person has already confirmed that cause and those steps for a similar
incident, so give it more weight than an unreviewed description. Base your
conclusion only on what the tools return, and say so when the evidence is thin."""

REPORT_PROMPT = """Below are the results of an incident investigation.

Tool results:
{findings}

Investigator's conclusion:
{conclusion}

Write the final analysis for the support engineer. Use only facts that appear above."""


class AnalysisResult(BaseModel):
    probable_cause: str = Field(description="The most likely root cause, in one or two sentences")
    suggested_steps: list[str] = Field(description="Concrete next steps for the support engineer, in order")
    evidence: list[str] = Field(description="Facts from the tool results that support the cause, citing incident IDs")


class AgentState(MessagesState):
    incident_id: str
    requested_by: str | None
    analysis: dict | None
    decision: dict | None
    saved: bool | None


def collect_similar_incidents(messages) -> list[dict]:
    """Structured list of the incidents the agent's searches found: for each one the
    highest similarity seen and whether it had an approved analysis. Error results,
    other tools and content that is not JSON are skipped."""
    found: dict[str, dict] = {}
    for message in messages:
        if not isinstance(message, ToolMessage) or message.name != "search_similar_incidents":
            continue
        try:
            results = json.loads(message.content)
        except (TypeError, ValueError):
            continue
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            entry = found.setdefault(
                result["incident_id"],
                {
                    "incident_id": result["incident_id"],
                    "similarity": result["similarity"],
                    "has_approved_analysis": False,
                },
            )
            entry["similarity"] = max(entry["similarity"], result["similarity"])
            if result.get("approved_analysis") is not None:
                entry["has_approved_analysis"] = True
    return sorted(found.values(), key=lambda item: item["similarity"], reverse=True)


def build_agent(model, conn, embeddings, checkpointer=None):
    tools = make_tools(conn, embeddings)
    model_with_tools = model.bind_tools(tools)
    report_model = model.with_structured_output(AnalysisResult, method="json_schema")

    def agent(state: AgentState):
        response = model_with_tools.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [response]}

    def respond(state: AgentState):
        findings = [
            f"[{message.name}] {message.content}"
            for message in state["messages"]
            if isinstance(message, ToolMessage)
        ]
        prompt = REPORT_PROMPT.format(
            findings="\n".join(findings),
            conclusion=state["messages"][-1].text,
        )
        analysis = report_model.invoke([HumanMessage(prompt)])
        return {"analysis": analysis.model_dump()}

    def record_pending(state: AgentState, config: RunnableConfig):
        # Runs once: the checkpoint after this node means a resume does not repeat it
        analysis = state["analysis"]

        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO incident_analyses
                    (incident_id, thread_id, status, probable_cause, suggested_steps,
                     evidence, similar_incidents, requested_by)
                VALUES (%s, %s, 'pending', %s, %s, %s, %s, %s)
                ON CONFLICT (thread_id) DO NOTHING
                """,
                (
                    state["incident_id"],
                    config["configurable"]["thread_id"],
                    analysis["probable_cause"],
                    Jsonb(analysis["suggested_steps"]),
                    Jsonb(analysis["evidence"]),
                    Jsonb(collect_similar_incidents(state["messages"])),
                    state.get("requested_by"),
                ),
            )
        conn.commit()
        return {}

    def approval(state: AgentState):
        decision = interrupt({
            "incident_id": state["incident_id"],
            "analysis": state["analysis"],
        })
        return {"decision": decision}

    def save(state: AgentState, config: RunnableConfig):
        decision = state["decision"]

        # Only a row that is still pending can be decided, so two decisions at the
        # same time cannot both win: the second one updates nothing.
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE incident_analyses
                SET status = %s, reviewer_comment = %s, decided_by = %s, reviewed_at = now()
                WHERE thread_id = %s AND status = 'pending'
                """,
                (
                    "approved" if decision["approved"] else "rejected",
                    decision.get("comment"),
                    decision.get("decided_by"),
                    config["configurable"]["thread_id"],
                ),
            )
            saved = cursor.rowcount == 1
        conn.commit()
        return {"saved": saved}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("respond", respond)
    builder.add_node("record_pending", record_pending)
    builder.add_node("approval", approval)
    builder.add_node("save", save)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "respond"})
    builder.add_edge("tools", "agent")
    builder.add_edge("respond", "record_pending")
    builder.add_edge("record_pending", "approval")
    builder.add_edge("approval", "save")
    builder.add_edge("save", END)

    return builder.compile(checkpointer=checkpointer)