from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError
from app.services import expense_service
from app.services.expense_service import ExpenseInput

router = APIRouter(prefix="/expenses")


class ExpenseBody(BaseModel):
    usage_date: date
    budget_item_id: int
    purpose: str
    amount: str
    payment_method_id: int
    memo: str | None = None
    payment_date: date

    def to_input(self) -> ExpenseInput:
        return ExpenseInput(
            usage_date=self.usage_date,
            budget_item_id=self.budget_item_id,
            purpose=self.purpose,
            amount=self.amount,
            payment_method_id=self.payment_method_id,
            memo=self.memo,
            payment_date=self.payment_date,
        )


@router.get("")
def list_expenses(
    start_date: date = Query(...),
    end_date: date = Query(...),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        return {"items": expense_service.list_for_range(auth.user.id, start_date, end_date)}
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None


@router.post("", status_code=201)
def create_expense(
    body: ExpenseBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return expense_service.create_expense(auth.user.id, body.to_input())
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None


@router.patch("/{expense_id}")
def patch_expense(
    expense_id: int,
    body: ExpenseBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return expense_service.change_expense(auth.user.id, expense_id, body.to_input())
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.delete("/{expense_id}", status_code=204)
def delete_expense(
    expense_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        expense_service.remove_expense(auth.user.id, expense_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
