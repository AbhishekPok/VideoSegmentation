from app.config import settings
from app.services import youtube_service
from tests.conftest import V1


class FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_not_configured(user):
    assert user.get(f"{V1}/config").json() == {"youtube_api": False}
    r = user.get(f"{V1}/youtube/videos/c3Cn4xYfxJY")
    assert r.status_code == 404 and r.json()["detail"] == "not_configured"


def test_lookup_with_key_and_cache(user, monkeypatch, aws_description):
    monkeypatch.setattr(settings, "youtube_api_key", "dummy")
    youtube_service.clear_cache()
    calls = []
    payload = {"items": [{"contentDetails": {"duration": "P2DT2H29M18S"}, "snippet": {"description": aws_description}}]}
    monkeypatch.setattr(youtube_service.httpx, "get", lambda *a, **k: calls.append(k) or FakeResp(200, payload))

    assert user.get(f"{V1}/config").json() == {"youtube_api": True}
    r = user.get(f"{V1}/youtube/videos/c3Cn4xYfxJY")
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["duration"] == "50:29:18"
    assert m["chapter_count"] == 82
    assert user.get(f"{V1}/youtube/videos/c3Cn4xYfxJY").status_code == 200
    assert len(calls) == 1  # second call served from cache
    assert user.get(f"{V1}/youtube/videos/bad").status_code == 422


def test_missing_video_and_api_errors(user, monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "dummy")
    youtube_service.clear_cache()
    monkeypatch.setattr(youtube_service.httpx, "get", lambda *a, **k: FakeResp(200, {"items": []}))
    r = user.get(f"{V1}/youtube/videos/AAAAAAAAAAA")
    assert r.status_code == 404 and "not found" in r.json()["detail"]

    monkeypatch.setattr(
        youtube_service.httpx, "get", lambda *a, **k: FakeResp(400, {"error": {"message": "API key not valid"}})
    )
    r = user.get(f"{V1}/youtube/videos/BBBBBBBBBBB")
    assert r.status_code == 502 and "API key not valid" in r.json()["detail"]
