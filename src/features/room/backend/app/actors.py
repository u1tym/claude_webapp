from __future__ import annotations

# 操作ログに残す「実行した主体」
ACTOR_SCREEN = "画面の利用者"
ACTOR_API = "API の利用者"
ACTOR_JOB = "定期実行"


def actor_for(via: str) -> str:
    """認証の経路から、実行した主体の表記を返す。API キーは API の利用者、それ以外は画面の利用者。"""
    return ACTOR_API if via == "api_key" else ACTOR_SCREEN
