from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.config import FEATURE_ID
from app.deps import AuthContext, get_current_user
from app.security import to_data_url
from app.services import feature_service

router = APIRouter(prefix="/features")


class FeatureCreateBody(BaseModel):
    id: str
    title: str
    url: str
    icon: str

    @field_validator("id", "title", "url", "icon")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("blank")
        return value


class FeatureUpdateBody(BaseModel):
    title: str
    url: str
    icon: str | None = None

    @field_validator("title", "url")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("blank")
        return value


def _feature_body(
    feature_id: str,
    title: str,
    url: str,
    icon: str,
) -> dict[str, object]:
    return {
        "id": feature_id,
        "title": title,
        "url": url,
        "icon": icon,
        "is_protected": feature_id == FEATURE_ID,
    }


@router.get("")
def list_features(_auth: AuthContext = Depends(get_current_user)) -> dict[str, list[dict[str, object]]]:
    items = [
        _feature_body(
            row.id,
            row.title,
            row.url,
            to_data_url(row.icon_media_type, row.icon),
        )
        for row in feature_service.list_features()
    ]
    return {"items": items}


@router.post("", status_code=201)
def create_feature(
    body: FeatureCreateBody,
    _auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        row = feature_service.add_feature(body.id, body.title, body.url, body.icon)
    except feature_service.InvalidIconError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except feature_service.DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None
    return _feature_body(
        row.id,
        row.title,
        row.url,
        to_data_url(row.icon_media_type, row.icon),
    )


@router.patch("/{feature_id}")
def patch_feature(
    feature_id: str,
    body: FeatureUpdateBody,
    _auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    icon = body.icon.strip() if body.icon else None
    if icon == "":
        icon = None
    try:
        row = feature_service.change_feature(feature_id, body.title, body.url, icon)
    except feature_service.InvalidIconError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except feature_service.NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    return _feature_body(
        row.id,
        row.title,
        row.url,
        to_data_url(row.icon_media_type, row.icon),
    )


@router.delete("/{feature_id}", status_code=204)
def delete_feature(
    feature_id: str,
    _auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        feature_service.remove_feature(feature_id)
    except feature_service.ForbiddenOpError:
        raise HTTPException(status_code=409, detail="削除できませんでした") from None
    except feature_service.NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
