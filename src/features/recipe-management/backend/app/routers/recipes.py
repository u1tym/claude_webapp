from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.common import Required, Trimmed
from app.deps import AuthContext, get_current_user
from app.services import recipe_service

router = APIRouter(tags=["recipes"])


class ItemBody(BaseModel):
    ingredient_id: int
    measurement_id: int
    amount: Trimmed


class StepBody(BaseModel):
    description: Required
    items: list[ItemBody]


class RecipeBody(BaseModel):
    name: Required
    kana: Required
    steps: Annotated[list[StepBody], Field(min_length=1)]


@router.get("/recipes")
def list_recipes(auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return recipe_service.list_recipes(auth.user.id)


@router.post("/recipes", status_code=201)
def create_recipe(body: RecipeBody, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return recipe_service.create_recipe(auth.user.id, body.model_dump())


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return recipe_service.get_recipe(auth.user.id, recipe_id)


@router.put("/recipes/{recipe_id}")
def update_recipe(recipe_id: int, body: RecipeBody, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return recipe_service.update_recipe(auth.user.id, recipe_id, body.model_dump())


@router.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, auth: AuthContext = Depends(get_current_user)) -> Response:
    recipe_service.delete_recipe(auth.user.id, recipe_id)
    return Response(status_code=204)
