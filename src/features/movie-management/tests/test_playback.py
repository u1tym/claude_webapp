from __future__ import annotations

from app.db import get_conn

from conftest import TestUser, make_video_file, upload_video


def _video(client, title: str = "動画", **extra) -> int:
    return upload_video(client, make_video_file(2000), title=title, duration_ms=10_000, **extra)


def _start(client, video_id: int, **body):
    return client.post(f"/videos/{video_id}/playback/start", json=body)


def _save(client, video_id: int, position_ms: int, completed: bool | None = None):
    body = {"position_ms": position_ms}
    if completed is not None:
        body["completed"] = completed
    return client.put(f"/videos/{video_id}/playback/state", json=body)


def test_start_first_time(user: TestUser) -> None:
    vid = _video(user.client)
    res = _start(user.client, vid)
    assert res.status_code == 200
    body = res.json()
    assert (body["id"], body["title"], body["status"]) == (vid, "動画", "ready")
    assert (body["duration_ms"], body["mime_type"], body["chunk_count"]) == (10_000, "video/mp4", 2)
    assert (body["position_ms"], body["completed"]) == (0, False)
    assert body["start_chunk"] == {"chunk_index": 0, "start_time_ms": 0, "end_time_ms": 5000, "byte_length": 1000}
    detail = user.client.get(f"/videos/{vid}").json()
    assert detail["play_count"] == 1
    assert detail["last_played_at"] is not None


def test_start_without_body_resumes(user: TestUser) -> None:
    vid = _video(user.client)
    _save(user.client, vid, 6000)
    res = user.client.post(f"/videos/{vid}/playback/start")
    assert res.status_code == 200
    assert res.json()["position_ms"] == 6000


def test_resume_true_and_false(user: TestUser) -> None:
    vid = _video(user.client)
    _save(user.client, vid, 6000)
    resumed = _start(user.client, vid, resume=True).json()
    assert resumed["position_ms"] == 6000
    assert resumed["start_chunk"]["chunk_index"] == 1  # 5000ms 以降のチャンク
    assert _start(user.client, vid, resume=False).json()["position_ms"] == 0
    assert user.client.get(f"/videos/{vid}").json()["play_count"] == 2


def test_resume_beyond_duration_starts_from_top(user: TestUser) -> None:
    vid = _video(user.client)
    _save(user.client, vid, 6000)
    with get_conn() as conn, conn.cursor() as cur:  # 差し替えなどで動画が短くなった状況
        cur.execute("UPDATE movie_management.videos SET duration_ms = 3000 WHERE id = %s", (vid,))
    assert _start(user.client, vid).json()["position_ms"] == 0


def test_start_requires_ready_own_video(user: TestUser, other_user: TestUser) -> None:
    uploading = user.client.post("/videos", json={"title": "登録中", "duration_ms": 1000}).json()["id"]
    res = _start(user.client, uploading)
    assert res.status_code == 422
    assert res.json() == {"detail": "再生できない動画です"}
    vid = _video(user.client)
    assert _start(other_user.client, vid).status_code == 404
    assert _start(user.client, 99999999).status_code == 404


def test_save_state_upserts_and_keeps_play_count(user: TestUser) -> None:
    vid = _video(user.client)
    res = _save(user.client, vid, 1234)
    assert res.status_code == 200
    body = res.json()
    assert (body["video_id"], body["position_ms"], body["completed"]) == (vid, 1234, False)
    assert body["last_played_at"]
    detail = user.client.get(f"/videos/{vid}").json()
    assert (detail["position_ms"], detail["completed"], detail["play_count"]) == (1234, False, 0)
    _start(user.client, vid)
    _save(user.client, vid, 9000, True)
    detail = user.client.get(f"/videos/{vid}").json()
    assert (detail["position_ms"], detail["completed"], detail["play_count"]) == (9000, True, 1)


def test_save_state_range(user: TestUser) -> None:
    vid = _video(user.client)
    assert _save(user.client, vid, 10_000).status_code == 200  # 動画の長さ以下
    assert _save(user.client, vid, 10_001).status_code == 400
    assert _save(user.client, vid, -1).status_code == 400
    assert user.client.put(f"/videos/{vid}/playback/state", json={}).status_code == 400
    assert user.client.put(f"/videos/{vid}/playback/state", json={"position_ms": "x"}).status_code == 400


def test_save_state_is_private(user: TestUser, other_user: TestUser) -> None:
    vid = _video(user.client)
    assert _save(other_user.client, vid, 100).status_code == 404
    _save(user.client, vid, 500)
    assert other_user.client.get("/playback/history").json()["items"] == []


# ---- 次の動画 ---------------------------------------------------------


def _next(client, video_id: int) -> dict:
    res = client.get(f"/videos/{video_id}/next")
    assert res.status_code == 200
    return res.json()


def test_next_in_series_follows_sort_order(user: TestUser) -> None:
    series_id = user.client.post("/series", json={"title": "作品"}).json()["id"]
    third = _video(user.client, "第3話", series_id=series_id, sort_order=30, episode_number=3)
    first = _video(user.client, "第1話", series_id=series_id, sort_order=10, episode_number=1)
    second = _video(user.client, "第2話", series_id=series_id, sort_order=20, episode_number=2)
    assert _next(user.client, first)["video"]["id"] == second
    assert _next(user.client, second)["video"]["id"] == third
    assert _next(user.client, third) == {"has_next": False, "video": None}
    body = _next(user.client, first)
    assert body["has_next"] is True
    assert set(body["video"]) == {"id", "title", "episode_number", "sort_order", "duration_ms", "status"}


