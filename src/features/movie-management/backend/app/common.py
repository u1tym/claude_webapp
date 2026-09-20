"""複数のルータ・サービスで使う共通部品（入力の型、ページ分け）。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, StringConstraints

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

# 前後の空白を除いた結果が空のときは入力不正（検証エラー → 400）
Title500 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Name100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Text500 = Annotated[str, StringConstraints(max_length=500)]


@dataclass(frozen=True)
class Page:
    page: int
    per_page: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=MAX_PER_PAGE)] = DEFAULT_PER_PAGE,
) -> Page:
    return Page(page=page, per_page=per_page)


class Pagination(BaseModel):
    page: int
    per_page: int
    total_count: int
    total_pages: int


def build_pagination(paging: Page, total_count: int) -> Pagination:
    total_pages = 0 if total_count == 0 else math.ceil(total_count / paging.per_page)
    return Pagination(
        page=paging.page,
        per_page=paging.per_page,
        total_count=total_count,
        total_pages=total_pages,
    )


def like_pattern(keyword: str) -> str:
    """ILIKE の部分一致用パターン。% _ \\ を文字として扱う。"""
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
