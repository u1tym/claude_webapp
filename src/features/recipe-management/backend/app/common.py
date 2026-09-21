"""複数のルータ・サービスで使う共通部品（入力の型）。"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

# 前後の空白を除いた結果が空のときは入力不正（検証エラー → 400）
Required = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
# 空文字を許す文字列（前後の空白は除く）
Trimmed = Annotated[str, StringConstraints(strip_whitespace=True)]
