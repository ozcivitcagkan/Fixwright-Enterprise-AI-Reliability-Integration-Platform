from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field

from app.agent.tools import make_tools

SYSTEM_PROMPT = """You are an incident analyst for an enterprise IT support team.
To investigate an incident, first call get_incident to read it. Then call
search_similar_incidents with a few keywords from its description to find related
past incidents, excluding the incident itself. Base your conclusion only on what
the tools return, and say so when the evidence is thin."""

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
    analysis: AnalysisResult | None


def build_agent(model, conn):
    tools = make_tools(conn)
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
        return {"analysis": analysis}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("respond", respond)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "respond"})
    builder.add_edge("tools", "agent")
    builder.add_edge("respond", END)

    return builder.compile()