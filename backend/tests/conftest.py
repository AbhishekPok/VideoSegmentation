import itertools
import os
import tempfile
from pathlib import Path

import pytest

# Point the app at a throwaway database before anything imports app.config.
# Run against PostgreSQL with: TEST_DATABASE_URL=postgresql+psycopg://... pytest
_tmp = tempfile.mkdtemp(prefix="planner-test-")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["YOUTUBE_API_KEY"] = ""
os.environ["LOG_JSON"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import email_limiter, ip_limiter  # noqa: E402
from app.main import app  # noqa: E402

V1 = "/api/v1"
FIXTURES = Path(__file__).parent
_ids = itertools.count(1)

PLAN = {
    "title": "AWS SAA",
    "video_url": "https://www.youtube.com/watch?v=c3Cn4xYfxJY",
    "duration": "2:02:29:18",
    "chapters": "",
    "minutes_per_day": 60,
    "speed": 1.5,
    "start_date": "2026-11-10",
    "snap_to_chapters": True,
    "weekdays": [0, 1, 2, 3, 4, 5, 6],
}


def new_client() -> TestClient:
    """A client that sends the CSRF header like the real frontend."""
    c = TestClient(app)
    c.headers["X-Requested-With"] = "planner"
    return c


def register(c: TestClient, email: str | None = None, password: str = "correct horse") -> str:
    email = email or f"user{next(_ids)}@example.com"
    r = c.post(f"{V1}/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return email


@pytest.fixture(scope="session")
def aws_description() -> str:
    return (FIXTURES / "aws_saa_description.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="session", autouse=True)
def _started_app():
    with TestClient(app):  # runs startup (migrations) once
        yield


@pytest.fixture(autouse=True)
def _reset_limiters():
    email_limiter.clear()
    ip_limiter.clear()


@pytest.fixture
def client() -> TestClient:
    return new_client()


@pytest.fixture
def user(client) -> TestClient:
    """A client logged in as a fresh user."""
    register(client)
    return client
