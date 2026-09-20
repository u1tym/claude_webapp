from __future__ import annotations

from conftest import TestUser, make_video_file, upload_video


def _video(client, title: str = "動画") -> int:
    return upload_video(client, make_video_file(2000), title=title, duration_ms=10_000)


def _playlist(client, name: str = "P", videos: list[int] | None = None) -> int:
    playlist_id = client.post("/playlists", json={"name": name}).json()["id"]
    if videos is not None:
        res = client.put(f"/playlists/{playlist_id}/items", json={"items": [{"video_id": v} for v in videos]})
        assert res.status_code == 200, res.text
    return playlist_id


def _titles(detail: dict) -> list[str]:
    return [i["title"] for i in detail["items"]]


def test_create_and_get(user: TestUser) -> None:
    res = user.client.post("/playlists", json={"name": "  お気に入り  ", "description": "説明"})
    assert res.status_code == 201
    body = res.json()
    assert (body["name"], body["description"], body["items"]) == ("お気に入り", "説明", [])
    assert user.client.get(f"/playlists/{body['id']}").json() == body


def test_create_validation(user: TestUser) -> None:
    for body in ({}, {"name": ""}, {"name": "   "}, {"name": "x" * 501}):
        assert user.client.post("/playlists", json=body).status_code == 400, body


def test_list_is_ordered_by_updated_desc_with_counts(user: TestUser) -> None:
    a, b = _video(user.client, "A"), _video(user.client, "B")
    first = _playlist(user.client, "古い", [a, b])
    second = _playlist(user.client, "新しい", [a])
    body = user.client.get("/playlists").json()
    assert [(p["name"], p["item_count"]) for p in body["items"]] == [("新しい", 1), ("古い", 2)]
    # 項目を更新すると先頭に来る
    user.client.put(f"/playlists/{first}/items", json={"items": [{"video_id": b}]})
    assert [p["name"] for p in user.client.get("/playlists").json()["items"]] == ["古い", "新しい"]
    assert body["pagination"]["total_count"] == 2
    assert second != first


def test_patch_name_and_description(user: TestUser) -> None:
    playlist_id = _playlist(user.client, "元")
    res = user.client.patch(f"/playlists/{playlist_id}", json={"name": "改名"})
    assert res.status_code == 200
    assert res.json()["name"] == "改名"
    assert user.client.patch(f"/playlists/{playlist_id}", json={"description": "説明"}).json()["description"] == "説明"
    assert user.client.patch(f"/playlists/{playlist_id}", json={"description": None}).json()["description"] is None
    for body in ({}, {"name": None}, {"name": ""}, {"unknown": 1}):
        assert user.client.patch(f"/playlists/{playlist_id}", json=body).status_code == 400, body


def test_replace_items_order_and_duplicates(user: TestUser) -> None:
    a, b = _video(user.client, "A"), _video(user.client, "B")
    playlist_id = _playlist(user.client, "P", [b, a, b])  # 同じ動画を複数回含められる
    detail = user.client.get(f"/playlists/{playlist_id}").json()
    assert _titles(detail) == ["B", "A", "B"]
    assert [i["sort_order"] for i in detail["items"]] == [0, 1, 2]
    first = detail["items"][0]
    assert set(first) == {"item_id", "video_id", "title", "duration_ms", "status", "has_thumbnail", "sort_order"}
    user.client.put(f"/videos/{a}/thumbnail", files={"data": ("t", b"jpeg", "image/jpeg")})
    assert [i["has_thumbnail"] for i in user.client.get(f"/playlists/{playlist_id}").json()["items"]] == [False, True, False]
    empty = user.client.put(f"/playlists/{playlist_id}/items", json={"items": []})
    assert empty.status_code == 200
    assert empty.json()["items"] == []


def test_replace_items_rejects_other_users_video_and_keeps_old_order(user: TestUser, other_user: TestUser) -> None:
    mine = _video(user.client, "自分")
    theirs = _video(other_user.client, "他人")
    playlist_id = _playlist(user.client, "P", [mine])
    res = user.client.put(f"/playlists/{playlist_id}/items", json={"items": [{"video_id": mine}, {"video_id": theirs}]})
    assert res.status_code == 404
    assert _titles(user.client.get(f"/playlists/{playlist_id}").json()) == ["自分"]  # 元の並びが残る
    assert user.client.put(f"/playlists/{playlist_id}/items", json={"items": [{"video_id": 99999999}]}).status_code == 404
    for body in ({}, {"items": [{}]}, {"items": [{"video_id": "x"}]}):
        assert user.client.put(f"/playlists/{playlist_id}/items", json=body).status_code == 400, body


