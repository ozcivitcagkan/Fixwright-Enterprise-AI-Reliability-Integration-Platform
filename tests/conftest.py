import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.main import app, get_db

load_dotenv()

TEST_DB_NAME = os.getenv("TEST_DB_NAME", "fixwright_test")

assert TEST_DB_NAME != os.getenv("DB_NAME"), "Tests must not run against the development database"


def connect_test_db():
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=TEST_DB_NAME,
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def override_get_db():
    conn = connect_test_db()
    try:
        yield conn
    finally:
        conn.close()


SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def reset_incidents_table():
    with connect_test_db() as conn:
        conn.execute("DROP TABLE IF EXISTS incident_analyses, incidents")
        conn.execute(SCHEMA_PATH.read_text())


@pytest.fixture
def client():
    reset_incidents_table()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()