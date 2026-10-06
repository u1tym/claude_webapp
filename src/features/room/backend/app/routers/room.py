from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import dimming
from app.actors import actor_for
from app.deps import AuthContext, get_current_user
from app.errors import DeviceOperationError, InvalidInputError, NotFoundError
from app.logger import write
from app.services import device_service, scene_service

router = APIRouter()


class DeviceStateBody(BaseModel):
    """個別切替の要求本文。目標の状態を必ず明示する（「反転」は受けない）。"""

    state: str | None = None
    # 調光パターン。電灯を ON にするときだけ指定できる（省略時は既定のパターン）
    pattern: str | None = None


class SceneBody(BaseModel):
    """一括切替の要求本文（任意）。調光パターンは、電灯選択のときだけ指定できる。"""

    pattern: str | None = None


@router.get("/dimming-patterns")
def get_dimming_patterns(auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """固定の調光パターン 4 種と、既定のパターンを返す。SwitchBot へは問い合わせない。"""
    write("INF", f"調光パターン取得要求 username={auth.user.username} 経路={auth.via}")
    return {
        "default": dimming.DEFAULT_PATTERN_ID,
        "patterns": [p.to_dict() for p in dimming.PATTERNS],
    }


@router.get("/state")
def get_state(auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """5 機器の状態と取得日時を返す。機器の取得失敗は status=error で示し、200 を返す。"""
    write("INF", f"状態取得要求 username={auth.user.username} 経路={auth.via}")
    return device_service.fetch_states().to_dict()


@router.post("/scenes/{scene}")
def post_scene(
    scene: str,
    body: SceneBody | None = None,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """一括切替を実行する。一部の機器が失敗しても 200 を返し、機器ごとの成否を示す。"""
    try:
        result = scene_service.run_scene(
            scene,
            actor=actor_for(auth.via),
            username=auth.user.username,
            pattern=body.pattern if body is not None else None,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    return result.to_dict()


@router.put("/devices/{device}/state")
def put_device_state(
    device: str,
    body: DeviceStateBody | None = None,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """1 機器を目標の状態へ切り替える。"""
    target = body.state if body is not None else None
    pattern = body.pattern if body is not None else None
    try:
        result = device_service.switch_device(
            device,
            target,
            actor=actor_for(auth.via),
            username=auth.user.username,
            pattern=pattern,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except DeviceOperationError:
        raise HTTPException(status_code=502, detail="機器を操作できませんでした") from None
    return result.to_dict()
