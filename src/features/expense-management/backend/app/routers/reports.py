from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError
from app.services import report_service

router = APIRouter(prefix="/reports")


@router.get("/usage-date")
def get_usage_date_report(
    budget_period_id: int = Query(...),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return report_service.usage_date_report(auth.user.id, budget_period_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.get("/payment-month")
def get_payment_month_report(
    year_month: str = Query(...),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return report_service.payment_month_report(auth.user.id, year_month)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
