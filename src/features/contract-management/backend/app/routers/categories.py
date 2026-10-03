from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, StrictBool

from app.deps import AuthContext, get_cookie_user, get_current_user
from app.services import category_service

router = APIRouter()


class CategoryIn(BaseModel):
    name: str
    is_financial: StrictBool = False


@router.get("/categories")
def list_categories(ctx: AuthContext = Depends(get_current_user)) -> dict[str, object]:
    return {"items": category_service.list_categories(ctx.user.id)}


@router.post("/categories", status_code=201)
def create_category(body: CategoryIn, ctx: AuthContext = Depends(get_cookie_user)) -> dict[str, object]:
    return category_service.create_category(ctx.user.id, body.name, body.is_financial)


@router.patch("/categories/{category_id}")
def update_category(
    category_id: int, body: CategoryIn, ctx: AuthContext = Depends(get_cookie_user)
) -> dict[str, object]:
    return category_service.update_category(ctx.user.id, category_id, body.name, body.is_financial)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, ctx: AuthContext = Depends(get_cookie_user)) -> Response:
    category_service.delete_category(ctx.user.id, category_id)
    return Response(status_code=204)
