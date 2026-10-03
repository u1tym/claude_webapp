from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, StrictInt

from app.deps import AuthContext, get_cookie_user, get_current_user
from app.services import cancellation_service

router = APIRouter()


class PlanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_ids: list[StrictInt]


@router.get("/cancellation-plan")
def get_plan(ctx: AuthContext = Depends(get_current_user)) -> dict[str, object]:
    return cancellation_service.get_plan(ctx.user.id)


@router.get("/cancellation-plan/candidates")
def list_candidates(ctx: AuthContext = Depends(get_cookie_user)) -> dict[str, object]:
    return cancellation_service.list_candidates(ctx.user.id)


@router.put("/cancellation-plan")
def save_plan(body: PlanIn, ctx: AuthContext = Depends(get_cookie_user)) -> dict[str, object]:
    return cancellation_service.save_plan(ctx.user.id, body.contract_ids)
