from __future__ import annotations

from datetime import datetime, timedelta, timezone

# 日本標準時。Windows には tz データベースが無いことがあるため、固定のオフセットで持つ
JST = timezone(timedelta(hours=9))


def now_jst() -> datetime:
    """日本標準時の現在日時を返す。"""
    return datetime.now(JST)


def iso_seconds(value: datetime) -> str:
    """秒までの ISO 8601（日本標準時のオフセット付き）にする。例: 2026-10-01T10:15:30+09:00"""
    return value.astimezone(JST).isoformat(timespec="seconds")
