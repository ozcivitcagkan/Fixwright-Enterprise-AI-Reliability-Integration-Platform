from datetime import datetime
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from starlette.middleware.sessions import SessionMiddleware
import psycopg

from app.agent.graph import AnalysisResult, build_agent
from app.agent.llm import get_chat_model
from app.auth import (
    check_api_key,
    require_auth,
    require_web_client,
    session_https_only,
    session_secret,
)
from app.config import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS
from app.db import connect, connect_checkpointer_db
from app.demo import (
    demo_analyses_left,
    ensure_demo_can_analyze,
    ensure_demo_can_create,
    ensure_not_demo,
)
from app.embeddings import embed_for_storage, get_embeddings


app = FastAPI()
load_dotenv()

# The cookie holds only the role, signed with SESSION_SECRET. The app does not start without it.
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    session_cookie=SESSION_COOKIE_NAME,
    max_age=SESSION_MAX_AGE_SECONDS,
    same_site="strict",
    https_only=session_https_only(),
)


# Only files from this site may run, and no other site may frame these pages
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
# Swagger UI loads its files from the jsDelivr CDN and starts with an inline script
DOCS_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; object-src 'none'; frame-ancestors 'none'"
)
DOCS_PATHS = {"/docs", "/docs/oauth2-redirect", "/redoc"}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        DOCS_CONTENT_SECURITY_POLICY if request.url.path in DOCS_PATHS else CONTENT_SECURITY_POLICY
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    # Browsers ignore this header over plain http, and local development uses http
    if session_https_only():
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response

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
    latest_status: str | None = None

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

class SimilarIncident(BaseModel):
    incident_id: str
    similarity: float
    has_approved_analysis: bool

class AnalysisRecord(BaseModel):
    thread_id: str
    status: str
    analysis: AnalysisResult
    similar_incidents: list[SimilarIncident]
    reviewer_comment: str | None
    requested_by: str | None
    decided_by: str | None
    created_at: datetime
    reviewed_at: datetime | None

class PendingAnalysis(BaseModel):
    thread_id: str
    incident_id: str
    description: str
    probable_cause: str
    created_at: datetime

class LoginRequest(BaseModel):
    api_key: str

class Me(BaseModel):
    role: str
    demo_analyses_left: int | None = None


@app.post("/auth/demo", response_model=Me, response_model_exclude_none=True,
          dependencies=[Depends(require_web_client)])
def sign_in_as_demo(request: Request,
                    conn = Depends(get_db)
                    ):
    request.session.clear()
    request.session["role"] = "demo"
    return {"role": "demo", "demo_analyses_left": demo_analyses_left(conn)}


@app.post("/auth/login", response_model=Me, response_model_exclude_none=True,
          dependencies=[Depends(require_web_client)])
def sign_in_as_admin(login: LoginRequest, request: Request):
    if not check_api_key(login.api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    request.session.clear()
    request.session["role"] = "admin"
    return {"role": "admin"}


@app.post("/auth/logout", dependencies=[Depends(require_web_client)])
def sign_out(request: Request):
    request.session.clear()
    return {"message": "Signed out"}


@app.get("/auth/me", response_model=Me, response_model_exclude_none=True)
def who_am_i(role: str = Depends(require_auth),
             conn = Depends(get_db)
             ):
    if role == "demo":
        return {"role": role, "demo_analyses_left": demo_analyses_left(conn)}
    return {"role": role}


@app.post("/incidents")
def create_incident(incident: Incident,
                    role: str = Depends(require_auth),
                    conn = Depends(get_db),
                    embeddings = Depends(get_embeddings)
                    ):
    # Checked before embedding so a refused request costs no Voyage call
    if role == "demo":
        ensure_demo_can_create(conn, incident.description)

    embedding = embed_for_storage(embeddings, incident.description)

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """ 
                    INSERT INTO incidents (incident_id, description, embedding, created_by)
                    VALUES (%s, %s, %s::vector, %s)
                """,
                (incident.incident_id, incident.description, embedding, role)
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

# Each incident with the status of its newest analysis (empty when it has none)
INCIDENTS_WITH_LATEST_STATUS = """
    SELECT i.id, i.incident_id, i.description, a.status AS latest_status
    FROM incidents i
    LEFT JOIN LATERAL (
        SELECT status
        FROM incident_analyses
        WHERE incident_id = i.incident_id
        ORDER BY created_at DESC, id DESC
        LIMIT 1
    ) a ON true
"""

@app.get("/incidents", response_model=list[IncidentResponse], dependencies=[Depends(require_auth)])
def get_incidents(conn= Depends(get_db)):
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(INCIDENTS_WITH_LATEST_STATUS + " ORDER BY i.id DESC")
        return cursor.fetchall()


@app.get("/incidents/{incident_id}", response_model=IncidentResponse, dependencies=[Depends(require_auth)])
def get_incident(incident_id: str,
                 conn = Depends(get_db)
                 ):
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(INCIDENTS_WITH_LATEST_STATUS + " WHERE i.incident_id = %s", (incident_id,))
        incident = cursor.fetchone()

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )
    return incident


