from __future__ import annotations

from app.db import get_conn

from conftest import TestUser, make_video_file, upload_video

BODY = {"title": "第1話", "duration_ms": 60_000}


def _genre_id(client, name: str = "アニメ") -> int:
    return next(g["id"] for g in client.get("/genres").json()["items"] if g["name"] == name)


def test_create_video_is_uploading(user: TestUser) -> None:
    res = user.client.post("/videos", json=BODY)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "uploading"
    assert body["chunk_count"] == 0
    detail = user.client.get(f"/videos/{body['id']}").json()
    assert detail["mime_type"] == "video/mp4"
    assert detail["sort_order"] == 0
    assert detail["genres"] == []
    assert detail["position_ms"] is None
    assert detail["completed"] is False
    assert detail["play_count"] == 0
    assert detail["last_played_at"] is None
    assert detail["has_thumbnail"] is False


def test_create_video_validation(user: TestUser) -> None:
    bad = [
        {"duration_ms": 1000},
        {"title": "", "duration_ms": 1000},
        {"title": "   ", "duration_ms": 1000},
        {"title": "x" * 501, "duration_ms": 1000},
        {"title": "t", "duration_ms": 0},
        {"title": "t", "duration_ms": 14_400_001},
        {"title": "t"},
        {"title": "t", "duration_ms": 1000, "episode_number": 0},
        {"title": "t", "duration_ms": 1000, "sort_order": -1},
        {"title": "t", "duration_ms": 1000, "episode_title": "x" * 501},
        {"title": "t", "duration_ms": 1000, "genre_ids": [1, 1]},
    ]
    for body in bad:
        assert user.client.post("/videos", json=body).status_code == 400, body
    assert user.client.post("/videos", json={"title": "t", "duration_ms": 14_400_000}).status_code == 201


def test_create_with_series_and_genres(user: TestUser) -> None:
    series_id = user.client.post("/series", json={"title": "作品"}).json()["id"]
    genre_id = _genre_id(user.client)
    own = user.client.post("/genres", json={"name": "独自"}).json()["id"]
    res = user.client.post(
        "/videos",
        json={**BODY, "series_id": series_id, "episode_number": 1, "genre_ids": [genre_id, own]},
    )
    assert res.status_code == 201
    detail = user.client.get(f"/videos/{res.json()['id']}").json()
    assert detail["series_title"] == "作品"
    assert {g["name"] for g in detail["genres"]} == {"アニメ", "独自"}


def test_create_rejects_other_users_series_or_genre(user: TestUser, other_user: TestUser) -> None:
    series_id = other_user.client.post("/series", json={"title": "他人の作品"}).json()["id"]
    genre_id = other_user.client.post("/genres", json={"name": "他人のジャンル"}).json()["id"]
    assert user.client.post("/videos", json={**BODY, "series_id": series_id}).status_code == 404
    assert user.client.post("/videos", json={**BODY, "genre_ids": [genre_id]}).status_code == 404
    assert user.client.post("/videos", json={**BODY, "genre_ids": [99999999]}).status_code == 404
    # 何も作られていない
    assert user.client.get("/videos", params={"status": "all"}).json()["items"] == []


def test_episode_number_conflict_within_series(user: TestUser) -> None:
    series_id = user.client.post("/series", json={"title": "作品"}).json()["id"]
    body = {**BODY, "series_id": series_id, "episode_number": 1}
    assert user.client.post("/videos", json=body).status_code == 201
    res = user.client.post("/videos", json=body)
    assert res.status_code == 409
    assert res.json() == {"detail": "話数が重複しています"}
    # 別の作品なら同じ話数でよい
    other = user.client.post("/series", json={"title": "別作品"}).json()["id"]
    assert user.client.post("/videos", json={**body, "series_id": other}).status_code == 201