def test_delete_playlist_keeps_videos(user: TestUser) -> None:
    vid = _video(user.client)
    playlist_id = _playlist(user.client, "P", [vid])
    assert user.client.delete(f"/playlists/{playlist_id}").status_code == 204
    assert user.client.get(f"/playlists/{playlist_id}").status_code == 404
    assert user.client.get(f"/videos/{vid}").status_code == 200
    assert user.client.delete(f"/playlists/{playlist_id}").status_code == 404


def test_other_users_playlist_is_404(user: TestUser, other_user: TestUser) -> None:
    playlist_id = _playlist(user.client, "P")
    assert other_user.client.get(f"/playlists/{playlist_id}").status_code == 404
    assert other_user.client.patch(f"/playlists/{playlist_id}", json={"name": "x"}).status_code == 404
    assert other_user.client.delete(f"/playlists/{playlist_id}").status_code == 404
    assert other_user.client.put(f"/playlists/{playlist_id}/items", json={"items": []}).status_code == 404
    assert other_user.client.post(f"/playlists/{playlist_id}/playback/start", json={}).status_code == 404
    assert other_user.client.get("/playlists").json()["items"] == []


# ---- 再生 -------------------------------------------------------------


def _start(client, playlist_id: int, **body):
    return client.post(f"/playlists/{playlist_id}/playback/start", json=body)


def test_start_from_first_item(user: TestUser) -> None:
    a, b = _video(user.client, "A"), _video(user.client, "B")
    playlist_id = _playlist(user.client, "P", [a, b])
    res = _start(user.client, playlist_id)
    assert res.status_code == 200
    body = res.json()
    assert (body["title"], body["video_id"], body["position_ms"], body["sort_order"]) == ("A", a, 0, 0)
    assert (body["has_next"], body["has_prev"], body["status"]) == (True, False, "ready")
    assert body["playlist_id"] == playlist_id
    assert body["start_chunk"]["chunk_index"] == 0
    assert user.client.get(f"/videos/{a}").json()["play_count"] == 1


def test_empty_playlist_cannot_start(user: TestUser) -> None:
    playlist_id = _playlist(user.client, "空")
    res = _start(user.client, playlist_id)
    assert res.status_code == 422
    assert res.json() == {"detail": "プレイリストに動画がありません"}


def test_next_and_prev_move_by_sort_order(user: TestUser) -> None:
    a, b, c = (_video(user.client, t) for t in "ABC")
    playlist_id = _playlist(user.client, "P", [a, b, c])
    item_a = _start(user.client, playlist_id).json()["item_id"]
    nxt = user.client.get(f"/playlists/{playlist_id}/items/{item_a}/next").json()
    assert nxt["has_next"] is True
    assert (nxt["item"]["title"], nxt["item"]["position_ms"], nxt["item"]["has_prev"]) == ("B", 0, True)
    item_b = nxt["item"]["item_id"]
    last = user.client.get(f"/playlists/{playlist_id}/items/{item_b}/next").json()["item"]
    assert (last["title"], last["has_next"]) == ("C", False)
    end = user.client.get(f"/playlists/{playlist_id}/items/{last['item_id']}/next").json()
    assert end == {"has_next": False, "item": None}
    prev = user.client.get(f"/playlists/{playlist_id}/items/{item_b}/prev").json()
    assert (prev["has_prev"], prev["item"]["title"], prev["item"]["has_prev"]) == (True, "A", False)
    assert user.client.get(f"/playlists/{playlist_id}/items/{item_a}/prev").json() == {"has_prev": False, "item": None}


def test_next_item_must_belong_to_playlist(user: TestUser) -> None:
    a = _video(user.client, "A")
    p1, p2 = _playlist(user.client, "P1", [a]), _playlist(user.client, "P2", [a])
    item_of_p1 = _start(user.client, p1).json()["item_id"]
    assert user.client.get(f"/playlists/{p2}/items/{item_of_p1}/next").status_code == 404
    assert user.client.get(f"/playlists/{p1}/items/99999999/prev").status_code == 404


def test_state_saves_video_state_and_playlist_context_only(user: TestUser) -> None:
    single, a = _video(user.client, "単独"), _video(user.client, "A")
    user.client.post(f"/videos/{single}/playback/start", json={})
    playlist_id = _playlist(user.client, "P", [a])
    item = _start(user.client, playlist_id).json()["item_id"]
    res = user.client.put(
        f"/playlists/{playlist_id}/items/{item}/playback/state", json={"position_ms": 6000, "completed": False}
    )
    assert res.status_code == 204
    detail = user.client.get(f"/videos/{a}").json()
    assert (detail["position_ms"], detail["completed"]) == (6000, False)
    last = user.client.get("/playback/last").json()
    assert last["playlist"]["playlist_id"] == playlist_id
    assert (last["playlist"]["item_id"], last["playlist"]["position_ms"], last["playlist"]["playlist_name"]) == (
        item, 6000, "P",
    )
    assert (last["playlist"]["video_id"], last["playlist"]["video_title"]) == (a, "A")
    # 単独再生の続きから視聴は変わらない
    assert last["video"]["video_id"] == single