@app.get("/incidents/{incident_id}/analyses", response_model=list[AnalysisRecord],
         dependencies=[Depends(require_auth)])
def get_incident_analyses(incident_id: str,
                          conn = Depends(get_db)
                          ):
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT 1 AS found FROM incidents WHERE incident_id = %s", (incident_id,))
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Incident not found"
            )

        cursor.execute(
            """
            SELECT thread_id, status, probable_cause, suggested_steps, evidence,
                   similar_incidents, reviewer_comment, requested_by, decided_by,
                   created_at, reviewed_at
            FROM incident_analyses
            WHERE incident_id = %s
            ORDER BY created_at DESC, id DESC
            """,
            (incident_id,)
        )
        rows = cursor.fetchall()

    return [
        {
            "thread_id": row["thread_id"],
            "status": row["status"],
            "analysis": {
                "probable_cause": row["probable_cause"],
                "suggested_steps": row["suggested_steps"],
                "evidence": row["evidence"],
            },
            "similar_incidents": row["similar_incidents"],
            "reviewer_comment": row["reviewer_comment"],
            "requested_by": row["requested_by"],
            "decided_by": row["decided_by"],
            "created_at": row["created_at"],
            "reviewed_at": row["reviewed_at"],
        }
        for row in rows
    ]


@app.get("/analyses", response_model=list[PendingAnalysis], dependencies=[Depends(require_auth)])
def get_analyses(status: Literal["pending"],
                 conn = Depends(get_db)
                 ):
    # Only the queue of analyses waiting for a decision exists for now
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT a.thread_id, a.incident_id, i.description, a.probable_cause, a.created_at
            FROM incident_analyses a
            JOIN incidents i ON i.incident_id = a.incident_id
            WHERE a.status = 'pending'
            ORDER BY a.created_at, a.id
            """
        )
        return cursor.fetchall()


@app.put("/incidents/{incident_id}")
def update_incident(incident_id: str, 
                    incident: IncidentUpdate,
                    role: str = Depends(require_auth),
                    conn = Depends(get_db),
                    embeddings = Depends(get_embeddings)
                    ):
    ensure_not_demo(role)

    embedding = embed_for_storage(embeddings, incident.description)

    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE incidents
            SET description= %s, embedding= %s::vector
            WHERE incident_id= %s
            """,
            (incident.description, embedding, incident_id)
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
                    role: str = Depends(require_auth),
                    conn= Depends(get_db)
                    ):
    ensure_not_demo(role)

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
                     role: str = Depends(require_auth),
                     conn = Depends(get_db),
                     checkpointer = Depends(get_checkpointer),
                     model = Depends(get_chat_model),
                     embeddings = Depends(get_embeddings)
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

    # Checked before the agent runs so a refused request costs no model call
    if role == "demo":
        ensure_demo_can_analyze(conn)

    thread_id = str(uuid4())
    config = {
        "configurable": {"thread_id": thread_id},
        # Shown in LangSmith traces so runs can be found by incident
        "run_name": "analyze_incident",
        "tags": ["analyze"],
        "metadata": {"incident_id": incident_id},
    }

    graph = build_agent(model, conn, embeddings, checkpointer)
    result = graph.invoke(
        {
            "incident_id": incident_id,
            "requested_by": role,
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
                    role: str = Depends(require_auth),
                    conn = Depends(get_db),
                    checkpointer = Depends(get_checkpointer),
                    model = Depends(get_chat_model),
                    embeddings = Depends(get_embeddings)
                    ):
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_agent(model, conn, embeddings, checkpointer)

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

    result = graph.invoke(
        Command(resume={**decision.model_dump(), "decided_by": role}),
        {
            **config,
            "run_name": "decide_analysis",
            "tags": ["decision"],
            "metadata": {
                "incident_id": state.values["incident_id"],
                "approved": decision.approved,
            },
        },
    )

    # The decision lost a race (someone decided first) or the analysis has no pending row
    if not result.get("saved"):
        raise HTTPException(
            status_code=409,
            detail="Analysis already decided"
        )

    return {
        "thread_id": thread_id,
        "status": "approved" if decision.approved else "rejected",
    }