def test_next_in_series_uses_episode_number_when_sort_order_ties(user: TestUser) -> None:
    series_id = user.client.post("/series", json={"title": "作品"}).json()["id"]
    b = _video(user.client, "B", series_id=series_id, episode_number=2)
    a = _video(user.client, "A", series_id=series_id, episode_number=1)
    assert _next(user.client, a)["video"]["id"] == b


def test_next_in_series_skips_videos_not_ready_and_other_series(user: TestUser) -> None:
    s1 = user.client.post("/series", json={"title": "S1"}).json()["id"]
    s2 = user.client.post("/series", json={"title": "S2"}).json()["id"]
    first = _video(user.client, "1", series_id=s1, sort_order=1)
    user.client.post("/videos", json={"title": "登録中", "duration_ms": 1000, "series_id": s1, "sort_order": 2})
    _video(user.client, "別作品", series_id=s2, sort_order=3)
    last = _video(user.client, "4", series_id=s1, sort_order=4)
    assert _next(user.client, first)["video"]["id"] == last


def test_next_standalone_follows_created_order(user: TestUser) -> None:
    a = _video(user.client, "A")
    series_id = user.client.post("/series", json={"title": "作品"}).json()["id"]
    _video(user.client, "作品内", series_id=series_id)
    b = _video(user.client, "B")
    c = _video(user.client, "C")
    assert _next(user.client, a)["video"]["id"] == b  # 作品に属する動画は対象外
    assert _next(user.client, b)["video"]["id"] == c
    assert _next(user.client, c)["has_next"] is False


def test_next_is_private(user: TestUser, other_user: TestUser) -> None:
    a = _video(user.client, "A")
    _video(other_user.client, "他人の動画")
    assert _next(user.client, a)["has_next"] is False
    assert other_user.client.get(f"/videos/{a}/next").status_code == 404


# ---- 履歴・続きから視聴 -----------------------------------------------


def test_history_is_ordered_by_last_played_desc(user: TestUser) -> None:
    a, b, c = _video(user.client, "A"), _video(user.client, "B"), _video(user.client, "C")
    _save(user.client, a, 1000)
    _save(user.client, b, 2000, True)
    _start(user.client, c)
    _save(user.client, a, 3000)  # A が最新になる
    body = user.client.get("/playback/history").json()
    assert [i["title"] for i in body["items"]] == ["A", "C", "B"]
    first = body["items"][0]
    assert set(first) == {"video_id", "title", "position_ms", "completed", "duration_ms", "last_played_at"}
    assert (first["position_ms"], first["completed"], first["duration_ms"]) == (3000, False, 10_000)
    assert body["items"][2]["completed"] is True
    assert body["pagination"] == {"page": 1, "per_page": 20, "total_count": 3, "total_pages": 1}


def test_history_paging_and_deleted_videos(user: TestUser) -> None:
    ids = [_video(user.client, f"V{i}") for i in range(3)]
    for vid in ids:
        _save(user.client, vid, 100)
    page = user.client.get("/playback/history", params={"per_page": 2, "page": 2}).json()
    assert len(page["items"]) == 1
    user.client.delete(f"/videos/{ids[0]}")
    assert user.client.get("/playback/history").json()["pagination"]["total_count"] == 2
    assert user.client.get("/playback/history", params={"per_page": 101}).status_code == 400


def test_last_playback_is_empty_at_first(user: TestUser) -> None:
    assert user.client.get("/playback/last").json() == {"video": None, "playlist": None}


def test_last_playback_tracks_single_video(user: TestUser) -> None:
    a, b = _video(user.client, "A"), _video(user.client, "B")
    _start(user.client, a)
    _save(user.client, a, 4000)
    _start(user.client, b)
    body = user.client.get("/playback/last").json()
    assert body["playlist"] is None
    assert body["video"]["video_id"] == b
    assert (body["video"]["title"], body["video"]["duration_ms"], body["video"]["position_ms"]) == ("B", 10_000, 0)
    _save(user.client, b, 7000)
    assert user.client.get("/playback/last").json()["video"]["position_ms"] == 7000


def test_last_playback_hides_deleted_or_unplayable(user: TestUser) -> None:
    vid = _video(user.client)
    _start(user.client, vid)
    user.client.post(f"/videos/{vid}/replace", json={"duration_ms": 1000})  # 登録中に戻る
    assert user.client.get("/playback/last").json()["video"] is None
    vid2 = _video(user.client, "B")
    _start(user.client, vid2)
    assert user.client.get("/playback/last").json()["video"]["video_id"] == vid2
    user.client.delete(f"/videos/{vid2}")
    assert user.client.get("/playback/last").json()["video"] is None


def test_last_playback_is_per_user(user: TestUser, other_user: TestUser) -> None:
    _start(user.client, _video(user.client))
    assert other_user.client.get("/playback/last").json() == {"video": None, "playlist": None}


def test_resume_from_the_very_end_starts_from_top(user: TestUser) -> None:
    """最後まで視聴した動画（末尾の位置が保存される）は、続きからでも先頭から再生する。"""
    vid = _video(user.client)
    _save(user.client, vid, 10_000, True)
    assert _start(user.client, vid, resume=True).json()["position_ms"] == 0
    _save(user.client, vid, 9_999)
    assert _start(user.client, vid, resume=True).json()["position_ms"] == 9_999  # 末尾の手前は、その位置から
