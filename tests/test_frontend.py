import pytest

from app import frontend


@pytest.fixture
def dist(tmp_path, monkeypatch):
    """A tiny stand-in for the built web app, with a file next to it that must never be served."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>fixwright app</html>")
    (dist / "assets" / "app.js").write_text('console.log("app")')
    (tmp_path / "secret.txt").write_text("secret")
    monkeypatch.setattr(frontend, "FRONTEND_DIST", dist)
    return dist


def test_root_redirects_to_ui(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/ui/"


def test_ui_serves_index_for_app_routes(client, dist):
    for path in ["/ui/", "/ui/login", "/ui/incidents/INC-1"]:
        response = client.get(path)

        assert response.status_code == 200
        assert "fixwright app" in response.text
        assert response.headers["cache-control"] == "no-cache"


def test_ui_serves_assets_with_long_cache(client, dist):
    response = client.get("/ui/assets/app.js")

    assert response.text == 'console.log("app")'
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_missing_asset_returns_404(client, dist):
    assert client.get("/ui/assets/missing.js").status_code == 404


def test_ui_never_serves_files_outside_dist(client, dist):
    for path in ["/ui/../secret.txt", "/ui/%2e%2e/secret.txt", "/ui/..%2Fsecret.txt"]:
        assert "secret" not in client.get(path).text


def test_ui_returns_404_without_build(client, tmp_path, monkeypatch):
    monkeypatch.setattr(frontend, "FRONTEND_DIST", tmp_path / "missing")

    assert client.get("/ui/").status_code == 404


def test_ui_needs_no_key_and_gets_the_strict_policy(client, dist):
    client.headers.pop("X-API-Key")

    response = client.get("/ui/")

    assert response.status_code == 200
    assert "script-src 'self';" in response.headers["content-security-policy"]