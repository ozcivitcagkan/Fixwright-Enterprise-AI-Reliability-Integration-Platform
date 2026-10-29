from fastapi.testclient import TestClient

from app.embeddings import get_embeddings
from app.main import app
from tests.conftest import TEST_API_KEY


def test_api_response_has_security_headers(client):
    headers = client.get("/health").headers

    policy = headers["content-security-policy"]
    assert "default-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "unsafe-inline" not in policy
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "same-origin"
    assert headers["strict-transport-security"] == "max-age=31536000"


def test_error_responses_also_have_security_headers(client):
    del client.headers["X-API-Key"]

    response = client.get("/incidents")

    assert response.status_code == 401
    assert "content-security-policy" in response.headers


def test_docs_page_gets_docs_policy(client):
    response = client.get("/docs")

    assert response.status_code == 200
    policy = response.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in policy
    assert "frame-ancestors 'none'" in policy


def test_unhandled_error_hides_details(client):
    def broken_embeddings():
        raise RuntimeError("VOYAGE_API_KEY is not set")

    app.dependency_overrides[get_embeddings] = broken_embeddings

    # This client returns the 500 response instead of raising the error in the test
    with TestClient(
        app,
        base_url="https://testserver",
        raise_server_exceptions=False,
        headers={"X-API-Key": TEST_API_KEY},
    ) as quiet_client:
        response = quiet_client.post("/incidents", json={"incident_id": "INC-1", "description": "Disk full"})

    assert response.status_code == 500
    assert "VOYAGE_API_KEY" not in response.text
    assert "Traceback" not in response.text