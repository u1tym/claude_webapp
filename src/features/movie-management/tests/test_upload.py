from __future__ import annotations

from app.db import get_conn
from app.services.upload_service import MAX_CHUNK_BYTES

from conftest import TestUser, make_video_file, upload_video

BODY = {"title": "動画", "duration_ms": 10_000}


def _chunk(client, video_id: int, index: int, data: bytes, start: int = 0, end: int = 1000):
    return client.post(
        f"/videos/{video_id}/chunks",
        data={"chunk_index": index, "start_time_ms": start, "end_time_ms": end},
        files={"data": ("c", data, "application/octet-stream")},
    )


def _new(client) -> int:
    return client.post("/videos", json=BODY).json()["id"]


def test_three_step_upload_makes_video_ready(user: TestUser) -> None:
    video_id = _new(user.client)
    first = _chunk(user.client, video_id, 0, b"a" * 100)
    assert first.status_code == 201
    assert first.json() == {"video_id": video_id, "chunk_index": 0, "byte_length": 100, "uploaded_chunks": 1}
    assert _chunk(user.client, video_id, 1, b"b" * 50, 1000, 2000).json()["uploaded_chunks"] == 2
    detail = user.client.get(f"/videos/{video_id}").json()
    assert (detail["status"], detail["chunk_count"], detail["file_size_bytes"]) == ("uploading", 2, 150)
    done = user.client.post(f"/videos/{video_id}/complete", json={"duration_ms": 9_000, "chunk_count": 2})
    assert done.status_code == 200
    assert done.json() == {
        "id": video_id, "status": "ready", "duration_ms": 9_000, "chunk_count": 2, "file_size_bytes": 150,
    }
    assert user.client.get(f"/videos/{video_id}").json()["duration_ms"] == 9_000


def test_duplicate_chunk_is_409(user: TestUser) -> None:
    video_id = _new(user.client)
    assert _chunk(user.client, video_id, 0, b"x").status_code == 201
    res = _chunk(user.client, video_id, 0, b"y")
    assert res.status_code == 409
    assert res.json() == {"detail": "同じチャンクが登録済みです"}
    # 重複した分は加算されない
    assert user.client.get(f"/videos/{video_id}").json()["chunk_count"] == 1


def test_chunk_validation(user: TestUser) -> None:
    video_id = _new(user.client)
    assert _chunk(user.client, video_id, 0, b"").status_code == 400
    assert _chunk(user.client, video_id, 0, b"x" * (MAX_CHUNK_BYTES + 1)).status_code == 400
    assert _chunk(user.client, video_id, -1, b"x").status_code == 400
    assert _chunk(user.client, video_id, 0, b"x", start=-1, end=10).status_code == 400
    assert _chunk(user.client, video_id, 0, b"x", start=10, end=10).status_code == 400
    missing = user.client.post(f"/videos/{video_id}/chunks", data={"chunk_index": 0})
    assert missing.status_code == 400
    assert _chunk(user.client, video_id, 0, b"x" * MAX_CHUNK_BYTES).status_code == 201


def test_chunk_needs_own_uploading_video(user: TestUser, other_user: TestUser) -> None:
    video_id = _new(user.client)
    assert _chunk(other_user.client, video_id, 0, b"x").status_code == 404
    assert _chunk(user.client, 99999999, 0, b"x").status_code == 404
    ready = upload_video(user.client, make_video_file(300))
    res = _chunk(user.client, ready, 5, b"x")
    assert res.status_code == 422
    assert res.json() == {"detail": "登録中の動画ではありません"}


def test_complete_requires_matching_chunk_count(user: TestUser) -> None:
    video_id = _new(user.client)
    empty = user.client.post(f"/videos/{video_id}/complete", json={"duration_ms": 1000, "chunk_count": 1})
    assert empty.status_code == 422
    assert empty.json() == {"detail": "チャンク数が一致しません"}
    _chunk(user.client, video_id, 0, b"x")
    _chunk(user.client, video_id, 1, b"y", 1000, 2000)
    assert user.client.post(f"/videos/{video_id}/complete", json={"duration_ms": 1000, "chunk_count": 3}).status_code == 422
    assert user.client.get(f"/videos/{video_id}").json()["status"] == "uploading"


