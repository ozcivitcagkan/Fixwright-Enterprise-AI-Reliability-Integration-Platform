CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    embedding vector(1024),
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Older databases (dev, Neon) already have the tables, so CREATE TABLE IF NOT EXISTS
-- does not add later columns there. Every change below must be safe to run again.
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS embedding vector(1024);
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS created_by VARCHAR(255);
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS incidents_embedding_idx
    ON incidents USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS incident_analyses (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) NOT NULL REFERENCES incidents (incident_id) ON DELETE CASCADE,
    thread_id VARCHAR(100) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL,
    probable_cause TEXT NOT NULL,
    suggested_steps JSONB NOT NULL,
    evidence JSONB NOT NULL,
    similar_incidents JSONB NOT NULL DEFAULT '[]',
    reviewer_comment TEXT,
    requested_by VARCHAR(255),
    decided_by VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ
);

ALTER TABLE incident_analyses ADD COLUMN IF NOT EXISTS similar_incidents JSONB NOT NULL DEFAULT '[]';
ALTER TABLE incident_analyses ADD COLUMN IF NOT EXISTS requested_by VARCHAR(255);
ALTER TABLE incident_analyses ADD COLUMN IF NOT EXISTS decided_by VARCHAR(255);
ALTER TABLE incident_analyses ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Pending analyses are stored before anyone has reviewed them
ALTER TABLE incident_analyses ALTER COLUMN reviewed_at DROP NOT NULL;
ALTER TABLE incident_analyses ALTER COLUMN reviewed_at DROP DEFAULT;
ALTER TABLE incident_analyses DROP CONSTRAINT IF EXISTS incident_analyses_status_check;
ALTER TABLE incident_analyses ADD CONSTRAINT incident_analyses_status_check
    CHECK (status IN ('pending', 'approved', 'rejected'));