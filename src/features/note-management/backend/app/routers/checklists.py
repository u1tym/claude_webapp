from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StrictBool

from app.common import Required, Trimmed
from app.deps import AuthContext, get_current_user
from app.services import checklist_service

router = APIRouter(tags=["checklists"])


class TitleBody(BaseModel):
    title: Trimmed


class CategoryBody(BaseModel):
    name: Required


class ReorderBody(BaseModel):
    ordered_ids: list[int]


class ItemCreateBody(BaseModel):
    category_id: int | None = None
    title: Trimmed = ""


class ItemUpdateBody(BaseModel):
    title: Trimmed | None = None
    is_checked: StrictBool | None = None


class ItemMoveBody(BaseModel):
    to_category_id: int
    to_index: int = Field(ge=0)


@router.get("/checklists/{checklist_id}")
def get_checklist(checklist_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return checklist_service.get_checklist(auth.user.id, checklist_id)


@router.patch("/checklists/{checklist_id}")
def update_title(checklist_id: int, body: TitleBody, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return checklist_service.update_title(auth.user.id, checklist_id, body.title)


@router.post("/checklists/{checklist_id}/categories")
def create_category(
    checklist_id: int, body: CategoryBody, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return checklist_service.create_category(auth.user.id, checklist_id, body.name)


@router.post("/checklists/{checklist_id}/categories/reorder")
def reorder_categories(
    checklist_id: int, body: ReorderBody, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return checklist_service.reorder_categories(auth.user.id, checklist_id, body.ordered_ids)


@router.patch("/checklists/{checklist_id}/categories/{category_id}")
def rename_category(
    checklist_id: int, category_id: int, body: CategoryBody, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return checklist_service.rename_category(auth.user.id, checklist_id, category_id, body.name)


@router.delete("/checklists/{checklist_id}/categories/{category_id}")
def delete_category(
    checklist_id: int, category_id: int, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return checklist_service.delete_category(auth.user.id, checklist_id, category_id)


@router.post("/checklists/{checklist_id}/items")
def create_item(checklist_id: int, body: ItemCreateBody, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return checklist_service.create_item(auth.user.id, checklist_id, body.category_id, body.title)


@router.patch("/checklists/{checklist_id}/items/{item_id}")
def update_item(
    checklist_id: int, item_id: int, body: ItemUpdateBody, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return checklist_service.update_item(auth.user.id, checklist_id, item_id, body.title, body.is_checked)


@router.delete("/checklists/{checklist_id}/items/{item_id}")
def delete_item(checklist_id: int, item_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return checklist_service.delete_item(auth.user.id, checklist_id, item_id)


@router.post("/checklists/{checklist_id}/items/{item_id}/move")
def move_item(
    checklist_id: int, item_id: int, body: ItemMoveBody, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return checklist_service.move_item(auth.user.id, checklist_id, item_id, body.to_category_id, body.to_index)
