"""Measures how well similar-incident search finds the right past incidents, and
which similarity threshold works best. Calls Voyage AI, so it is not part of the
test suite or CI.

Run: python -m evals.retrieval_eval
"""
import json
import os
from pathlib import Path

from app.config import SIMILARITY_THRESHOLD
from app.db import connect, setup_database
from app.embeddings import get_embeddings, to_pgvector

EVAL_DIR = Path(__file__).parent
EVAL_DB_NAME = "fixwright_eval"
# Same default limit as the search_similar_incidents tool
SEARCH_LIMIT = 5
THRESHOLDS = [round(0.30 + 0.05 * step, 2) for step in range(9)]

assert EVAL_DB_NAME != os.getenv("DB_NAME"), "Evals must not run against the development database"


def ensure_database():
    with connect(autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (EVAL_DB_NAME,)
        ).fetchone()
        if not exists:
            conn.execute(f"CREATE DATABASE {EVAL_DB_NAME}")
    setup_database(EVAL_DB_NAME)


def load_corpus(conn, embeddings, incidents):
    vectors = embeddings.embed_documents([incident["description"] for incident in incidents])
    with conn.cursor() as cursor:
        cursor.execute("TRUNCATE incidents CASCADE")
        for incident, vector in zip(incidents, vectors):
            cursor.execute(
                "INSERT INTO incidents (incident_id, description, embedding) VALUES (%s, %s, %s::vector)",
                (incident["incident_id"], incident["description"], to_pgvector(vector)),
            )
    conn.commit()


def rank(conn, embeddings, query):
    query_vector = to_pgvector(embeddings.embed_query(query))
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT incident_id, 1 - (embedding <=> %(query)s::vector) AS similarity
            FROM incidents
            ORDER BY embedding <=> %(query)s::vector
            LIMIT %(limit)s
            """,
            {"query": query_vector, "limit": SEARCH_LIMIT},
        )
        return cursor.fetchall()


def score(cases, rankings, threshold):
    true_pos = false_pos = false_neg = 0
    for case, ranking in zip(cases, rankings):
        found = {incident_id for incident_id, similarity in ranking if similarity >= threshold}
        relevant = set(case["relevant"])
        true_pos += len(found & relevant)
        false_pos += len(found - relevant)
        false_neg += len(relevant - found)

    precision = true_pos / (true_pos + false_pos) if true_pos + false_pos else 1.0
    recall = true_pos / (true_pos + false_neg) if true_pos + false_neg else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def main():
    incidents = json.loads((EVAL_DIR / "incidents.json").read_text())
    cases = json.loads((EVAL_DIR / "retrieval_cases.json").read_text())
    embeddings = get_embeddings()

    ensure_database()
    with connect(EVAL_DB_NAME) as conn:
        load_corpus(conn, embeddings, incidents)
        rankings = [rank(conn, embeddings, case["query"]) for case in cases]

    print("Top results per query (* = labeled relevant):")
    for case, ranking in zip(cases, rankings):
        print(f"\n{case['query']}")
        for incident_id, similarity in ranking:
            marker = "*" if incident_id in case["relevant"] else " "
            print(f"  {marker} {incident_id}  {similarity:.3f}")

    print(f"\n{'threshold':>9}  {'precision':>9}  {'recall':>6}  {'f1':>5}")
    for threshold in THRESHOLDS:
        precision, recall, f1 = score(cases, rankings, threshold)
        current = "  <- current" if threshold == SIMILARITY_THRESHOLD else ""
        print(f"{threshold:>9.2f}  {precision:>9.2f}  {recall:>6.2f}  {f1:>5.2f}{current}")


if __name__ == "__main__":
    main()