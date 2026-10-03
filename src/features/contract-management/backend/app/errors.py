from __future__ import annotations


class NotFoundError(Exception):
    """対象がない（他人の行、削除済み、存在しない ID を含む）。404。"""


class InvalidInputError(Exception):
    """入力不正。400。"""


class ConflictError(Exception):
    """競合（名称の重複、依存の循環、使用中の区分の削除など）。409。"""
