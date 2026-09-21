from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.common import Required
from app.deps import AuthContext, get_current_user
from app.services import ingredient_service

router = APIRouter(tags=["ingredients"])


class IngredientCreate(BaseModel):
    name: Required
    kana: Required


@router.get("/ingredients")
def list_ingredients(auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return ingredient_service.list_ingredients(auth.user.id)


@router.post("/ingredients", status_code=201)
def create_ingredient(body: IngredientCreate, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return ingredient_service.create_ingredient(auth.user.id, body.name, body.kana)
