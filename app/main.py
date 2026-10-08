from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import psycopg
import os


app = FastAPI()
load_dotenv()

conn = psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)


@app.get("/health")
def health():
    return {"status" : "healthy" }


class Incident(BaseModel):
    incident_id : str
    description : str

class IncidentResponse(BaseModel):
    id: int 
    incident_id: str
    description: str

class IncidentUpdate(BaseModel):
    description: str

@app.post("/incidents")
def create_incident(incident: Incident):


    with conn.cursor() as cursor:
        cursor.execute(
            """ 
                INSERT INTO incidents (incident_id, description)
                VALUES (%s, %s)
            """,
            (incident.incident_id, incident.description)
        )

    conn.commit()


    return {
        "message": "Incident received",
        "incident_id": incident.incident_id,
        "description": incident.description
    }

@app.get("/incidents", response_model=list[IncidentResponse])
def get_incidents():
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
def update_incident(incident_id: str, incident: IncidentUpdate):
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
def delete_incident(incident_id: str):
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