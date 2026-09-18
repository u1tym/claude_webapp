from __future__ import annotations

from datetime import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator

from app.deps import AuthContext, get_current_user
from app.errors import CompletionNotAllowedError, InvalidInputError, NotFoundError
from app.services import schedule_service
from app.services.category_service import parse_date, parse_time

router = APIRouter(prefix="/schedules")


class ScheduleBody(BaseModel):
    title: str
    location: str | None = None
    detail: str | None = None
    kind: str
    granularity: str
    start_date: str
    end_date: str
    start_time: str | None = None
    end_time: str | None = None
    category_id: int
    needs_notification: bool

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def empty_time_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("needs_notification", mode="before")
    @classmethod
    def require_bool_notification(cls, value: object) -> object:
        if not isinstance(value, bool):
            raise ValueError("needs_notification が真偽でない")
        return value


class CompletionBody(BaseModel):
    is_completed: bool


def _times(granularity: str, start_raw: str | None, end_raw: str | None) -> tuple[time | None, time | None]:
    if granularity == "day":
        if start_raw is not None or end_raw is not None:
            raise InvalidInputError("日単位に時刻がある")
        return None, None
    if start_raw is None or end_raw is None:
        raise InvalidInputError("時間単位に時刻がない")
    return parse_time(start_raw), parse_time(end_raw)


@router.get("")
def list_schedules(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    if start_date is None or end_date is None:
        raise HTTPException(status_code=400, detail="入力が不正です")
    try:
        start = parse_date(start_date)
        end = parse_date(end_date)
        items = schedule_service.list_for_range(auth.user.id, start, end)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    return {"items": items}


@router.post("", status_code=201)
def create_schedule(
    body: ScheduleBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        start = parse_date(body.start_date)
        end = parse_date(body.end_date)
        start_time, end_time = _times(body.granularity, body.start_time, body.end_time)
        return schedule_service.add_schedule(
            auth.user.id,
            body.title,
            body.location,
            body.detail,
            body.kind,
            body.granularity,
            start,
            end,
            start_time,
            end_time,
            body.category_id,
            body.needs_notification,
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.patch("/{schedule_id}")
def patch_schedule(
    schedule_id: int,
    body: ScheduleBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        start = parse_date(body.start_date)
        end = parse_date(body.end_date)
        start_time, end_time = _times(body.granularity, body.start_time, body.end_time)
        return schedule_service.change_schedule(
            auth.user.id,
            schedule_id,
            body.title,
            body.location,
            body.detail,
            body.kind,
            body.granularity,
            start,
            end,
            start_time,
            end_time,
            body.category_id,
            body.needs_notification,
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.patch("/{schedule_id}/completion")
def patch_completion(
    schedule_id: int,
    body: CompletionBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return schedule_service.change_completion(auth.user.id, schedule_id, body.is_completed)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except CompletionNotAllowedError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        schedule_service.remove_schedule(auth.user.id, schedule_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
