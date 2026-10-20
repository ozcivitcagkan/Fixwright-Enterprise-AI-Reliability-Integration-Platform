from typing import Annotated

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from psycopg.errors import UniqueViolation
import psycopg
import os

from app.agent.graph import AnalysisResult, build_agent
from app.agent.llm import get_chat_model


app = FastAPI()
load_dotenv()

def get_db():
    conn= psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
 
    try:
        yield conn
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

@app.post("/incidents/{incident_id}/analyze", response_model=AnalysisResult)
def analyze_incident(incident_id: str,
                     conn = Depends(get_db),
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

    graph = build_agent(model, conn)
    result = graph.invoke(
        {"messages": [HumanMessage(f"Analyze incident {incident_id}")]}
    )

    return result["analysis"]