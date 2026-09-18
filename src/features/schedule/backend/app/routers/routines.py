from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError
from app.services import routine_service

router = APIRouter(prefix="/routines")


class RoutineBody(BaseModel):
    title: str
    detail: str | None = None
    kind: str
    category_id: int
    occurrence_type: str
    date_rule: str | None = None
    day_of_month: int | None = None
    weekday_rule: str | None = None
    weekday_n: int | None = None
    weekday: str | None = None
    adjust_excluded: bool
    shift_direction: str | None = None
    months: list[int]
    exclusions: list[str] = Field(default_factory=list)
    needs_notification: bool

    @field_validator("needs_notification", mode="before")
    @classmethod
    def require_bool_notification(cls, value: object) -> object:
        if not isinstance(value, bool):
            raise ValueError("needs_notification が真偽でない")
        return value


class ApplyBody(BaseModel):
    year: int
    month: int


@router.get("")
def list_routines(
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    return {"items": routine_service.list_for_user(auth.user.id)}


@router.post("", status_code=201)
def create_routine(
    body: RoutineBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return routine_service.add_routine(
            auth.user.id,
            body.title,
            body.detail,
            body.kind,
            body.category_id,
            body.occurrence_type,
            body.date_rule,
            body.day_of_month,
            body.weekday_rule,
            body.weekday_n,
            body.weekday,
            body.adjust_excluded,
            body.shift_direction,
            body.needs_notification,
            body.months,
            body.exclusions,
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.patch("/{routine_id}")
def patch_routine(
    routine_id: int,
    body: RoutineBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return routine_service.change_routine(
            auth.user.id,
            routine_id,
            body.title,
            body.detail,
            body.kind,
            body.category_id,
            body.occurrence_type,
            body.date_rule,
            body.day_of_month,
            body.weekday_rule,
            body.weekday_n,
            body.weekday,
            body.adjust_excluded,
            body.shift_direction,
            body.needs_notification,
            body.months,
            body.exclusions,
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.post("/apply-all")
def apply_all_routines(
    body: ApplyBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        items = routine_service.apply_all(auth.user.id, body.year, body.month)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    return {"items": items}


@router.post("/{routine_id}/apply")
def apply_one_routine(
    routine_id: int,
    body: ApplyBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        items = routine_service.apply_routine(auth.user.id, routine_id, body.year, body.month)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    return {"items": items}


@router.delete("/{routine_id}", status_code=204)
def delete_routine(
    routine_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        routine_service.remove_routine(auth.user.id, routine_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
