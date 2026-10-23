import os
import zlib

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


@pytest.fixture
def client(monkeypatch):
    reset_database()
    monkeypatch.setenv("FIXWRIGHT_API_KEY", TEST_API_KEY)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_checkpointer] = override_get_checkpointer
    app.dependency_overrides[get_embeddings] = lambda: FakeEmbeddings()

    with TestClient(app, headers={"X-API-Key": TEST_API_KEY}) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def db():
    with connect(TEST_DB_NAME, autocommit=True) as conn:
        yield conn


@pytest.fixture
def fake_embeddings():
    return FakeEmbeddings()