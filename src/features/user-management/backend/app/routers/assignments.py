from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.config import FEATURE_ID
from app.deps import AuthContext, get_current_user
from app.services import assignment_service

router = APIRouter(prefix="/assignments")


class AssignmentCreateBody(BaseModel):
    user_id: int
    feature_id: str
    display_order: int

    @field_validator("feature_id")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("blank")
        return value


def _item(
    user_id: int,
    username: str,
    feature_id: str,
    feature_title: str,
    display_order: int,
    actor_id: int,
) -> dict[str, object]:
    return {
        "user_id": user_id,
        "username": username,
        "feature_id": feature_id,
        "feature_title": feature_title,
        "display_order": display_order,
        "can_unassign": not (user_id == actor_id and feature_id == FEATURE_ID),
    }


@router.get("")
def list_assignments(
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    items = [
        _item(
            row.user_id,
            row.username,
            row.feature_id,
            row.feature_title,
            row.display_order,
            auth.user.id,
        )
        for row in assignment_service.list_assignments()
    ]
    return {"items": items}


@router.post("", status_code=201)
def create_assignment(
    body: AssignmentCreateBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        row = assignment_service.add_assignment(body.user_id, body.feature_id, body.display_order)
    except assignment_service.NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except assignment_service.DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None
    return _item(
        row.user_id,
        row.username,
        row.feature_id,
        row.feature_title,
        row.display_order,
        auth.user.id,
    )


@router.delete("/{user_id}/{feature_id}", status_code=204)
def delete_assignment(
    user_id: int,
    feature_id: str,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        assignment_service.remove_assignment(user_id, feature_id, auth.user.id)
    except assignment_service.ForbiddenOpError:
        raise HTTPException(status_code=409, detail="削除できませんでした") from None
    except assignment_service.NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
