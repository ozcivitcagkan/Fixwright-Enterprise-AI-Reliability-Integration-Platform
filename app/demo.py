from fastapi import HTTPException

from app.config import (
    DEMO_DAILY_ANALYSIS_LIMIT,
    DEMO_DAILY_INCIDENT_LIMIT,
    DEMO_MAX_DESCRIPTION_LENGTH,
)

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