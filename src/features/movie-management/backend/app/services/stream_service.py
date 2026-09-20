"""動画ファイルの範囲配信。

チャンクのバイト長を先頭から積み上げて各チャンクの動画内の位置を求め（データ本体は読まない）、
要求された範囲にかかるチャンクだけを 1 つずつ取得して返す。同時にメモリへ載せるのは 1 チャンク分。
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass

from app.db import connect, get_conn
from app.errors import InvalidInputError, NotFoundError, RangeNotSatisfiableError, UnprocessableError
from app.logger import write
from app.repos import chunk as chunk_repo
from app.repos import video as video_repo

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


@dataclass(frozen=True)
class StreamPlan:
    status_code: int
    media_type: str
    content_length: int
    content_range: str | None
    body: Iterator[bytes]


def parse_range(header: str, total: int) -> tuple[int, int]:
    """Range ヘッダを (開始, 終了) のバイト位置（両端を含む）にする。

    a-b / a- / -n の 3 形式のうち 1 つだけを受け付ける。
    """
    text = header.strip()
    if "," in text:
        raise InvalidInputError(reason=f"複数範囲は未対応 Range={text}")
    match = _RANGE_RE.match(text)
    if match is None or (match.group(1) == "" and match.group(2) == ""):
        raise InvalidInputError(reason=f"Range の形式不正 Range={text}")
    first, last = match.group(1), match.group(2)
    unsatisfiable = RangeNotSatisfiableError(
        reason=f"範囲外 Range={text} total={total}", headers={"Content-Range": f"bytes */{total}"}
    )
    if first == "":  # 末尾から n バイト
        length = int(last)
        if length == 0:
            raise unsatisfiable
        return max(total - length, 0), total - 1
    start = int(first)
    if start >= total:
        raise unsatisfiable
    if last == "":
        return start, total - 1
    end = int(last)
    if start > end:
        raise unsatisfiable
    return start, min(end, total - 1)


def _iter_range(video_id: int, parts: list[tuple[int, int, int]]) -> Iterator[bytes]:
    """parts = [(チャンク番号, チャンク内の開始位置, 取り出す長さ)]。1 接続で 1 チャンクずつ取得する。"""
    conn = connect()
    try:
        with conn.cursor() as cur:
            for chunk_index, offset, length in parts:
                cur.execute(
                    """
                    SELECT substring(data FROM %s FOR %s) AS part
                    FROM movie_management.video_chunks
                    WHERE video_id = %s AND chunk_index = %s
                    """,
                    (offset + 1, length, video_id, chunk_index),
                )
                row = cur.fetchone()
                if row is None:  # 配信中に動画が削除された
                    write("WRN", f"配信中にチャンクが消えた video_id={video_id} chunk_index={chunk_index}")
                    return
                yield bytes(row["part"])
    finally:
        conn.close()


def prepare_stream(user_id: int, video_id: int, range_header: str | None) -> StreamPlan:
    with get_conn() as conn, conn.cursor() as cur:
        video = video_repo.get_owned(cur, user_id, video_id)
        if video is None:
            raise NotFoundError(reason=f"動画なし user_id={user_id} video_id={video_id}")
        if video["status"] != "ready":
            raise UnprocessableError(
                "再生できない動画です", reason=f"再生不可の動画の配信 video_id={video_id} status={video['status']}"
            )
        layout = chunk_repo.layout(cur, video_id)
    total = sum(length for _, length in layout)
    if total <= 0:
        raise UnprocessableError("再生できない動画です", reason=f"チャンクなし video_id={video_id}")

    if range_header:
        start, end = parse_range(range_header, total)
        status_code = 206
    else:
        start, end = 0, total - 1
        status_code = 200

    # 各チャンクの動画内の開始位置
    starts: list[int] = []
    position = 0
    for _, length in layout:
        starts.append(position)
        position += length

    parts: list[tuple[int, int, int]] = []
    first = bisect_right(starts, start) - 1
    for i in range(first, len(layout)):
        chunk_start = starts[i]
        if chunk_start > end:
            break
        chunk_index, length = layout[i]
        lo = max(start, chunk_start) - chunk_start
        hi = min(end, chunk_start + length - 1) - chunk_start
        parts.append((chunk_index, lo, hi - lo + 1))

    if start == 0:
        # 範囲要求は動画要素から頻繁に届くため、先頭からの要求だけを記録する
        write("INF", f"動画配信要求 user_id={user_id} video_id={video_id} range={range_header or '-'}")
    return StreamPlan(
        status_code=status_code,
        media_type=str(video["mime_type"]),
        content_length=end - start + 1,
        content_range=f"bytes {start}-{end}/{total}" if status_code == 206 else None,
        body=_iter_range(video_id, parts),
    )
