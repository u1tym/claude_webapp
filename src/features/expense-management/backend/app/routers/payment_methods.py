from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError
from app.services import payment_method_service
from app.services.closing_date_service import estimate_payment_date
from app.services.payment_method_service import PaymentMethodInput

router = APIRouter(prefix="/payment-methods")


class ExclusionItem(BaseModel):
    exclusion_kind: str


class PaymentMethodBody(BaseModel):
    name: str
    closing_day: int
    closing_day_shift_direction: str | None = None
    closing_day_exclusions: list[ExclusionItem] = Field(default_factory=list)
    payment_month_offset: int | None = None
    payment_day: int | None = None
    payment_day_shift_direction: str | None = None
    payment_day_exclusions: list[ExclusionItem] = Field(default_factory=list)
    display_order: int

    def to_input(self) -> PaymentMethodInput:
        return PaymentMethodInput(
            name=self.name,
            closing_day=self.closing_day,
            closing_day_shift_direction=self.closing_day_shift_direction,
            closing_day_exclusions=[item.exclusion_kind for item in self.closing_day_exclusions],
            payment_month_offset=self.payment_month_offset,
            payment_day=self.payment_day,
            payment_day_shift_direction=self.payment_day_shift_direction,
            payment_day_exclusions=[item.exclusion_kind for item in self.payment_day_exclusions],
            display_order=self.display_order,
        )


@router.get("")
def list_payment_methods(
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    return {"items": payment_method_service.list_for_user(auth.user.id)}


@router.post("", status_code=201)
def create_payment_method(
    body: PaymentMethodBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return payment_method_service.create_payment_method(auth.user.id, body.to_input())
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None


@router.patch("/{payment_method_id}")
def patch_payment_method(
    payment_method_id: int,
    body: PaymentMethodBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return payment_method_service.change_payment_method(auth.user.id, payment_method_id, body.to_input())
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.delete("/{payment_method_id}", status_code=204)
def delete_payment_method(
    payment_method_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        payment_method_service.remove_payment_method(auth.user.id, payment_method_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.get("/{payment_method_id}/estimated-payment-date")
def get_estimated_payment_date(
    payment_method_id: int,
    usage_date: date = Query(...),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    try:
        method = payment_method_service.require_own_active(auth.user.id, payment_method_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    closing_exclusions = payment_method_service.exclusions_for(payment_method_id, "closing_day")
    payment_exclusions = payment_method_service.exclusions_for(payment_method_id, "payment_day")
    result = estimate_payment_date(
        usage_date=usage_date,
        closing_day=method.closing_day,
        closing_day_shift_direction=method.closing_day_shift_direction,
        closing_day_exclusions=closing_exclusions,
        payment_month_offset=method.payment_month_offset,
        payment_day=method.payment_day,
        payment_day_shift_direction=method.payment_day_shift_direction,
        payment_day_exclusions=payment_exclusions,
    )
    return {"payment_date": result.isoformat()}
