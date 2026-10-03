from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import AuthContext, get_cookie_user
from app.services import contract_service

router = APIRouter()


@router.get("/accounts")
def list_accounts(keyword: str | None = None, ctx: AuthContext = Depends(get_cookie_user)) -> dict[str, object]:
    return contract_service.list_accounts(ctx.user.id, keyword)
