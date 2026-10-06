from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError
from app.services import schedule_service
from app.services.schedule_service import UNSET, ScheduleInput

router = APIRouter()


class ScheduleBody(BaseModel):
    """定期実行の登録・変更の要求本文。値の検証は schedule_service で行う。"""

    condition: Any = None
    weekdays: Any = None
    run_time: Any = None
    scene: Any = None
    is_enabled: Any = None
    holiday_mode: Any = None
    day_shift: Any = None
    device: Any = None
    state: Any = None
    pattern: Any = None
    # タイトルと表示順。要求に項目が無いのと、`null` とは区別する（model_fields_set で見分ける）
    title: Any = None
    display_order: Any = None


class EnabledBody(BaseModel):
    is_enabled: Any = None


def _input(body: ScheduleBody | None) -> ScheduleInput:
    body = body or ScheduleBody()
    return ScheduleInput(
        condition=body.condition,
        weekdays=body.weekdays,
        run_time=body.run_time,
        scene=body.scene,
        is_enabled=body.is_enabled,
        holiday_mode=body.holiday_mode,
        day_shift=body.day_shift,
        device=body.device,
        state=body.state,
        pattern=body.pattern,
        title=body.title if "title" in body.model_fields_set else UNSET,
        display_order=body.display_order if "display_order" in body.model_fields_set else UNSET,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="対象がありません")


def _invalid() -> HTTPException:
    return HTTPException(status_code=400, detail="入力が不正です")


@router.get("/schedules")
def get_schedules(_auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return {"schedules": schedule_service.list_schedules()}


@router.post("/schedules", status_code=201)
def post_schedule(
    body: ScheduleBody | None = None, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    try:
        return schedule_service.create_schedule(_input(body), auth.user.id, auth.user.username)
    except InvalidInputError:
        raise _invalid() from None


@router.put("/schedules/{schedule_id}")
def put_schedule(
    schedule_id: int,
    body: ScheduleBody | None = None,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return schedule_service.update_schedule(schedule_id, _input(body), auth.user.username)
    except InvalidInputError:
        raise _invalid() from None
    except NotFoundError:
        raise _not_found() from None


@router.put("/schedules/{schedule_id}/enabled")
def put_schedule_enabled(
    schedule_id: int,
    body: EnabledBody | None = None,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return schedule_service.set_enabled(
            schedule_id, (body or EnabledBody()).is_enabled, auth.user.username
        )
    except InvalidInputError:
        raise _invalid() from None
    except NotFoundError:
        raise _not_found() from None


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: int, auth: AuthContext = Depends(get_current_user)
) -> Response:
    try:
        schedule_service.delete_schedule(schedule_id, auth.user.username)
    except NotFoundError:
        raise _not_found() from None
    return Response(status_code=204)
