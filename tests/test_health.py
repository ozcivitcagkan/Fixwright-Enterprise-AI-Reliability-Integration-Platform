import psycopg

from app.main import app, get_db


def test_health_returns_healthy_when_database_is_up(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "ok"}


def test_health_returns_503_when_database_is_down(client):
    def broken_get_db():
        raise psycopg.OperationalError("connection refused")

    app.dependency_overrides[get_db] = broken_get_db

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}