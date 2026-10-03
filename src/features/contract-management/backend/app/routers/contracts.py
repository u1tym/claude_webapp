from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.contract_model import ContractIn

from app.deps import AuthContext, get_cookie_user, get_current_user
from app.services import contract_service

router = APIRouter()


@router.get("/contracts")
def list_contracts(
    keyword: str | None = None,
    category_id: int | None = None,
    status: str | None = None,
    has_contract: bool | None = None,
    password_unset: bool | None = None,
    ctx: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    return contract_service.list_contracts(
        ctx.user.id, keyword, category_id, status, has_contract, password_unset
    )


@router.get("/contracts/{contract_id}")
def get_contract(contract_id: int, ctx: AuthContext = Depends(get_current_user)) -> dict[str, object]:
    return contract_service.get_contract(ctx.user.id, contract_id)


@router.get("/contracts/{contract_id}/password")
def get_password(contract_id: int, ctx: AuthContext = Depends(get_cookie_user)) -> dict[str, object]:
    return contract_service.get_password(ctx.user.id, contract_id)


@router.post("/contracts", status_code=201)
def create_contract(body: ContractIn, ctx: AuthContext = Depends(get_current_user)) -> dict[str, object]:
    return contract_service.create_contract(ctx.user.id, body, ctx.via_api_key)


@router.patch("/contracts/{contract_id}")
def update_contract(
    contract_id: int, body: ContractIn, ctx: AuthContext = Depends(get_current_user)
) -> dict[str, object]:
    return contract_service.update_contract(ctx.user.id, contract_id, body, ctx.via_api_key)


@router.delete("/contracts/{contract_id}", status_code=204)
def delete_contract(contract_id: int, ctx: AuthContext = Depends(get_cookie_user)) -> Response:
    contract_service.delete_contract(ctx.user.id, contract_id)
    return Response(status_code=204)