def test_patch_updates_only_given_fields(user: TestUser) -> None:
    genre_a, genre_b = _genre_id(user.client, "洋画"), _genre_id(user.client, "邦画")
    vid = user.client.post("/videos", json={**BODY, "description": "元", "genre_ids": [genre_a]}).json()["id"]
    res = user.client.patch(f"/videos/{vid}", json={"title": "  改題  ", "genre_ids": [genre_b]})
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "改題"
    assert body["description"] == "元"  # 指定しない項目は変わらない
    assert [g["name"] for g in body["genres"]] == ["邦画"]  # 全置換
    cleared = user.client.patch(f"/videos/{vid}", json={"description": None, "genre_ids": []}).json()
    assert cleared["description"] is None
    assert cleared["genres"] == []


def test_patch_series_and_episode(user: TestUser) -> None:
    series_id = user.client.post("/series", json={"title": "作品"}).json()["id"]
    first = user.client.post("/videos", json={**BODY, "series_id": series_id, "episode_number": 1}).json()["id"]
    second = user.client.post("/videos", json={**BODY, "series_id": series_id, "episode_number": 2}).json()["id"]
    assert user.client.patch(f"/videos/{second}", json={"episode_number": 1}).status_code == 409
    moved = user.client.patch(f"/videos/{first}", json={"series_id": None, "episode_number": None})
    assert moved.status_code == 200
    assert moved.json()["series_id"] is None
    assert user.client.patch(f"/videos/{second}", json={"episode_number": 1}).status_code == 200


def test_patch_rejects_unchangeable_or_invalid(user: TestUser) -> None:
    vid = user.client.post("/videos", json=BODY).json()["id"]
    for body in (
        {},
        {"duration_ms": 1000},
        {"mime_type": "video/webm"},
        {"title": None},
        {"title": ""},
        {"sort_order": None},
        {"genre_ids": None},
        {"episode_number": 0},
    ):
        assert user.client.patch(f"/videos/{vid}", json=body).status_code == 400, body


def test_patch_missing_or_foreign_is_404(user: TestUser, other_user: TestUser) -> None:
    vid = other_user.client.post("/videos", json=BODY).json()["id"]
    assert user.client.patch(f"/videos/{vid}", json={"title": "x"}).status_code == 404
    assert user.client.patch("/videos/99999999", json={"title": "x"}).status_code == 404
    series_id = other_user.client.post("/series", json={"title": "s"}).json()["id"]
    mine = user.client.post("/videos", json=BODY).json()["id"]
    assert user.client.patch(f"/videos/{mine}", json={"series_id": series_id}).status_code == 404


def test_foreign_video_is_404(user: TestUser, other_user: TestUser) -> None:
    vid = user.client.post("/videos", json=BODY).json()["id"]
    assert other_user.client.get(f"/videos/{vid}").status_code == 404
    assert other_user.client.delete(f"/videos/{vid}").status_code == 404
    assert other_user.client.get("/videos", params={"status": "all"}).json()["items"] == []


def test_delete_removes_everything_attached(user: TestUser) -> None:
    vid = upload_video(user.client, make_video_file(2500))
    user.client.put(f"/videos/{vid}/thumbnail", files={"data": ("t.jpg", b"jpeg-bytes", "image/jpeg")})
    user.client.post(f"/videos/{vid}/playback/start", json={})
    playlist = user.client.post("/playlists", json={"name": "P"}).json()["id"]
    user.client.put(f"/playlists/{playlist}/items", json={"items": [{"video_id": vid}]})
    assert user.client.delete(f"/videos/{vid}").status_code == 204
    assert user.client.get(f"/videos/{vid}").status_code == 404
    assert user.client.delete(f"/videos/{vid}").status_code == 404
    with get_conn() as conn, conn.cursor() as cur:
        for table in ("video_chunks", "thumbnails", "playback_states", "video_genres", "playlist_items"):
            cur.execute(f"SELECT count(*) AS n FROM movie_management.{table} WHERE video_id = %s", (vid,))
            assert cur.fetchone()["n"] == 0, table
    assert user.client.get(f"/playlists/{playlist}").json()["items"] == []
    assert user.client.get("/playback/last").json()["video"] is None


