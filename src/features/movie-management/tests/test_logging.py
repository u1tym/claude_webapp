from __future__ import annotations

import re

from conftest import TestUser, log_text, make_video_file, upload_video

LINE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d (INF|WRN|ERR|DBG) .+$")


def test_every_line_is_timestamp_level_message(user: TestUser, log_dir) -> None:
    upload_video(user.client, make_video_file(2500))
    user.client.get("/videos/99999999")
    lines = log_text(log_dir).splitlines()
    assert lines
    assert all(LINE.match(line) for line in lines), lines


def test_operations_are_logged_with_input_and_result(user: TestUser, log_dir) -> None:
    user.client.post("/genres", json={"name": "ログ用"})
    series_id = user.client.post("/series", json={"title": "ログ作品"}).json()["id"]
    video_id = upload_video(user.client, make_video_file(2500), title="ログ動画", series_id=series_id)
    user.client.patch(f"/videos/{video_id}", json={"title": "改題"})
    user.client.post(f"/videos/{video_id}/playback/start", json={})
    user.client.get("/videos", params={"q": "検索語"})
    user.client.post(f"/videos/{video_id}/replace", json={"duration_ms": 1000})
    user.client.delete(f"/videos/{video_id}")
    text = log_text(log_dir)
    for expected in (
        "ジャンル追加要求", "name=ログ用", "ジャンル追加成功",
        "作品登録要求", "title=ログ作品", "作品登録成功",
        "動画登録要求", "title=ログ動画", "動画登録成功",
        "動画ファイル登録開始", "動画ファイル登録完了", "chunk_count=3",
        "動画編集要求", "動画編集成功",
        "再生開始要求", "再生開始 ",
        "動画一覧", "q=検索語",
        "動画ファイル差し替え要求", "動画ファイル差し替え開始",
        "動画削除要求", "動画削除成功",
    ):
        assert expected in text, expected


def test_failures_log_internal_reason_but_not_in_response(user: TestUser, log_dir) -> None:
    res = user.client.get("/videos/99999999")
    assert res.status_code == 404
    assert res.json() == {"detail": "対象がありません"}
    text = log_text(log_dir)
    assert "WRN" in text
    assert "動画なし" in text and "video_id=99999999" in text
    assert "動画なし" not in res.text


def test_conflict_reason_is_logged(user: TestUser, log_dir) -> None:
    user.client.post("/genres", json={"name": "重複"})
    user.client.post("/genres", json={"name": "重複"})
    assert "ジャンル名重複" in log_text(log_dir)


def test_chunk_transfer_is_not_logged_per_chunk(user: TestUser, log_dir) -> None:
    video_id = upload_video(user.client, make_video_file(9000), chunk_size=1000)  # 9 チャンク
    for start in range(0, 9000, 1000):
        user.client.get(f"/videos/{video_id}/stream", headers={"Range": f"bytes={start}-{start + 999}"})
    text = log_text(log_dir)
    assert text.count("動画ファイル登録開始") == 1
    assert text.count("動画ファイル登録完了 ") == 1
    assert text.count("動画配信要求") == 1  # 範囲要求は先頭からのものだけ
    assert "chunk_index" not in text


def test_position_saves_are_not_logged(user: TestUser, log_dir) -> None:
    video_id = upload_video(user.client, make_video_file(500))
    before = len(log_text(log_dir).splitlines())
    for position in (100, 200, 300):
        user.client.put(f"/videos/{video_id}/playback/state", json={"position_ms": position})
    assert len(log_text(log_dir).splitlines()) == before


def test_secrets_are_never_logged(user: TestUser, log_dir) -> None:
    session_id = user.client.cookies.get("session_id")
    user.client.get("/genres")
    user.client.post("/videos", json={"title": "t", "duration_ms": 1000, "description": "秘密の説明文"})
    text = log_text(log_dir)
    assert session_id and session_id not in text
    assert "秘密の説明文" not in text  # 説明文の値そのものは出さない
