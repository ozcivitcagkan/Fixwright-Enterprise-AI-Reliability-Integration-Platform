import pytest

from app.auth import session_https_only, session_secret
from tests.conftest import WEB, sign_in_admin, sign_in_demo

PROTECTED_ENDPOINTS = [
    ("POST", "/incidents"),
    ("GET", "/incidents"),
    ("GET", "/incidents/INC-001"),
    ("GET", "/incidents/INC-001/analyses"),
    ("GET", "/analyses?status=pending"),
    ("PUT", "/incidents/INC-001"),
    ("DELETE", "/incidents/INC-001"),
    ("POST", "/incidents/INC-001/analyze"),
    ("POST", "/analyses/any-thread/decision"),
    ("GET", "/auth/me"),
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


def test_session_secret_must_be_set_and_long_enough(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "too-short")
    with pytest.raises(RuntimeError):
        session_secret()

    monkeypatch.delenv("SESSION_SECRET")
    with pytest.raises(RuntimeError):
        session_secret()


def test_session_secret_accepts_32_characters(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)

    assert session_secret() == "s" * 32


@pytest.mark.parametrize(
    "value, expected",
    [(None, True), ("false", False), ("FALSE", False), ("true", True), ("0", True)],
)
def test_session_cookie_is_secure_unless_explicitly_turned_off(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("SESSION_HTTPS_ONLY", raising=False)
    else:
        monkeypatch.setenv("SESSION_HTTPS_ONLY", value)

    assert session_https_only() is expected


def test_demo_sign_in_sets_strict_secure_cookie(client):
    response = sign_in_demo(client)

    name_and_value, *flags = [part.strip() for part in response.headers["set-cookie"].lower().split(";")]
    assert name_and_value.startswith("fixwright_session=")
    for flag in ["httponly", "samesite=strict", "secure", "max-age=28800"]:
        assert flag in flags
    assert response.json() == {"role": "demo", "demo_analyses_left": 30}


def test_demo_session_works_without_api_key(client):
    sign_in_demo(client)

    assert client.get("/incidents").status_code == 200
    assert client.get("/auth/me").json() == {"role": "demo", "demo_analyses_left": 30}


def test_demo_sign_in_requires_client_header(client):
    del client.headers["X-API-Key"]

    response = client.post("/auth/demo")

    assert response.status_code == 403
    assert response.json() == {"detail": "Missing X-Fixwright-Client header"}


def test_session_post_without_client_header_returns_403(client):
    sign_in_demo(client)
    del client.headers["X-Fixwright-Client"]

    response = client.post("/incidents", json={"incident_id": "INC-1", "description": "Disk full"})

    assert response.status_code == 403
    assert response.json() == {"detail": "Missing X-Fixwright-Client header"}


def test_admin_login_with_correct_key(client):
    response = sign_in_admin(client)

    assert response.json() == {"role": "admin"}
    assert client.get("/auth/me").json() == {"role": "admin"}


def test_admin_login_with_wrong_key_returns_401(client):
    del client.headers["X-API-Key"]
    client.headers.update(WEB)

    response = client.post("/auth/login", json={"api_key": "wrong-key"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}
    assert client.get("/auth/me").status_code == 401


def test_api_key_request_has_api_role(client):
    assert client.get("/auth/me").json() == {"role": "api"}


def test_wrong_api_key_beats_valid_session(client):
    sign_in_demo(client)

    response = client.get("/incidents", headers={"X-API-Key": "wrong-key"})

    assert response.status_code == 401


def test_logout_clears_session(client):
    sign_in_demo(client)

    response = client.post("/auth/logout")

    assert response.json() == {"message": "Signed out"}
    assert client.get("/incidents").status_code == 401


def test_tampered_cookie_is_ignored(client):
    sign_in_demo(client)
    client.cookies.clear()

    response = client.get("/incidents", headers={"Cookie": "fixwright_session=forged-value"})

    assert response.status_code == 401


def test_incident_records_who_created_it(client, db):
    client.post("/incidents", json={"incident_id": "INC-1", "description": "Disk full"})
    sign_in_admin(client)
    client.post("/incidents", json={"incident_id": "INC-2", "description": "Printer jam"})

    rows = db.execute("SELECT incident_id, created_by FROM incidents ORDER BY id").fetchall()
    assert rows == [("INC-1", "api"), ("INC-2", "admin")]