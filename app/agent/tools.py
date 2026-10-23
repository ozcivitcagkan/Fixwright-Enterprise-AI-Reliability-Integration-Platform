import httpx
from langchain_core.tools import tool

from app.config import SIMILARITY_THRESHOLD
from app.embeddings import to_pgvector


def make_tools(conn, embeddings):
    @tool
    def get_incident(incident_id: str) -> dict:
        """Fetch a single incident by its incident_id, for example INC-101.
        Returns the incident's description, or an error if it does not exist."""
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT incident_id, description
                FROM incidents
                WHERE incident_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (incident_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return {"error": f"No incident found with incident_id {incident_id}"}

        return {"incident_id": row[0], "description": row[1]}

    @tool
    def search_similar_incidents(
        query: str,
        exclude_incident_id: str | None = None,
        limit: int = 5,
    ) -> list[dict] | dict:
        """Find past incidents that mean something similar to the query, even when
        they use different words. Pass a short description of the problem, for example
        "payroll job fails because the database is slow". Use exclude_incident_id to
        leave out the incident you are analyzing. Each result has a similarity score
        from 0 to 1 and, if a person approved an analysis for that incident, its
        probable cause and suggested steps."""
        try:
            query_vector = to_pgvector(embeddings.embed_query(query))
        except httpx.HTTPError:
            return {"error": "Similarity search is unavailable right now"}

        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT i.incident_id,
                       i.description,
                       1 - (i.embedding <=> %(query)s::vector) AS similarity,
                       a.probable_cause,
                       a.suggested_steps
                FROM incidents i
                LEFT JOIN LATERAL (
                    SELECT probable_cause, suggested_steps
                    FROM incident_analyses
                    WHERE incident_id = i.incident_id AND status = 'approved'
                    ORDER BY reviewed_at DESC
                    LIMIT 1
                ) a ON true
                WHERE i.embedding IS NOT NULL
                  AND i.incident_id IS DISTINCT FROM %(exclude)s
                  AND 1 - (i.embedding <=> %(query)s::vector) >= %(threshold)s
                ORDER BY i.embedding <=> %(query)s::vector
                LIMIT %(limit)s
                """,
                {
                    "query": query_vector,
                    "exclude": exclude_incident_id,
                    "threshold": SIMILARITY_THRESHOLD,
                    "limit": min(limit, 10),
                },
            )
            rows = cursor.fetchall()

        return [
            {
                "incident_id": incident_id,
                "description": description,
                "similarity": round(similarity, 3),
                "approved_analysis": (
                    {"probable_cause": probable_cause, "suggested_steps": suggested_steps}
                    if probable_cause is not None
                    else None
                ),
            }
            for incident_id, description, similarity, probable_cause, suggested_steps in rows
        ]

    return [get_incident, search_similar_incidents]