from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError
from app.services import budget_service

router = APIRouter(prefix="/budget-items")


class BudgetItemCreateBody(BaseModel):
    budget_period_id: int
    name: str
    amount: str
    display_order: int


class BudgetItemUpdateBody(BaseModel):
    name: str
    amount: str
    display_order: int


@router.get("")
def list_budget_items(
    budget_period_id: int = Query(...),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        return {"items": budget_service.list_items(auth.user.id, budget_period_id)}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.post("", status_code=201)
def create_budget_item(
    body: BudgetItemCreateBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return budget_service.add_item(
            auth.user.id, body.budget_period_id, body.name, body.amount, body.display_order
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None


@router.patch("/{budget_item_id}")
def patch_budget_item(
    budget_item_id: int,
    body: BudgetItemUpdateBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return budget_service.change_item(
            auth.user.id, budget_item_id, body.name, body.amount, body.display_order
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.delete("/{budget_item_id}", status_code=204)
def delete_budget_item(
    budget_item_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        budget_service.remove_item(auth.user.id, budget_item_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