def test_complete_rejects_gap_in_chunk_numbers(user: TestUser) -> None:
    video_id = _new(user.client)
    _chunk(user.client, video_id, 0, b"x")
    _chunk(user.client, video_id, 2, b"y", 1000, 2000)  # 1 番が抜けている
    res = user.client.post(f"/videos/{video_id}/complete", json={"duration_ms": 1000, "chunk_count": 2})
    assert res.status_code == 422


def test_complete_validation_and_state(user: TestUser, other_user: TestUser) -> None:
    video_id = _new(user.client)
    _chunk(user.client, video_id, 0, b"x")
    for body in ({}, {"duration_ms": 0, "chunk_count": 1}, {"duration_ms": 14_400_001, "chunk_count": 1},
                 {"duration_ms": 1000, "chunk_count": 0}):
        assert user.client.post(f"/videos/{video_id}/complete", json=body).status_code == 400, body
    assert other_user.client.post(f"/videos/{video_id}/complete", json={"duration_ms": 1000, "chunk_count": 1}).status_code == 404
    assert user.client.post(f"/videos/{video_id}/complete", json={"duration_ms": 1000, "chunk_count": 1}).status_code == 200
    again = user.client.post(f"/videos/{video_id}/complete", json={"duration_ms": 1000, "chunk_count": 1})
    assert again.status_code == 422


def test_replace_resets_file_state_but_keeps_info(user: TestUser) -> None:
    video_id = upload_video(user.client, make_video_file(2500), title="元の動画", description="説明")
    user.client.put(f"/videos/{video_id}/thumbnail", files={"data": ("t.jpg", b"jpeg", "image/jpeg")})
    user.client.post(f"/videos/{video_id}/playback/start", json={})
    user.client.put(f"/videos/{video_id}/playback/state", json={"position_ms": 5000, "completed": True})

    res = user.client.post(f"/videos/{video_id}/replace", json={"duration_ms": 20_000, "mime_type": "video/webm"})
    assert res.status_code == 200
    assert res.json() == {"id": video_id, "status": "uploading", "chunk_count": 0}

    detail = user.client.get(f"/videos/{video_id}").json()
    assert (detail["status"], detail["chunk_count"], detail["file_size_bytes"]) == ("uploading", 0, 0)
    assert (detail["duration_ms"], detail["mime_type"]) == (20_000, "video/webm")
    assert (detail["position_ms"], detail["completed"]) == (0, False)
    assert (detail["title"], detail["description"], detail["has_thumbnail"]) == ("元の動画", "説明", True)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM movie_management.video_chunks WHERE video_id = %s", (video_id,))
        assert cur.fetchone()["n"] == 0
    assert user.client.get(f"/videos/{video_id}/stream").status_code == 422  # 再生できない

    # 新しいファイルを送って完了すると再生できる
    assert _chunk(user.client, video_id, 0, b"new-file").status_code == 201
    done = user.client.post(f"/videos/{video_id}/complete", json={"duration_ms": 20_000, "chunk_count": 1})
    assert done.status_code == 200
    assert user.client.get(f"/videos/{video_id}/stream").content == b"new-file"


def test_replace_validation(user: TestUser, other_user: TestUser) -> None:
    video_id = upload_video(user.client, make_video_file(300))
    assert user.client.post(f"/videos/{video_id}/replace", json={}).status_code == 400
    assert user.client.post(f"/videos/{video_id}/replace", json={"duration_ms": 0}).status_code == 400
    assert other_user.client.post(f"/videos/{video_id}/replace", json={"duration_ms": 1000}).status_code == 404
