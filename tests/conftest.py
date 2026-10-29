import os
import zlib

# Must run before the app imports below: app.db calls load_dotenv(), which would
# otherwise turn on LangSmith tracing from .env and send fake test runs to LangSmith.
os.environ["LANGSMITH_TRACING"] = "false"
# The app refuses to start without a session secret. Tests also use the production
# cookie flags (Secure), even when the local .env turns them off for plain http.
os.environ["SESSION_SECRET"] = "test-session-secret-" + "x" * 32
os.environ["SESSION_HTTPS_ONLY"] = "true"

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from langgraph.checkpoint.postgres import PostgresSaver

from app.config import EMBEDDING_DIMENSIONS
from app.db import connect, connect_checkpointer_db, setup_database
from app.embeddings import get_embeddings
from app.main import app, get_checkpointer, get_db

load_dotenv()

TEST_DB_NAME = os.getenv("TEST_DB_NAME", "fixwright_test")
TEST_API_KEY = "test-api-key"
# The header the web UI sends with every request that changes something
WEB = {"X-Fixwright-Client": "web"}

assert TEST_DB_NAME != os.getenv("DB_NAME"), "Tests must not run against the development database"


class FakeEmbeddings(Embeddings):
    """Embeds text without calling Voyage. Each word adds 1 to a fixed position,
    so texts that share words get similar vectors."""

    def embed_query(self, text):
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for word in text.lower().split():
            vector[zlib.crc32(word.encode()) % EMBEDDING_DIMENSIONS] += 1.0
        return vector

    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]


def override_get_db():
    conn = connect(TEST_DB_NAME)
    try:
        yield conn
    finally:
        conn.close()


def override_get_checkpointer():
    conn = connect_checkpointer_db(TEST_DB_NAME)
    try:
        yield PostgresSaver(conn)
    finally:
        conn.close()


def reset_database():
    with connect(TEST_DB_NAME) as conn:
        conn.execute("DROP TABLE IF EXISTS incident_analyses, incidents")
    setup_database(TEST_DB_NAME)


def sign_in(client, path, body=None):
    """Signs in like the web UI does: no API key, the web header, a session cookie."""
    client.headers.pop("X-API-Key", None)
    client.headers.update(WEB)
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    return response


def sign_in_demo(client):
    return sign_in(client, "/auth/demo")


def sign_in_admin(client):
    return sign_in(client, "/auth/login", {"api_key": TEST_API_KEY})


@pytest.fixture
def client(monkeypatch):
    reset_database()
    monkeypatch.setenv("FIXWRIGHT_API_KEY", TEST_API_KEY)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_checkpointer] = override_get_checkpointer
    app.dependency_overrides[get_embeddings] = lambda: FakeEmbeddings()

    # https, because the browser only sends the Secure session cookie back over https
    with TestClient(app, base_url="https://testserver", headers={"X-API-Key": TEST_API_KEY}) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def db():
    with connect(TEST_DB_NAME, autocommit=True) as conn:
        yield conn


@pytest.fixture
def fake_embeddings():
    return FakeEmbeddings()