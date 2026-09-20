from __future__ import annotations


class AppError(Exception):
    """業務エラー。status_code と本文 detail は api-design.md の共通エラーに従う。"""

    status_code = 500
    default_detail = "サーバエラーです"

    def __init__(
        self,
        detail: str | None = None,
        *,
        reason: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.detail = detail if detail is not None else self.default_detail
        # 画面へ出さない内部理由。ログにだけ残す。
        self.reason = reason
        self.headers = headers
        super().__init__(self.detail)


class InvalidInputError(AppError):
    status_code = 400
    default_detail = "入力が不正です"


class NotFoundError(AppError):
    """存在しない、または他ユーザのもの。"""

    status_code = 404
    default_detail = "対象がありません"


class ConflictError(AppError):
    status_code = 409
    default_detail = "保存できませんでした"


class UnprocessableError(AppError):
    status_code = 422
    default_detail = "処理できない状態です"


class RangeNotSatisfiableError(AppError):
    status_code = 416
    default_detail = "指定の範囲は取得できません"
