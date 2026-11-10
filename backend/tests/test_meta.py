from tests.conftest import V1


def test_health_checks_database(client):
    assert client.get(f"{V1}/health").json() == {"status": "ok", "database": "ok"}


def test_frontend_is_served_with_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_api_responses_are_not_cached_and_have_request_id(client):
    r = client.get(f"{V1}/health")
    assert r.headers["Cache-Control"] == "no-store"
    assert r.headers["X-Request-ID"]


def test_openapi_docs_available(client):
    assert client.get("/api/docs").status_code == 200
    paths = client.get("/api/openapi.json").json()["paths"]
    assert f"{V1}/plans" in paths and f"{V1}/auth/login" in paths