def test_state_validation(user: TestUser) -> None:
    a = _video(user.client)
    playlist_id = _playlist(user.client, "P", [a])
    item = _start(user.client, playlist_id).json()["item_id"]
    url = f"/playlists/{playlist_id}/items/{item}/playback/state"
    assert user.client.put(url, json={"position_ms": 10_001}).status_code == 400
    assert user.client.put(url, json={"position_ms": -1}).status_code == 400
    assert user.client.put(url, json={}).status_code == 400
    assert user.client.put(f"/playlists/{playlist_id}/items/99999999/playback/state", json={"position_ms": 1}).status_code == 404


def test_resume_continues_last_item_and_position(user: TestUser) -> None:
    a, b = _video(user.client, "A"), _video(user.client, "B")
    playlist_id = _playlist(user.client, "P", [a, b])
    first = _start(user.client, playlist_id).json()
    item_b = user.client.get(f"/playlists/{playlist_id}/items/{first['item_id']}/next").json()["item"]["item_id"]
    user.client.put(f"/playlists/{playlist_id}/items/{item_b}/playback/state", json={"position_ms": 7000})
    resumed = _start(user.client, playlist_id, resume=True).json()
    assert (resumed["title"], resumed["position_ms"], resumed["has_prev"]) == ("B", 7000, True)
    restarted = _start(user.client, playlist_id, resume=False).json()
    assert (restarted["title"], restarted["position_ms"]) == ("A", 0)


def test_resume_of_another_playlist_starts_from_top(user: TestUser) -> None:
    a, b = _video(user.client, "A"), _video(user.client, "B")
    p1, p2 = _playlist(user.client, "P1", [a]), _playlist(user.client, "P2", [b, a])
    item = _start(user.client, p1).json()["item_id"]
    user.client.put(f"/playlists/{p1}/items/{item}/playback/state", json={"position_ms": 3000})
    assert _start(user.client, p2).json()["title"] == "B"


def test_resume_after_items_replaced_starts_from_top(user: TestUser) -> None:
    a, b = _video(user.client, "A"), _video(user.client, "B")
    playlist_id = _playlist(user.client, "P", [a, b])
    item = _start(user.client, playlist_id).json()["item_id"]
    user.client.put(f"/playlists/{playlist_id}/items/{item}/playback/state", json={"position_ms": 3000})
    user.client.put(f"/playlists/{playlist_id}/items", json={"items": [{"video_id": b}, {"video_id": a}]})
    assert user.client.get("/playback/last").json()["playlist"] is None  # 項目が作り直されたため
    restarted = _start(user.client, playlist_id).json()
    assert (restarted["title"], restarted["position_ms"]) == ("B", 0)


def test_unplayable_item_is_returned_with_status(user: TestUser) -> None:
    a = _video(user.client, "A")
    uploading = user.client.post("/videos", json={"title": "登録中", "duration_ms": 1000}).json()["id"]
    playlist_id = _playlist(user.client, "P", [uploading, a])
    first = _start(user.client, playlist_id)
    assert first.status_code == 200
    body = first.json()
    assert (body["status"], body["start_chunk"], body["position_ms"], body["has_next"]) == ("uploading", None, 0, True)
    nxt = user.client.get(f"/playlists/{playlist_id}/items/{body['item_id']}/next").json()["item"]
    assert (nxt["title"], nxt["status"]) == ("A", "ready")
    back = user.client.get(f"/playlists/{playlist_id}/items/{nxt['item_id']}/prev").json()["item"]
    assert back["status"] == "uploading"
    assert user.client.get(f"/videos/{uploading}").json()["play_count"] == 0


def test_last_playlist_hides_unplayable_item(user: TestUser) -> None:
    a = _video(user.client, "A")
    playlist_id = _playlist(user.client, "P", [a])
    item = _start(user.client, playlist_id).json()["item_id"]
    assert user.client.get("/playback/last").json()["playlist"]["item_id"] == item
    user.client.post(f"/videos/{a}/replace", json={"duration_ms": 1000})
    assert user.client.get("/playback/last").json()["playlist"] is None
    user.client.delete(f"/playlists/{playlist_id}")
    assert user.client.get("/playback/last").json()["playlist"] is None


def test_playlist_resume_from_the_very_end_starts_item_from_top(user: TestUser) -> None:
    a = _video(user.client, "A")
    playlist_id = _playlist(user.client, "P", [a])
    item = _start(user.client, playlist_id).json()["item_id"]
    user.client.put(f"/playlists/{playlist_id}/items/{item}/playback/state", json={"position_ms": 10_000, "completed": True})
    resumed = _start(user.client, playlist_id, resume=True).json()
    assert (resumed["item_id"], resumed["position_ms"]) == (item, 0)
