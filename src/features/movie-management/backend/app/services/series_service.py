from __future__ import annotations

from typing import Any

from app.common import Page, build_pagination, like_pattern
from app.db import get_conn
from app.errors import NotFoundError
from app.logger import write
from app.repos import series as series_repo


def list_series(user_id: int, paging: Page, q: str | None) -> dict[str, Any]:
    keyword = q.strip() if q else ""
    pattern = like_pattern(keyword) if keyword else None
    with get_conn() as conn, conn.cursor() as cur:
        total = series_repo.count_series(cur, user_id, pattern)
        items = series_repo.list_series(cur, user_id, pattern, paging.per_page, paging.offset)
    write("INF", f"作品一覧 user_id={user_id} q={keyword} 件数={len(items)}/{total}")
    return {"items": items, "pagination": build_pagination(paging, total).model_dump()}


def create_series(user_id: int, title: str, description: str | None) -> dict[str, Any]:
    write("INF", f"作品登録要求 user_id={user_id} title={title}")
    with get_conn() as conn, conn.cursor() as cur:
        item = series_repo.insert_series(cur, user_id, title, description)
    write("INF", f"作品登録成功 user_id={user_id} series_id={item['id']}")
    return item


def get_series_detail(user_id: int, series_id: int) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        series = series_repo.get_series(cur, user_id, series_id)
        if series is None:
            raise NotFoundError(reason=f"作品なし user_id={user_id} series_id={series_id}")
        videos = series_repo.list_series_videos(cur, user_id, series_id)
    write("INF", f"作品詳細 user_id={user_id} series_id={series_id} 動画数={len(videos)}")
    return {**series, "videos": videos}
