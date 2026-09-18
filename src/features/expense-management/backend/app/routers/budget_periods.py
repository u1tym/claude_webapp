from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError
from app.services import budget_service

router = APIRouter(prefix="/budget-periods")


class BudgetPeriodBody(BaseModel):
    title: str
    start_date: date
    end_date: date


@router.get("")
def list_budget_periods(
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    return {"items": budget_service.list_periods(auth.user.id)}


@router.post("", status_code=201)
def create_budget_period(
    body: BudgetPeriodBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return budget_service.create_period(auth.user.id, body.title, body.start_date, body.end_date)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None


@router.patch("/{budget_period_id}")
def update_budget_period(
    budget_period_id: int,
    body: BudgetPeriodBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return budget_service.change_period(
            auth.user.id, budget_period_id, body.title, body.start_date, body.end_date
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.post("/{budget_period_id}/duplicate", status_code=201)
def duplicate_budget_period(
    budget_period_id: int,
    body: BudgetPeriodBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return budget_service.duplicate_period(
            auth.user.id, budget_period_id, body.title, body.start_date, body.end_date
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
