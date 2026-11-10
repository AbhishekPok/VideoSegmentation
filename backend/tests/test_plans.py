from tests.conftest import PLAN, V1, new_client, register


def test_create_and_read_plan(user):
    r = user.post(f"{V1}/plans", json=PLAN)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["plan"]["duration"] == "50:29:18"
    assert d["plan"]["video_id"] == "c3Cn4xYfxJY"
    assert d["plan"]["speed"] == 1.5
    assert len(d["schedule"]["sessions"]) == 34
    assert d["schedule"]["sessions"][0]["date"] == "2026-11-10"
    assert d["done"] == []

    pid = d["plan"]["id"]
    assert user.get(f"{V1}/plans/{pid}").json()["plan"]["title"] == "AWS SAA"
    lst = user.get(f"{V1}/plans").json()
    assert lst[0]["sessions_total"] == 34


def test_update_plan_and_validation(user):
    pid = user.post(f"{V1}/plans", json=PLAN).json()["plan"]["id"]
    r = user.put(f"{V1}/plans/{pid}", json={**PLAN, "speed": 1.0, "weekdays": [3, 1, 1]})
    assert r.status_code == 200
    assert len(r.json()["schedule"]["sessions"]) == 51
    assert r.json()["plan"]["weekdays"] == [1, 3]

    bad_inputs = [
        {"duration": "abc"},
        {"speed": 3},
        {"weekdays": []},
        {"weekdays": [7]},
        {"minutes_per_day": 5},
        {"duration": "11:00:00:00"},
    ]
    for bad in bad_inputs:
        assert user.put(f"{V1}/plans/{pid}", json={**PLAN, **bad}).status_code == 422, bad


def test_validation_message_is_readable(user):
    r = user.post(f"{V1}/plans", json={**PLAN, "duration": "abc"})
    assert "Enter the total length" in r.json()["detail"][0]["msg"]


def test_progress_ticks(user):
    pid = user.post(f"{V1}/plans", json=PLAN).json()["plan"]["id"]
    tick = lambda i, done: user.put(f"{V1}/plans/{pid}/progress/{i}", json={"done": done})  # noqa: E731
    assert tick(0, True).json() == [0]
    assert tick(3, True).json() == [0, 3]
    assert tick(3, True).json() == [0, 3]  # idempotent
    assert tick(0, False).json() == [3]
    assert user.get(f"{V1}/plans/{pid}").json()["done"] == [3]
    assert tick(999, True).status_code == 400
    assert user.delete(f"{V1}/plans/{pid}/progress").status_code == 204
    assert user.get(f"{V1}/plans/{pid}").json()["done"] == []


def test_users_cannot_touch_each_others_plans(user):
    pid = user.post(f"{V1}/plans", json=PLAN).json()["plan"]["id"]
    other = new_client()
    register(other)
    assert other.get(f"{V1}/plans/{pid}").status_code == 404
    assert other.put(f"{V1}/plans/{pid}", json=PLAN).status_code == 404
    assert other.delete(f"{V1}/plans/{pid}").status_code == 404
    assert other.put(f"{V1}/plans/{pid}/progress/0", json={"done": True}).status_code == 404
    assert other.delete(f"{V1}/plans/{pid}/progress").status_code == 404
    assert other.get(f"{V1}/plans").json() == []
    assert user.get(f"{V1}/plans/{pid}").status_code == 200  # untouched


def test_delete_plan_removes_progress(user):
    pid = user.post(f"{V1}/plans", json=PLAN).json()["plan"]["id"]
    user.put(f"{V1}/plans/{pid}/progress/0", json={"done": True})
    assert user.delete(f"{V1}/plans/{pid}").status_code == 204
    assert user.get(f"{V1}/plans/{pid}").status_code == 404


def test_shrinking_a_plan_hides_out_of_range_ticks(user):
    pid = user.post(f"{V1}/plans", json=PLAN).json()["plan"]["id"]
    user.put(f"{V1}/plans/{pid}/progress/30", json={"done": True})
    d = user.put(f"{V1}/plans/{pid}", json={**PLAN, "minutes_per_day": 480}).json()
    assert len(d["schedule"]["sessions"]) < 30
    assert d["done"] == []
