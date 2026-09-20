from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

from conftest import TestUser, make_video_file, upload_video

SIZE = 3500  # 1000 バイトのチャンク 4 つ（最後は 500 バイト）
DATA = make_video_file(SIZE)


@pytest.fixture()
def video_id(user: TestUser) -> int:
    return upload_video(user.client, DATA, chunk_size=1000, mime_type="video/mp4")


def _get(user: TestUser, video_id: int, range_header: str | None = None):
    headers = {"Range": range_header} if range_header else {}
    return user.client.get(f"/videos/{video_id}/stream", headers=headers)


def test_full_body_without_range(user: TestUser, video_id: int) -> None:
    res = _get(user, video_id)
    assert res.status_code == 200
    assert res.content == DATA
    assert res.headers["accept-ranges"] == "bytes"
    assert res.headers["content-length"] == str(SIZE)
    assert res.headers["content-type"] == "video/mp4"
    assert res.headers["cache-control"] == "private"
    assert "content-range" not in res.headers


@pytest.mark.parametrize(
    ("header", "start", "end"),
    [
        ("bytes=0-0", 0, 0),
        ("bytes=0-999", 0, 999),  # ちょうど 1 チャンク
        ("bytes=999-1000", 999, 1000),  # チャンクの境界をまたぐ
        ("bytes=500-2600", 500, 2600),  # 3 チャンクにまたがる
        ("bytes=1000-1999", 1000, 1999),
        ("bytes=3000-3499", 3000, 3499),  # 最後のチャンク
        ("bytes=3400-", 3400, 3499),  # 開始のみ
        ("bytes=0-", 0, 3499),
        ("bytes=-100", 3400, 3499),  # 末尾から
        ("bytes=-99999", 0, 3499),  # 末尾指定が大きさを超える
        ("bytes=3000-99999", 3000, 3499),  # 終了が大きさを超えるときは末尾に丸める
    ],
)
def test_ranges(user: TestUser, video_id: int, header: str, start: int, end: int) -> None:
    res = _get(user, video_id, header)
    assert res.status_code == 206
    assert res.content == DATA[start : end + 1]
    assert res.headers["content-range"] == f"bytes {start}-{end}/{SIZE}"
    assert res.headers["content-length"] == str(end - start + 1)


@pytest.mark.parametrize("header", [f"bytes={SIZE}-", f"bytes={SIZE + 10}-{SIZE + 20}", "bytes=5-2", "bytes=-0"])
def test_unsatisfiable_range_is_416(user: TestUser, video_id: int, header: str) -> None:
    res = _get(user, video_id, header)
    assert res.status_code == 416
    assert res.headers["content-range"] == f"bytes */{SIZE}"
    assert res.json() == {"detail": "指定の範囲は取得できません"}


@pytest.mark.parametrize("header", ["bytes=0-1,5-6", "bytes=abc", "items=0-5", "bytes=-", "bytes=1-2-3", ""])
def test_malformed_range_is_400(user: TestUser, video_id: int, header: str) -> None:
    if header == "":
        # 空の Range は指定なしと同じ（全体を返す）
        assert _get(user, video_id, header).status_code == 200
        return
    assert _get(user, video_id, header).status_code == 400


def test_reassembling_by_ranges_matches_original(user: TestUser, video_id: int) -> None:
    """動画要素のように小刻みな範囲で取り直しても、元のバイト列と一致する。"""
    step = 333
    parts = []
    for start in range(0, SIZE, step):
        end = min(start + step - 1, SIZE - 1)
        res = _get(user, video_id, f"bytes={start}-{end}")
        assert res.status_code == 206
        parts.append(res.content)
    assert b"".join(parts) == DATA


def test_only_ready_video_is_streamed(user: TestUser) -> None:
    uploading = user.client.post("/videos", json={"title": "登録中", "duration_ms": 1000}).json()["id"]
    res = _get(user, uploading)
    assert res.status_code == 422
    assert res.json() == {"detail": "再生できない動画です"}


def test_other_user_and_anonymous_cannot_stream(user: TestUser, other_user: TestUser, video_id: int) -> None:
    assert _get(other_user, video_id).status_code == 404
    assert TestClient(app).get(f"/videos/{video_id}/stream").status_code == 401
    assert _get(user, 99999999).status_code == 404


def test_stream_logs_only_first_range(user: TestUser, video_id: int, log_dir) -> None:
    from conftest import log_text

    _get(user, video_id, "bytes=0-99")
    _get(user, video_id, "bytes=1000-1099")
    _get(user, video_id, "bytes=2000-2099")
    assert log_text(log_dir).count("動画配信要求") == 1
