from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone

from app.config import Config, load_config
from app.logger import write
from app.repos import CandidateRow, insert_notified, is_notified, list_candidates
from app.services.mail_service import build_body, build_subject, send_mail

JST = timezone(timedelta(hours=9))

SendFn = Callable[[Config, str, str, str], None]


def now_jst() -> datetime:
    return datetime.now(JST).replace(tzinfo=None)


def start_datetime(
    start_date: date,
    start_time: time | None,
    granularity: str,
    day_time: time,
) -> datetime:
    if granularity == "day":
        return datetime.combine(start_date, day_time)
    if start_time is None:
        return datetime.combine(start_date, day_time)
    return datetime.combine(start_date, start_time)


def lookback_lower(judged_at: datetime, lookback_days: int) -> date:
    return judged_at.date() - timedelta(days=lookback_days)


def threshold_at(judged_at: datetime, lead_minutes: int) -> datetime:
    return judged_at + timedelta(minutes=lead_minutes)


def format_start_text(start: datetime) -> str:
    return start.strftime("%Y-%m-%d %H:%M")


def _email_present(email: str) -> bool:
    return bool(email.strip())


def _process_row(
    row: CandidateRow,
    cfg: Config,
    threshold: datetime,
    send: SendFn,
) -> None:
    write(
        "INF",
        "判定 schedule_id=%s user_id=%s kind=%s granularity=%s "
        "start_date=%s email_present=%s"
        % (
            row.id,
            row.user_id,
            row.kind,
            row.granularity,
            row.start_date.isoformat(),
            _email_present(row.email),
        ),
    )
    if is_notified(row.id):
        write("INF", f"対象外 schedule_id={row.id} 理由=通知済み")
        return
    if row.kind == "todo" and row.is_completed is not False:
        write("INF", f"対象外 schedule_id={row.id} 理由=TODO実施済み")
        return
    start = start_datetime(row.start_date, row.start_time, row.granularity, cfg.notice_day_time)
    write("INF", f"開始日時 schedule_id={row.id} start={format_start_text(start)}")
    if start >= threshold:
        write("INF", f"対象外 schedule_id={row.id} 理由=開始がしきい時刻以降")
        return
    if row.user_deleted:
        write(
            "WRN",
            f"送らない schedule_id={row.id} user_id={row.user_id} 理由=所有者論理削除済み",
        )
        return
    if not _email_present(row.email):
        write(
            "WRN",
            f"送らない schedule_id={row.id} user_id={row.user_id} 理由=メールアドレス空",
        )
        return
    subject = build_subject(row.kind, row.title)
    body = build_body(row.title, format_start_text(start))
    try:
        send(cfg, row.email, subject, body)
    except Exception as exc:
        write(
            "ERR",
            f"送信失敗 schedule_id={row.id} user_id={row.user_id} "
            f"理由={type(exc).__name__}",
        )
        return
    if not insert_notified(row.id):
        write("INF", f"記録済のため追加せず schedule_id={row.id} 理由=通知済み")
        return
    write("INF", f"送信成功 schedule_id={row.id} user_id={row.user_id}")


def run_once(
    *,
    now: datetime | None = None,
    send: SendFn | None = None,
) -> None:
    cfg = load_config()
    for warning in cfg.setting_warnings:
        write("WRN", warning)
    judged_at = now if now is not None else now_jst()
    threshold = threshold_at(judged_at, cfg.notice_lead_minutes)
    lower = lookback_lower(judged_at, cfg.notice_lookback_days)
    write(
        "INF",
        "判定開始 judged_at=%s lead_minutes=%s day_time=%s lookback_days=%s "
        "lower_date=%s threshold=%s"
        % (
            judged_at.strftime("%Y-%m-%d %H:%M"),
            cfg.notice_lead_minutes,
            cfg.notice_day_time.strftime("%H:%M"),
            cfg.notice_lookback_days,
            lower.isoformat(),
            threshold.strftime("%Y-%m-%d %H:%M"),
        ),
    )
    rows = list_candidates(lower)
    write("INF", f"取得件数 n={len(rows)}")
    sender = send if send is not None else send_mail
    for row in rows:
        try:
            _process_row(row, cfg, threshold, sender)
        except Exception as exc:
            write(
                "ERR",
                f"件の処理失敗 schedule_id={row.id} 理由={type(exc).__name__}",
            )
