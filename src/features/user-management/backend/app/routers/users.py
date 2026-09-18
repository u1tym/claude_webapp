from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.deps import AuthContext, get_current_user
from app.repos import UserRow
from app.services import user_service

router = APIRouter(prefix="/users")


def _email_format(value: str) -> str:
    stripped = value.strip()
    if stripped == "":
        raise ValueError("blank")
    if not user_service.email_is_valid(stripped):
        raise ValueError("email")
    return stripped


class UserCreateBody(BaseModel):
    username: str
    password: str
    email: str

    @field_validator("username", "password")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("blank")
        return value

    @field_validator("email")
    @classmethod
    def email_not_blank(cls, value: str) -> str:
        return _email_format(value)


class UserUpdateBody(BaseModel):
    username: str
    email: str
    password: str | None = None

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("blank")
        return value

    @field_validator("email")
    @classmethod
    def email_not_blank(cls, value: str) -> str:
        return _email_format(value)


def _user_body(user: UserRow, actor_id: int) -> dict[str, object]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_self": user.id == actor_id,
    }


@router.get("")
def list_users(auth: AuthContext = Depends(get_current_user)) -> dict[str, list[dict[str, object]]]:
    items = [_user_body(user, auth.user.id) for user in user_service.list_users()]
    return {"items": items}


@router.post("", status_code=201)
def create_user(
    body: UserCreateBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        user = user_service.add_user(body.username, body.password, body.email)
    except user_service.InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except user_service.DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None
    return _user_body(user, auth.user.id)


@router.patch("/{user_id}")
def patch_user(
    user_id: int,
    body: UserUpdateBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    password = body.password.strip() if body.password else None
    if password == "":
        password = None
    try:
        user = user_service.change_user(user_id, body.username, body.email, password)
    except user_service.InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except user_service.NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except user_service.DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None
    return _user_body(user, auth.user.id)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        user_service.remove_user(user_id, auth.user.id)
    except user_service.ForbiddenOpError:
        raise HTTPException(status_code=409, detail="削除できませんでした") from None
    except user_service.NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
