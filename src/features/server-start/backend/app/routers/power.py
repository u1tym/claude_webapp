from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.logger import safe_text, write
from app.services.start_service import StartBusyError, StartFailedError, run_start
from app.services.status_service import check_power_status

router = APIRouter()


class StartBody(BaseModel):
    confirmed: bool


@router.get("/status")
def get_status(auth: AuthContext = Depends(get_current_user)) -> dict[str, bool]:
    username = safe_text(auth.user.username)
    write("INF", f"状態参照要求 username={username}")
    is_up = check_power_status()
    write("INF", f"状態参照成功 username={username} is_up={str(is_up).lower()}")
    return {"is_up": is_up}


@router.post("/start", status_code=204)
def start_power(body: StartBody, auth: AuthContext = Depends(get_current_user)) -> None:
    username = safe_text(auth.user.username)
    confirmed = str(body.confirmed).lower()
    write("INF", f"起動指示 username={username} confirmed={confirmed}")
    try:
        run_start()
    except StartBusyError:
        write("WRN", f"起動指示失敗 username={username} 理由=実行中")
        raise HTTPException(status_code=409, detail="実行できませんでした") from None
    except StartFailedError as exc:
        write("WRN", f"起動指示失敗 username={username} 理由={exc.reason}")
        raise HTTPException(status_code=409, detail="実行できませんでした") from None
    write("INF", f"起動指示成功 username={username} confirmed={confirmed}")
