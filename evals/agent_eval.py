"""Runs the full analysis agent with the real model on a few scenarios and checks the
result: did it search, cite the right past incidents, reuse approved analyses, keep
rejected ones out, and stay grounded in what the tools returned. Calls Anthropic and
Voyage AI, so it is not part of the test suite or CI.

Run: python -m evals.agent_eval
"""
import json
import os

# Must run before the app imports: keeps eval traces apart from normal local runs
# in LangSmith when tracing is on. load_dotenv() does not override it.
os.environ["LANGSMITH_PROJECT"] = "fixwright-evals"

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.agent.graph import build_agent
from app.agent.llm import get_chat_model
from app.db import connect
from app.embeddings import embed_for_storage, get_embeddings
from evals.retrieval_eval import EVAL_DB_NAME, EVAL_DIR, ensure_database, load_corpus

JUDGE_PROMPT = """You are reviewing an incident analysis written by an AI agent.

Tool results the agent saw:
{findings}

The agent's analysis:
{analysis}

Is every claim in the analysis supported by the tool results, with any guess clearly
marked as unconfirmed? Set grounded to false if the analysis states a cause or a fact
as certain when the tool results do not support it."""


class Verdict(BaseModel):
    reason: str = Field(description="One sentence explaining the verdict")
    grounded: bool = Field(description="True if the analysis only claims what the tool results support")


def add_reviewed_analyses(conn, reviewed):
    with conn.cursor() as cursor:
        for item in reviewed:
            cursor.execute(
                """
                INSERT INTO incident_analyses
                    (incident_id, thread_id, status, probable_cause, suggested_steps, evidence)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    item["incident_id"],
                    f"eval-{item['incident_id']}",
                    item["status"],
                    item["probable_cause"],
                    Jsonb(item["suggested_steps"]),
                    Jsonb([]),
                ),
            )
    conn.commit()


def run_case(conn, embeddings, case):
    """Adds the case's incident, runs the agent until it waits for approval, then
    removes the incident so it does not show up in the next case's search."""
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO incidents (incident_id, description, embedding) VALUES (%s, %s, %s::vector)",
            (case["incident_id"], case["description"], embed_for_storage(embeddings, case["description"])),
        )
    conn.commit()

    try:
        graph = build_agent(get_chat_model(), conn, embeddings, InMemorySaver())
        config = {
            "configurable": {"thread_id": case["incident_id"]},
            "run_name": "agent_eval",
            "metadata": {"incident_id": case["incident_id"]},
        }
        result = graph.invoke(
            {
                "incident_id": case["incident_id"],
                "messages": [HumanMessage(f"Analyze incident {case['incident_id']}")],
            },
            config,
        )
    finally:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM incidents WHERE incident_id = %s", (case["incident_id"],))
        conn.commit()

    tool_messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    return result["__interrupt__"][0].value["analysis"], tool_messages


def check(case, analysis, tool_messages, verdict):
    text = json.dumps(analysis).lower()
    evidence = " ".join(analysis["evidence"])
    called = {message.name for message in tool_messages}
    return {
        "searched": {"get_incident", "search_similar_incidents"} <= called,
        "cited expected": all(incident_id in evidence for incident_id in case["expected_ids"]),
        "used approved": all(phrase.lower() in text for phrase in case["required_phrases"]),
        "no forbidden": not any(phrase.lower() in text for phrase in case["forbidden_phrases"]),
        "grounded": verdict.grounded,
    }


def main():
    incidents = json.loads((EVAL_DIR / "incidents.json").read_text())
    reviewed = json.loads((EVAL_DIR / "reviewed_analyses.json").read_text())
    cases = json.loads((EVAL_DIR / "agent_cases.json").read_text())
    embeddings = get_embeddings()
    judge = get_chat_model().with_structured_output(Verdict, method="json_schema")

    ensure_database()
    all_checks = []
    with connect(EVAL_DB_NAME) as conn:
        load_corpus(conn, embeddings, incidents)
        add_reviewed_analyses(conn, reviewed)

        for case in cases:
            analysis, tool_messages = run_case(conn, embeddings, case)
            findings = "\n".join(f"[{message.name}] {message.content}" for message in tool_messages)
            verdict = judge.invoke([HumanMessage(JUDGE_PROMPT.format(
                findings=findings,
                analysis=json.dumps(analysis, indent=2),
            ))])
            checks = check(case, analysis, tool_messages, verdict)
            all_checks.append(checks)

            print(f"\n{case['incident_id']}: {case['description']}")
            print(f"  cause: {analysis['probable_cause']}")
            for name, passed in checks.items():
                print(f"  {'PASS' if passed else 'FAIL'}  {name}")
            print(f"  judge: {verdict.reason}")

    print("\nSummary:")
    for name in all_checks[0]:
        passed = sum(checks[name] for checks in all_checks)
        print(f"  {name:<15} {passed}/{len(all_checks)}")
    total = sum(sum(checks.values()) for checks in all_checks)
    print(f"  {'all checks':<15} {total}/{len(all_checks) * len(all_checks[0])}")


if __name__ == "__main__":
    main()