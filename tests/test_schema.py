from psycopg.errors import CheckViolation
import pytest

from app.db import setup_database
from tests.conftest import TEST_DB_NAME, reset_database

# db/schema.sql as it was before pending analyses were stored. The development
# and production databases were created from it, so the current schema must
# upgrade it in place without losing rows.
OLD_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    embedding vector(1024)
);

CREATE INDEX IF NOT EXISTS incidents_embedding_idx
    ON incidents USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS incident_analyses (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) NOT NULL REFERENCES incidents (incident_id) ON DELETE CASCADE,
    thread_id VARCHAR(100) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('approved', 'rejected')),
    probable_cause TEXT NOT NULL,
    suggested_steps JSONB NOT NULL,
    evidence JSONB NOT NULL,
    reviewer_comment TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def insert_incident(db, incident_id="INC-1"):
    db.execute(
        "INSERT INTO incidents (incident_id, description) VALUES (%s, 'Disk full')",
        (incident_id,),
    )


def insert_analysis(db, status, thread_id="thread-1"):
    db.execute(
        """
        INSERT INTO incident_analyses
            (incident_id, thread_id, status, probable_cause, suggested_steps, evidence)
        VALUES ('INC-1', %s, %s, 'Log rotation stopped', '[]', '[]')
        """,
        (thread_id, status),
    )


def test_schema_migrates_old_database_twice(db):
    db.execute("DROP TABLE IF EXISTS incident_analyses, incidents")
    db.execute(OLD_SCHEMA)
    insert_incident(db)
    insert_analysis(db, "approved", thread_id="old-thread")

    setup_database(TEST_DB_NAME)
    setup_database(TEST_DB_NAME)

    status, created_at, reviewed_at, similar_incidents, requested_by = db.execute(
        """
        SELECT status, created_at, reviewed_at, similar_incidents, requested_by
        FROM incident_analyses
        WHERE thread_id = 'old-thread'
        """
    ).fetchone()
    assert status == "approved"
    assert created_at is not None
    assert reviewed_at is not None
    assert similar_incidents == []
    assert requested_by is None

    incident_created_at = db.execute(
        "SELECT created_at FROM incidents WHERE incident_id = 'INC-1'"
    ).fetchone()[0]
    assert incident_created_at is not None


def test_pending_analysis_without_reviewed_at_is_allowed(db):
    reset_database()
    insert_incident(db)

    insert_analysis(db, "pending")

    reviewed_at = db.execute(
        "SELECT reviewed_at FROM incident_analyses WHERE thread_id = 'thread-1'"
    ).fetchone()[0]
    assert reviewed_at is None


def test_unknown_status_is_rejected(db):
    reset_database()
    insert_incident(db)

    with pytest.raises(CheckViolation):
        insert_analysis(db, "bogus")