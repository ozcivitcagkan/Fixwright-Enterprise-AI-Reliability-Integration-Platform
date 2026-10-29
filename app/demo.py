from fastapi import HTTPException
from langgraph.checkpoint.postgres import PostgresSaver

from app.config import (
    DEMO_DAILY_ANALYSIS_LIMIT,
    DEMO_DAILY_INCIDENT_LIMIT,
    DEMO_MAX_DESCRIPTION_LENGTH,
    DEMO_RETENTION_DAYS,
)
from app.db import connect, connect_checkpointer_db

LIMIT_REACHED = "Daily demo limit reached"


def demo_analyses_used_today(conn) -> int:
    return conn.execute(
        """
        SELECT count(*)
        FROM incident_analyses
        WHERE requested_by = 'demo' AND created_at >= date_trunc('day', now(), 'UTC')
        """
    ).fetchone()[0]


def demo_incidents_created_today(conn) -> int:
    return conn.execute(
        """
        SELECT count(*)
        FROM incidents
        WHERE created_by = 'demo' AND created_at >= date_trunc('day', now(), 'UTC')
        """
    ).fetchone()[0]


def demo_analyses_left(conn) -> int:
    return max(0, DEMO_DAILY_ANALYSIS_LIMIT - demo_analyses_used_today(conn))


def ensure_demo_can_analyze(conn) -> None:
    if demo_analyses_left(conn) == 0:
        raise HTTPException(status_code=429, detail=LIMIT_REACHED)


def ensure_demo_can_create(conn, description: str) -> None:
    if len(description) > DEMO_MAX_DESCRIPTION_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Description is limited to {DEMO_MAX_DESCRIPTION_LENGTH} characters in the demo",
        )
    if demo_incidents_created_today(conn) >= DEMO_DAILY_INCIDENT_LIMIT:
        raise HTTPException(status_code=429, detail=LIMIT_REACHED)


def ensure_not_demo(role: str) -> None:
    if role == "demo":
        raise HTTPException(
            status_code=403,
            detail="Demo users cannot change or delete incidents",
        )


def delete_old_demo_data(conn, checkpointer) -> dict[str, int]:
    """Deletes demo incidents and demo analyses older than DEMO_RETENTION_DAYS,
    together with the LangGraph checkpoints of those analyses."""
    retention = {"days": DEMO_RETENTION_DAYS}
    with conn.cursor() as cursor:
        # Collected first: the incident delete below also removes the analyses of
        # old demo incidents (ON DELETE CASCADE), even analyses that are still new
        cursor.execute(
            """
            SELECT a.thread_id
            FROM incident_analyses a
            JOIN incidents i ON i.incident_id = a.incident_id
            WHERE (a.requested_by = 'demo' AND a.created_at < now() - make_interval(days => %(days)s))
               OR (i.created_by = 'demo' AND i.created_at < now() - make_interval(days => %(days)s))
            """,
            retention,
        )
        thread_ids = [row[0] for row in cursor.fetchall()]

        cursor.execute(
            """
            DELETE FROM incidents
            WHERE created_by = 'demo' AND created_at < now() - make_interval(days => %(days)s)
            """,
            retention,
        )
        deleted_incidents = cursor.rowcount

        cursor.execute(
            """
            DELETE FROM incident_analyses
            WHERE requested_by = 'demo' AND created_at < now() - make_interval(days => %(days)s)
            """,
            retention,
        )
    conn.commit()

    # Checkpoints live in LangGraph's own tables, with no foreign key to ours
    for thread_id in thread_ids:
        checkpointer.delete_thread(thread_id)

    return {"incidents": deleted_incidents, "analyses": len(thread_ids)}


def run_demo_cleanup() -> None:
    with connect() as conn, connect_checkpointer_db() as checkpointer_conn:
        counts = delete_old_demo_data(conn, PostgresSaver(checkpointer_conn))
    print(f"Deleted {counts['incidents']} old demo incidents and {counts['analyses']} old demo analyses")


if __name__ == "__main__":
    run_demo_cleanup()