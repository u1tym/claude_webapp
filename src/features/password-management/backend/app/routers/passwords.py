from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import DuplicateError, InvalidInputError, NotFoundError
from app.services import password_service

router = APIRouter(prefix="/passwords")


class PasswordBody(BaseModel):
    title: str
    userword: str
    psword: str
    site: str | None = None
    memo: str | None = None


@router.get("")
def list_passwords(
    keyword: str | None = Query(default=None),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    items = password_service.list_for_user(auth.user.id, keyword)
    return {"total": len(items), "items": items}


@router.get("/{entry_id}")
def get_password(
    entry_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return password_service.get_for_user(auth.user.id, entry_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.post("", status_code=201)
def create_password(
    body: PasswordBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return password_service.create_entry(
            auth.user.id, body.title, body.userword, body.psword, body.site, body.memo
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None


@router.patch("/{entry_id}")
def update_password(
    entry_id: int,
    body: PasswordBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return password_service.change_entry(
            auth.user.id, entry_id, body.title, body.userword, body.psword, body.site, body.memo
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None


@router.delete("/{entry_id}", status_code=204)
def delete_password(
    entry_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        password_service.remove_entry(auth.user.id, entry_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
