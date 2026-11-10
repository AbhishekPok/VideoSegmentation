from tests.conftest import PLAN, V1, register


def test_register_login_logout_flow(client):
    r = client.post(f"{V1}/auth/register", json={"email": "Flow@Example.com", "password": "longenough"})
    assert r.status_code == 201
    assert r.json()["email"] == "flow@example.com"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get(f"{V1}/auth/me").status_code == 200

    assert client.post(f"{V1}/auth/logout").status_code == 204
    assert client.get(f"{V1}/auth/me").status_code == 401

    r = client.post(f"{V1}/auth/login", json={"email": "flow@example.com ", "password": "longenough"})
    assert r.status_code == 200
    assert client.get(f"{V1}/auth/me").json()["email"] == "flow@example.com"


def test_logout_revokes_the_token_server_side(client):
    register(client)
    token = client.cookies.get("lvsp_session")
    client.post(f"{V1}/auth/logout")
    client.cookies.set("lvsp_session", token)  # replaying the old cookie must not work
    assert client.get(f"{V1}/auth/me").status_code == 401


def test_register_validation(client):
    assert client.post(f"{V1}/auth/register", json={"email": "x@example.com", "password": "short"}).status_code == 422
    assert client.post(f"{V1}/auth/register", json={"email": "not-an-email", "password": "longenough"}).status_code == 422


def test_duplicate_email(client):
    register(client, "dup@example.com")
    r = client.post(f"{V1}/auth/register", json={"email": "DUP@example.com", "password": "longenough"})
    assert r.status_code == 409


def test_wrong_password_then_lockout(client):
    register(client, "lock@example.com", "longenough")
    client.post(f"{V1}/auth/logout")
    for _ in range(10):
        r = client.post(f"{V1}/auth/login", json={"email": "lock@example.com", "password": "wrongwrong"})
        assert r.status_code == 401
    r = client.post(f"{V1}/auth/login", json={"email": "lock@example.com", "password": "longenough"})
    assert r.status_code == 429


def test_unknown_email_gives_same_error(client):
    r = client.post(f"{V1}/auth/login", json={"email": "nobody@example.com", "password": "whatever1"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Wrong email or password."


def test_csrf_header_required(user):
    r = user.post(f"{V1}/plans", json=PLAN, headers={"X-Requested-With": ""})
    assert r.status_code == 403


def test_protected_routes_require_login(client):
    assert client.get(f"{V1}/plans").status_code == 401
    assert client.get(f"{V1}/youtube/videos/c3Cn4xYfxJY").status_code == 401
