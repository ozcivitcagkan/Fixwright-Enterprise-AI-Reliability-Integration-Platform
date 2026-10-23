CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    embedding vector(1024)
);

-- Databases created before the RAG phase (dev, Neon) already have the table,
-- so CREATE TABLE IF NOT EXISTS above does not add the column there.
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS embedding vector(1024);

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