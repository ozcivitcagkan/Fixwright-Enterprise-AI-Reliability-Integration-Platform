from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg.errors import UniqueViolation
import psycopg

from app.agent.graph import AnalysisResult, build_agent
from app.agent.llm import get_chat_model
from app.db import connect, connect_checkpointer_db


app = FastAPI()
load_dotenv()

def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def get_checkpointer():
    conn = connect_checkpointer_db()
    try:
        yield PostgresSaver(conn)
    finally:
        conn.close()


@app.exception_handler(psycopg.OperationalError)
def database_unavailable(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": "Database unavailable"}
    )


@app.get("/health")
def health(conn = Depends(get_db)):
    conn.execute("SELECT 1")
    return {"status": "healthy", "database": "ok"}


IncidentId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class Incident(BaseModel):
    incident_id : IncidentId
    description : Description

class IncidentResponse(BaseModel):
    id: int 
    incident_id: str
    description: str

class IncidentUpdate(BaseModel):
    description: Description

class AnalysisPending(BaseModel):
    thread_id: str
    status: str
    analysis: AnalysisResult

class Decision(BaseModel):
    approved: bool
    comment: str | None = None

class DecisionResponse(BaseModel):
    thread_id: str
    status: str

@app.post("/incidents")
def create_incident(incident: Incident,
                    conn = Depends(get_db)
                    ):

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """ 
                    INSERT INTO incidents (incident_id, description)
                    VALUES (%s, %s)
                """,
                (incident.incident_id, incident.description)
            )
    except UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Incident already exists"
        )

    conn.commit()


    return {
        "message": "Incident received",
        "incident_id": incident.incident_id,
        "description": incident.description
    }

@app.get("/incidents", response_model=list[IncidentResponse])
def get_incidents(conn= Depends(get_db)):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, incident_id,description FROM incidents"
        )
        rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "incident_id": row[1],
            "description": row[2]
        }
        for row in rows
    ]


@app.put("/incidents/{incident_id}")
def update_incident(incident_id: str, 
                    incident: IncidentUpdate,
                    conn = Depends(get_db)
                    ):

    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE incidents
            SET description= %s
            WHERE incident_id= %s
            """,
            (incident.description,incident_id)
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code= 404,
                detail="Incident not found"
            )

    conn.commit()

    return {
    "message": "Incident updated",
    "incident_id": incident_id,
    "description": incident.description
    }

@app.delete("/incidents/{incident_id}")
def delete_incident(incident_id: str,
                    conn= Depends(get_db)
                    ):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM incidents
            WHERE incident_id= %s
            """,
            (incident_id,)
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Incident not found"
            )
    
    conn.commit()

    return {
        "message": "Incident deleted",
        "incident_id": incident_id
    }

@app.post("/incidents/{incident_id}/analyze", response_model=AnalysisPending)
def analyze_incident(incident_id: str,
                     conn = Depends(get_db),
                     checkpointer = Depends(get_checkpointer),
                     model = Depends(get_chat_model)
                     ):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM incidents WHERE incident_id = %s",
            (incident_id,)
        )
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Incident not found"
            )

    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    graph = build_agent(model, conn, checkpointer)
    result = graph.invoke(
        {
            "incident_id": incident_id,
            "messages": [HumanMessage(f"Analyze incident {incident_id}")],
        },
        config,
    )

    return {
        "thread_id": thread_id,
        "status": "pending_approval",
        "analysis": result["__interrupt__"][0].value["analysis"],
    }

@app.post("/analyses/{thread_id}/decision", response_model=DecisionResponse)
def decide_analysis(thread_id: str,
                    decision: Decision,
                    conn = Depends(get_db),
                    checkpointer = Depends(get_checkpointer),
                    model = Depends(get_chat_model)
                    ):
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_agent(model, conn, checkpointer)

    state = graph.get_state(config)
    if not state.values:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found"
        )
    if state.next != ("approval",):
        raise HTTPException(
            status_code=409,
            detail="Analysis already decided"
        )

    graph.invoke(Command(resume=decision.model_dump()), config)

    return {
        "thread_id": thread_id,
        "status": "approved" if decision.approved else "rejected",
    }