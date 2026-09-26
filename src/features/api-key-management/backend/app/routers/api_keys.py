from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictStr

from app.deps import AuthContext, get_current_user
from app.errors import AlreadyRevokedError, InvalidInputError, NotFoundError
from app.logger import write
from app.repos import ApiKeyRow
from app.services import api_key_service

router = APIRouter()


class IssueRequest(BaseModel):
    name: StrictStr
    expires_at: datetime | None = None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_item(row: ApiKeyRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "key_prefix": row.key_prefix,
        "status": api_key_service.status_of(row),
        "created_at": _iso(row.created_at),
        "expires_at": _iso(row.expires_at),
        "last_used_at": _iso(row.last_used_at),
        "revoked_at": _iso(row.revoked_at),
    }


@router.get("/api-keys")
def list_api_keys(auth: AuthContext = Depends(get_current_user)) -> dict[str, list[dict[str, Any]]]:
    write("INF", f"API キー一覧要求 username={auth.user.username}")
    rows = api_key_service.list_for_user(auth.user.id)
    write("INF", f"API キー一覧成功 username={auth.user.username} 件数={len(rows)}")
    return {"items": [_to_item(row) for row in rows]}


@router.post("/api-keys", status_code=201)
def issue_api_key(body: IssueRequest, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    expires = body.expires_at.isoformat() if body.expires_at is not None else None
    write("INF", f"API キー発行要求 username={auth.user.username} name={body.name} expires_at={expires}")
    try:
        issued = api_key_service.issue(auth.user.id, body.name, body.expires_at)
    except InvalidInputError as exc:
        write("WRN", f"API キー発行失敗 username={auth.user.username} 理由={exc}")
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    write(
        "INF",
        f"API キー発行成功 username={auth.user.username} id={issued.row.id} "
        f"prefix={issued.row.key_prefix} name={issued.row.name}",
    )
    return {**_to_item(issued.row), "key": issued.key}


@router.post("/api-keys/{api_key_id}/revoke")
def revoke_api_key(api_key_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    write("INF", f"API キー失効要求 username={auth.user.username} id={api_key_id}")
    try:
        row = api_key_service.revoke(auth.user.id, api_key_id)
    except NotFoundError:
        write("WRN", f"API キー失効失敗 username={auth.user.username} id={api_key_id} 理由=対象なし(存在しないまたは他人)")
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except AlreadyRevokedError:
        write("WRN", f"API キー失効失敗 username={auth.user.username} id={api_key_id} 理由=失効済み")
        raise HTTPException(status_code=409, detail="既に失効しています") from None
    write("INF", f"API キー失効成功 username={auth.user.username} id={row.id} prefix={row.key_prefix}")
    return _to_item(row)