def test_uploading_video_can_be_deleted(user: TestUser) -> None:
    vid = user.client.post("/videos", json=BODY).json()["id"]
    assert user.client.delete(f"/videos/{vid}").status_code == 204


# ---- 一覧 -------------------------------------------------------------


def _titles(client, **params) -> list[str]:
    res = client.get("/videos", params=params)
    assert res.status_code == 200, res.text
    return [v["title"] for v in res.json()["items"]]


def test_list_defaults_to_ready_only(user: TestUser) -> None:
    upload_video(user.client, make_video_file(500), title="再生可能")
    user.client.post("/videos", json={**BODY, "title": "登録中"})
    assert _titles(user.client) == ["再生可能"]
    assert _titles(user.client, status="uploading") == ["登録中"]
    assert _titles(user.client, status="error") == []
    assert sorted(_titles(user.client, status="all")) == ["再生可能", "登録中"]


def test_list_filters(user: TestUser) -> None:
    series_id = user.client.post("/series", json={"title": "作品"}).json()["id"]
    genre_id = _genre_id(user.client)
    upload_video(user.client, make_video_file(500), title="Alpha Cat", series_id=series_id, genre_ids=[genre_id])
    upload_video(user.client, make_video_file(500), title="Beta", episode_title="猫の回")
    upload_video(user.client, make_video_file(500), title="Gamma")
    assert _titles(user.client, genre_id=genre_id) == ["Alpha Cat"]
    assert _titles(user.client, series_id=series_id) == ["Alpha Cat"]
    assert sorted(_titles(user.client, q="cat")) == ["Alpha Cat"]
    assert _titles(user.client, q="猫") == ["Beta"]
    assert _titles(user.client, q="%") == []


def test_list_sort_by_title_and_created(user: TestUser) -> None:
    for title in ("B", "C", "A"):
        upload_video(user.client, make_video_file(300), title=title)
    assert _titles(user.client, sort="title", order="asc") == ["A", "B", "C"]
    assert _titles(user.client, sort="title", order="desc") == ["C", "B", "A"]
    assert _titles(user.client) == ["A", "C", "B"]  # 登録日時の降順（既定）
    assert _titles(user.client, sort="created_at", order="asc") == ["B", "C", "A"]


def test_list_sort_by_last_played_puts_unplayed_last(user: TestUser) -> None:
    a = upload_video(user.client, make_video_file(300), title="A")
    b = upload_video(user.client, make_video_file(300), title="B")
    upload_video(user.client, make_video_file(300), title="C")
    user.client.post(f"/videos/{a}/playback/start", json={})
    user.client.post(f"/videos/{b}/playback/start", json={})
    assert _titles(user.client, sort="last_played_at", order="desc")[:2] == ["B", "A"]
    assert _titles(user.client, sort="last_played_at", order="desc")[-1] == "C"
    assert _titles(user.client, sort="last_played_at", order="asc")[:2] == ["A", "B"]
    assert _titles(user.client, sort="last_played_at", order="asc")[-1] == "C"


def test_list_shape_and_paging(user: TestUser) -> None:
    for i in range(3):
        upload_video(user.client, make_video_file(300), title=f"V{i}")
    body = user.client.get("/videos", params={"per_page": 2}).json()
    assert body["pagination"] == {"page": 1, "per_page": 2, "total_count": 3, "total_pages": 2}
    item = body["items"][0]
    assert set(item) == {
        "id", "title", "description", "series_id", "series_title", "episode_number", "episode_title",
        "sort_order", "duration_ms", "mime_type", "file_size_bytes", "status", "genres", "has_thumbnail",
        "position_ms", "completed", "created_at", "updated_at",
    }
    assert "data" not in item
    assert len(user.client.get("/videos", params={"page": 2, "per_page": 2}).json()["items"]) == 1


def test_list_bad_params_are_400(user: TestUser) -> None:
    for params in (
        {"status": "deleted"},
        {"sort": "size"},
        {"order": "up"},
        {"page": 0},
        {"per_page": 101},
        {"genre_id": "x"},
    ):
        assert user.client.get("/videos", params=params).status_code == 400, params
