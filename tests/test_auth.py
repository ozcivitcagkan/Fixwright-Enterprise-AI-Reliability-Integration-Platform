import pytest

PROTECTED_ENDPOINTS = [
    ("POST", "/incidents"),
    ("GET", "/incidents"),
    ("PUT", "/incidents/INC-001"),
    ("DELETE", "/incidents/INC-001"),
    ("POST", "/incidents/INC-001/analyze"),
    ("POST", "/analyses/any-thread/decision"),
]


@pytest.mark.parametrize("method, path", PROTECTED_ENDPOINTS)
def test_protected_endpoint_without_api_key_returns_401(client, method, path):
    del client.headers["X-API-Key"]

    response = client.request(method, path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}
    assert response.headers["WWW-Authenticate"] == "APIKey"


def test_wrong_api_key_returns_401(client):
    response = client.get("/incidents", headers={"X-API-Key": "wrong-key"})

    assert response.status_code == 401


def test_health_does_not_need_api_key(client):
    del client.headers["X-API-Key"]

    response = client.get("/health")

    assert response.status_code == 200


def test_server_without_configured_key_rejects_requests(client, monkeypatch):
    monkeypatch.delenv("FIXWRIGHT_API_KEY")

    response = client.get("/incidents")

    assert response.status_code == 500
    assert response.json() == {"detail": "API key is not configured"}